"""API HTTPS de autenticação e administração do SignTime."""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from auth.admin_service import (
    ManagedUserNotFound,
    ProtectedAdministrator,
    UserManagementError,
    create_managed_user,
    delete_managed_user,
    list_managed_users,
    set_managed_user_active,
    update_managed_user,
)
from auth.database import check_database_connection
from auth.service import (
    AccountLocked,
    ActiveSession,
    InvalidCredentials,
    UserAlreadyExists,
    authenticate_user,
    cleanup_expired_sessions,
    find_active_session,
    issue_session,
    revoke_session,
    session_duration_seconds,
    validate_csrf,
)


MAX_JSON_BYTES = 64 * 1024


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class CreateUserPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    full_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    role: Literal["admin", "user"] = "user"


class UpdateUserPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str | None = Field(default=None, max_length=256)
    full_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    role: Literal["admin", "user"]


class UserStatusPayload(BaseModel):
    is_active: bool


class LoginRateLimiter:
    """Limite curto por origem; o bloqueio persistente continua por usuário."""

    def __init__(self, limit: int = 12, window_seconds: int = 300) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._attempts[key]
        cutoff = now - self.window_seconds
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        return attempts

    def allowed(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) < self.limit

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.monotonic()).append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


LOGIN_LIMITER = LoginRateLimiter()

app = FastAPI(
    title="SignTime Auth API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _error(message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail=message)


def _user_payload(session: ActiveSession) -> dict:
    user = session.user
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
    }


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _error("Sessão não encontrada.", status.HTTP_401_UNAUTHORIZED)
    return token.strip()


def _active_session(token: Annotated[str, Depends(_bearer_token)]) -> ActiveSession:
    session = find_active_session(token)
    if session is None:
        raise _error("Sua sessão expirou. Entre novamente.", status.HTTP_401_UNAUTHORIZED)
    return session


def _admin_session(
    session: Annotated[ActiveSession, Depends(_active_session)],
) -> ActiveSession:
    if session.user.role != "admin":
        raise _error(
            "Acesso exclusivo para administradores.",
            status.HTTP_403_FORBIDDEN,
        )
    return session


def _require_csrf(session: ActiveSession, csrf_token: str | None) -> None:
    if not csrf_token or not validate_csrf(session, csrf_token):
        raise _error(
            "Validação de segurança inválida. Atualize a página.",
            status.HTTP_403_FORBIDDEN,
        )


