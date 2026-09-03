"""Cliente do backend remoto usado pelo executável portátil."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .service import ActiveSession, IssuedSession, UserIdentity


# Endereço público e não secreto. Ele será preenchido depois que o serviço
# for criado na hospedagem e então incorporado ao SignTime.exe.
DEFAULT_AUTH_API_URL = ""
DEFAULT_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class RemoteAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class RemoteAPIUnavailable(RemoteAPIError):
    def __init__(self, message: str = "O serviço de acesso está indisponível.") -> None:
        super().__init__(message, HTTPStatus.SERVICE_UNAVAILABLE)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


REMOTE_OPENER = build_opener(_NoRedirect())


@dataclass(frozen=True)
class RemoteLogin:
    user: UserIdentity
    issued_session: IssuedSession
    max_age: int


@dataclass(frozen=True)
class RemoteResponse:
    status_code: int
    payload: dict


def auth_api_url() -> str:
    value = os.getenv("SIGNTIME_AUTH_API_URL", "").strip() or DEFAULT_AUTH_API_URL
    return value.rstrip("/")


def remote_auth_enabled() -> bool:
    return bool(auth_api_url())


def _validated_base_url() -> str:
    base_url = auth_api_url()
    if not base_url:
        raise RemoteAPIUnavailable("O endereço do serviço de acesso não foi configurado.")
    parsed = urlparse(base_url)
    is_local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_local):
        raise RemoteAPIUnavailable("O serviço de acesso precisa usar uma conexão HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RemoteAPIUnavailable("O endereço do serviço de acesso é inválido.")
    return f"{base_url}/"


def _error_message(payload: object, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("error", "detail", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _decode_payload(body: bytes) -> dict:
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RemoteAPIUnavailable("O serviço de acesso retornou uma resposta inválida.") from exc
    if not isinstance(payload, dict):
        raise RemoteAPIUnavailable("O serviço de acesso retornou uma resposta inválida.")
    return payload


def remote_request(
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    session_token: str = "",
    csrf_token: str = "",
) -> RemoteResponse:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "User-Agent": "SignTime-Desktop/2.2"}
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    if session_token:
        headers["Authorization"] = f"Bearer {session_token}"
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token

    request = Request(
        urljoin(_validated_base_url(), path.lstrip("/")),
        data=body,
        headers=headers,
        method=method.upper(),
    )
    try:
        with REMOTE_OPENER.open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(response_body) > MAX_RESPONSE_BYTES:
                raise RemoteAPIUnavailable("O serviço de acesso retornou dados em excesso.")
            return RemoteResponse(response.status, _decode_payload(response_body))
    except HTTPError as exc:
        error_body = exc.read()
        try:
            error_payload = _decode_payload(error_body)
        except RemoteAPIUnavailable:
            error_payload = {}
        message = _error_message(error_payload, "Não foi possível concluir a solicitação.")
        raise RemoteAPIError(message, exc.code) from exc
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise RemoteAPIUnavailable() from exc


def _user_from_payload(payload: object) -> UserIdentity:
    if not isinstance(payload, dict):
        raise RemoteAPIUnavailable("O serviço de acesso retornou um usuário inválido.")
    try:
        role = str(payload["role"])
        if role not in {"admin", "user"}:
            raise ValueError("invalid role")
        return UserIdentity(
            id=str(payload["id"]),
            username=str(payload["username"]),
            email=str(payload["email"]) if payload.get("email") else None,
            full_name=str(payload["full_name"]),
            role=role,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RemoteAPIUnavailable("O serviço de acesso retornou um usuário inválido.") from exc


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise RemoteAPIUnavailable("O serviço de acesso retornou uma sessão inválida.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RemoteAPIUnavailable("O serviço de acesso retornou uma sessão inválida.") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def remote_login(username: str, password: str) -> RemoteLogin:
    response = remote_request(
        "POST",
        "/v1/auth/login",
        payload={"username": username, "password": password},
    )
    session = response.payload.get("session")
    if not isinstance(session, dict):
        raise RemoteAPIUnavailable("O serviço de acesso não criou a sessão.")
    try:
        issued = IssuedSession(
            token=str(session["token"]),
            csrf_token=str(session["csrf_token"]),
            expires_at=_datetime(session["expires_at"]),
        )
        max_age = int(session["max_age"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RemoteAPIUnavailable("O serviço de acesso retornou uma sessão inválida.") from exc
    if not issued.token or not issued.csrf_token or max_age <= 0:
        raise RemoteAPIUnavailable("O serviço de acesso retornou uma sessão inválida.")
    return RemoteLogin(
        user=_user_from_payload(response.payload.get("user")),
        issued_session=issued,
        max_age=max_age,
    )


def remote_find_active_session(session_token: str) -> ActiveSession | None:
    try:
        response = remote_request(
            "GET",
            "/v1/auth/session",
            session_token=session_token,
        )
    except RemoteAPIError as exc:
        if exc.status_code == HTTPStatus.UNAUTHORIZED:
            return None
        raise
    session = response.payload.get("session")
    if not isinstance(session, dict):
        raise RemoteAPIUnavailable("O serviço de acesso retornou uma sessão inválida.")
    return ActiveSession(
        id=str(session.get("id", "")),
        token_hash="",
        csrf_token_hash="",
        expires_at=_datetime(session.get("expires_at")),
        user=_user_from_payload(response.payload.get("user")),
    )


def remote_logout(session_token: str, csrf_token: str) -> None:
    remote_request(
        "POST",
        "/v1/auth/logout",
        session_token=session_token,
        csrf_token=csrf_token,
    )


def remote_admin_request(
    method: str,
    path: str,
    *,
    session_token: str,
    csrf_token: str = "",
    payload: dict | None = None,
) -> RemoteResponse:
    return remote_request(
        method,
        path,
        payload=payload,
        session_token=session_token,
        csrf_token=csrf_token,
    )