@app.middleware("http")
async def secure_responses(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_JSON_BYTES:
                return JSONResponse(
                    {"error": "A solicitação excede o limite permitido."},
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )
        except ValueError:
            return JSONResponse(
                {"error": "Tamanho de solicitação inválido."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Solicitação inválida."
    return JSONResponse({"error": message}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(
        {"error": "Confira os dados informados e tente novamente."},
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, _exc: Exception):
    return JSONResponse(
        {"error": "O serviço está temporariamente indisponível."},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.get("/v1/health")
def health() -> dict:
    if not check_database_connection():
        raise _error("Banco indisponível.", status.HTTP_503_SERVICE_UNAVAILABLE)
    return {"status": "ok", "service": "signtime-auth", "version": "1.0.0"}


@app.post("/v1/auth/login")
def login(payload: LoginPayload, request: Request) -> dict:
    client_key = _client_key(request)
    if not LOGIN_LIMITER.allowed(client_key):
        raise _error(
            "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    try:
        user = authenticate_user(payload.username, payload.password)
    except InvalidCredentials as exc:
        LOGIN_LIMITER.record_failure(client_key)
        raise _error("Usuário ou senha inválidos.", status.HTTP_401_UNAUTHORIZED) from exc
    except AccountLocked as exc:
        LOGIN_LIMITER.record_failure(client_key)
        raise _error(str(exc), status.HTTP_429_TOO_MANY_REQUESTS) from exc

    LOGIN_LIMITER.clear(client_key)
    issued = issue_session(user.id)
    try:
        cleanup_expired_sessions()
    except Exception:
        pass
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
        },
        "session": {
            "token": issued.token,
            "csrf_token": issued.csrf_token,
            "expires_at": issued.expires_at.isoformat(),
            "max_age": session_duration_seconds(),
        },
    }


@app.get("/v1/auth/session")
def session_status(
    session: Annotated[ActiveSession, Depends(_active_session)],
) -> dict:
    return {
        "authenticated": True,
        "user": _user_payload(session),
        "session": {
            "id": session.id,
            "expires_at": session.expires_at.isoformat(),
        },
    }


@app.post("/v1/auth/logout")
def logout(
    session: Annotated[ActiveSession, Depends(_active_session)],
    token: Annotated[str, Depends(_bearer_token)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict:
    _require_csrf(session, x_csrf_token)
    revoke_session(token)
    return {"authenticated": False}


@app.get("/v1/admin/users")
def users_list(
    _session: Annotated[ActiveSession, Depends(_admin_session)],
) -> dict:
    users = [user.to_dict() for user in list_managed_users()]
    return {"users": users, "count": len(users)}


@app.post("/v1/admin/users", status_code=status.HTTP_201_CREATED)
def user_create(
    payload: CreateUserPayload,
    session: Annotated[ActiveSession, Depends(_admin_session)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict:
    _require_csrf(session, x_csrf_token)
    try:
        user = create_managed_user(**payload.model_dump())
    except UserAlreadyExists as exc:
        raise _error(str(exc), status.HTTP_409_CONFLICT) from exc
    except (ValueError, UserManagementError) as exc:
        raise _error(str(exc), status.HTTP_400_BAD_REQUEST) from exc
    return {"user": user.to_dict()}


@app.patch("/v1/admin/users/{user_id}")
def user_update(
    user_id: str,
    payload: UpdateUserPayload,
    session: Annotated[ActiveSession, Depends(_admin_session)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict:
    _require_csrf(session, x_csrf_token)
    try:
        user = update_managed_user(
            user_id=user_id,
            actor_user_id=session.user.id,
            **payload.model_dump(),
        )
    except ManagedUserNotFound as exc:
        raise _error(str(exc), status.HTTP_404_NOT_FOUND) from exc
    except (ProtectedAdministrator, UserAlreadyExists) as exc:
        raise _error(str(exc), status.HTTP_409_CONFLICT) from exc
    except (ValueError, UserManagementError) as exc:
        raise _error(str(exc), status.HTTP_400_BAD_REQUEST) from exc
    return {"user": user.to_dict()}


@app.patch("/v1/admin/users/{user_id}/status")
def user_status(
    user_id: str,
    payload: UserStatusPayload,
    session: Annotated[ActiveSession, Depends(_admin_session)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict:
    _require_csrf(session, x_csrf_token)
    try:
        user = set_managed_user_active(
            user_id=user_id,
            actor_user_id=session.user.id,
            is_active=payload.is_active,
        )
    except ManagedUserNotFound as exc:
        raise _error(str(exc), status.HTTP_404_NOT_FOUND) from exc
    except ProtectedAdministrator as exc:
        raise _error(str(exc), status.HTTP_409_CONFLICT) from exc
    except UserManagementError as exc:
        raise _error(str(exc), status.HTTP_400_BAD_REQUEST) from exc
    return {"user": user.to_dict()}


@app.delete("/v1/admin/users/{user_id}")
def user_delete(
    user_id: str,
    session: Annotated[ActiveSession, Depends(_admin_session)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict:
    _require_csrf(session, x_csrf_token)
    try:
        delete_managed_user(user_id=user_id, actor_user_id=session.user.id)
    except ManagedUserNotFound as exc:
        raise _error(str(exc), status.HTTP_404_NOT_FOUND) from exc
    except ProtectedAdministrator as exc:
        raise _error(str(exc), status.HTTP_409_CONFLICT) from exc
    except UserManagementError as exc:
        raise _error(str(exc), status.HTTP_400_BAD_REQUEST) from exc
    return {"deleted": True}
