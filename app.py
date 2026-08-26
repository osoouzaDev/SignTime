"""Servidor web do SignTime com autenticação persistida no PostgreSQL."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import os
import sys
import tempfile
import threading
import time
import webbrowser
from collections import defaultdict, deque
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

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
from auth.service import (
    AccountLocked,
    UserAlreadyExists,
    ActiveSession,
    InvalidCredentials,
    authenticate_user,
    cleanup_expired_sessions,
    find_active_session,
    issue_session,
    revoke_session,
    session_duration_seconds,
    validate_csrf,
)
from contratos import ContractError, analyze_inputs, generate_contracts_zip


RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DATA_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
WEB_DIR = RESOURCE_DIR / "web"
MAX_BODY_BYTES = 70 * 1024 * 1024
MAX_FILE_BYTES = 25 * 1024 * 1024
SESSION_COOKIE = "signtime_session"
CSRF_COOKIE = "signtime_csrf"


def load_local_env(path: Path) -> None:
    """Carrega as variáveis locais sem sobrescrever o ambiente do servidor."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_local_env(DATA_DIR / ".env")
if getattr(sys, "frozen", False) and not os.getenv("DATABASE_URL"):
    # Facilita o teste do build dentro de dist/ sem copiar o segredo para lá.
    load_local_env(DATA_DIR.parent / ".env")


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


class LoginRateLimiter:
    """Limite simples por endereço para reduzir tentativas automatizadas."""

    def __init__(self, limit: int = 10, window_seconds: int = 300) -> None:
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


class ContractHandler(BaseHTTPRequestHandler):
    server_version = "SignTime/2.0"

    def log_message(self, format: str, *args) -> None:
        if getattr(self.server, "verbose", False):
            super().log_message(format, *args)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        if env_flag("COOKIE_SECURE"):
            self.send_header(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )

    def _send_json(
        self,
        payload: dict,
        status: int = HTTPStatus.OK,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._send_json({"error": message}, status)

    def _redirect(self, target: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target)
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()

    def _read_json(self, max_bytes: int = MAX_BODY_BYTES) -> dict:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            raise ContractError("A solicitação chegou sem conteúdo.")
        try:
            length = int(content_length)
        except ValueError as exc:
            raise ContractError("Tamanho de solicitação inválido.") from exc
        if length > max_bytes:
            raise ContractError("A solicitação excede o limite permitido.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ContractError("Não foi possível interpretar os dados enviados.") from exc
        if not isinstance(payload, dict):
            raise ContractError("Conteúdo da solicitação inválido.")
        return payload

    def _save_upload(
        self,
        upload: dict,
        directory: Path,
        allowed_extensions: set[str],
        label: str,
    ) -> Path:
        if not isinstance(upload, dict):
            raise ContractError(f"Envie {label}.")
        filename = Path(str(upload.get("name", ""))).name
        suffix = Path(filename).suffix.lower()
        if suffix not in allowed_extensions:
            formats = ", ".join(sorted(allowed_extensions))
            raise ContractError(f"{label.capitalize()} inválido. Use {formats}.")
        encoded = str(upload.get("data", ""))
        if "," in encoded and encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ContractError(f"Não foi possível ler {label}.") from exc
        if not content:
            raise ContractError(f"{label.capitalize()} vazio.")
        if len(content) > MAX_FILE_BYTES:
            raise ContractError(f"{label.capitalize()} excede 25 MB.")
        target = directory / f"upload{suffix}"
        target.write_bytes(content)
        return target

    def _serve_static(self, request_path: str) -> None:
        routes = {
            "/": "index.html",
            "/index.html": "index.html",
            "/login": "login.html",
            "/login.html": "login.html",
            "/admin": "admin.html",
            "/admin.html": "admin.html",
            "/admin.css": "admin.css",
            "/admin.js": "admin.js",
            "/styles.css": "styles.css",
            "/auth.css": "auth.css",
            "/app.js": "app.js",
            "/login.js": "login.js",
            "/signtime-logo.png": "signtime-logo.png",
            "/modelo-planilha-signtime.xlsx": "modelo_planilha_signtime.xlsx",
        }
        filename = routes.get(request_path)
        if not filename:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = WEB_DIR / filename
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        content_type = (
            f"{mime}; charset=utf-8"
            if mime.startswith("text/") or mime in {"application/javascript"}
            else mime
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cookie_value(self, name: str) -> str:
        raw_cookie = self.headers.get("Cookie", "")
        if not raw_cookie:
            return ""
        cookie = SimpleCookie()
        try:
            cookie.load(raw_cookie)
        except Exception:
            return ""
        morsel = cookie.get(name)
        return morsel.value if morsel else ""

    def _session_cookie(self, token: str, max_age: int) -> str:
        parts = [
            f"{SESSION_COOKIE}={token}",
            "Path=/",
            f"Max-Age={max_age}",
            "HttpOnly",
            "SameSite=Strict",
        ]
        if env_flag("COOKIE_SECURE"):
            parts.append("Secure")
        return "; ".join(parts)

    def _csrf_cookie(self, token: str, max_age: int) -> str:
        parts = [
            f"{CSRF_COOKIE}={token}",
            "Path=/",
            f"Max-Age={max_age}",
            "SameSite=Strict",
        ]
        if env_flag("COOKIE_SECURE"):
            parts.append("Secure")
        return "; ".join(parts)

    def _clear_cookie_headers(self) -> list[tuple[str, str]]:
        secure = "; Secure" if env_flag("COOKIE_SECURE") else ""
        return [
            (
                "Set-Cookie",
                f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict{secure}",
            ),
            (
                "Set-Cookie",
                f"{CSRF_COOKIE}=; Path=/; Max-Age=0; SameSite=Strict{secure}",
            ),
        ]

    def _current_session(self) -> ActiveSession | None:
        if hasattr(self, "_cached_auth_session"):
            return self._cached_auth_session
        token = self._cookie_value(SESSION_COOKIE)
        self._cached_auth_session = find_active_session(token) if token else None
        return self._cached_auth_session

    def _require_session(self) -> ActiveSession | None:
        session = self._current_session()
        if session is None:
            self._send_error("Sua sessão expirou. Entre novamente.", HTTPStatus.UNAUTHORIZED)
        return session

    def _valid_csrf(self, session: ActiveSession) -> bool:
        header_token = self.headers.get("X-CSRF-Token", "")
        cookie_token = self._cookie_value(CSRF_COOKIE)
        return (
            bool(header_token)
            and header_token == cookie_token
            and validate_csrf(session, header_token)
        )

    def _client_key(self) -> str:
        return self.client_address[0] if self.client_address else "unknown"

    def _user_payload(self, session: ActiveSession) -> dict:
        return {
            "id": session.user.id,
            "username": session.user.username,
            "full_name": session.user.full_name,
            "email": session.user.email,
            "role": session.user.role,
        }

    def _require_admin(self, session: ActiveSession) -> bool:
        if session.user.role != "admin":
            self._send_error(
                "Acesso exclusivo para administradores.",
                HTTPStatus.FORBIDDEN,
            )
            return False
        return True

    def _handle_admin_users_list(self) -> None:
        users = [user.to_dict() for user in list_managed_users()]
        self._send_json({"users": users, "count": len(users)})

    def _handle_admin_user_create(self) -> None:
        payload = self._read_json(max_bytes=64 * 1024)
        user = create_managed_user(
            username=str(payload.get("username", "")),
            password=str(payload.get("password", "")),
            full_name=str(payload.get("full_name", "")),
            email=(
                str(payload.get("email", "")).strip()
                if payload.get("email")
                else None
            ),
            role=str(payload.get("role", "user")),
        )
        self._send_json(
            {"user": user.to_dict()},
            status=HTTPStatus.CREATED,
        )

    def _handle_admin_user_update(
        self, session: ActiveSession, user_id: str
    ) -> None:
        payload = self._read_json(max_bytes=64 * 1024)
        user = update_managed_user(
            user_id=user_id,
            actor_user_id=session.user.id,
            username=str(payload.get("username", "")),
            full_name=str(payload.get("full_name", "")),
            email=(
                str(payload.get("email", "")).strip()
                if payload.get("email")
                else None
            ),
            role=str(payload.get("role", "user")),
            password=str(payload.get("password", "")) or None,
        )
        self._send_json({"user": user.to_dict()})

    def _handle_admin_user_status(
        self, session: ActiveSession, user_id: str
    ) -> None:
        payload = self._read_json(max_bytes=16 * 1024)
        is_active = payload.get("is_active")
        if not isinstance(is_active, bool):
            raise ValueError("Informe se o usuário deve ficar ativo ou desativado.")
        user = set_managed_user_active(
            user_id=user_id,
            actor_user_id=session.user.id,
            is_active=is_active,
        )
        self._send_json({"user": user.to_dict()})

    def _handle_admin_user_delete(
        self, session: ActiveSession, user_id: str
    ) -> None:
        delete_managed_user(
            user_id=user_id,
            actor_user_id=session.user.id,
        )
        self._send_json({"deleted": True})
    def _handle_login(self) -> None:
        client_key = self._client_key()
        if not LOGIN_LIMITER.allowed(client_key):
            self._send_error(
                "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
                HTTPStatus.TOO_MANY_REQUESTS,
            )
            return
        payload = self._read_json(max_bytes=16 * 1024)
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        if len(username) > 80 or len(password) > 256:
            LOGIN_LIMITER.record_failure(client_key)
            self._send_error("Usuário ou senha inválidos.", HTTPStatus.UNAUTHORIZED)
            return
        try:
            user = authenticate_user(username, password)
        except InvalidCredentials:
            LOGIN_LIMITER.record_failure(client_key)
            self._send_error("Usuário ou senha inválidos.", HTTPStatus.UNAUTHORIZED)
            return
        except AccountLocked:
            LOGIN_LIMITER.record_failure(client_key)
            self._send_error(
                "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
                HTTPStatus.TOO_MANY_REQUESTS,
            )
            return

        LOGIN_LIMITER.clear(client_key)
        issued = issue_session(user.id)
        try:
            cleanup_expired_sessions()
        except Exception:
            # A limpeza é de manutenção e não deve impedir um login válido.
            if getattr(self.server, "verbose", False):
                self.log_error("Não foi possível limpar sessões antigas")
        max_age = session_duration_seconds()
        self._send_json(
            {
                "authenticated": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "email": user.email,
                    "role": user.role,
                },
            },
            extra_headers=[
                ("Set-Cookie", self._session_cookie(issued.token, max_age)),
                ("Set-Cookie", self._csrf_cookie(issued.csrf_token, max_age)),
            ],
        )

    def _handle_logout(self, session: ActiveSession) -> None:
        if not self._valid_csrf(session):
            self._send_error("Validação de segurança inválida.", HTTPStatus.FORBIDDEN)
            return
        revoke_session(self._cookie_value(SESSION_COOKIE))
        self._send_json(
            {"authenticated": False}, extra_headers=self._clear_cookie_headers()
        )

    def do_GET(self) -> None:
        request_path = unquote(urlparse(self.path).path)
        public_static = {
            "/styles.css",
            "/auth.css",
            "/login.js",
            "/signtime-logo.png",
        }
        try:
            if request_path == "/api/health":
                self._send_json({"status": "ok", "version": "2.1"})
                return
            if request_path in public_static:
                self._serve_static(request_path)
                return
            if request_path in {"/login", "/login.html"}:
                if self._current_session():
                    self._redirect("/")
                else:
                    self._serve_static(request_path)
                return
            if request_path == "/api/auth/session":
                session = self._current_session()
                if session is None:
                    self._send_error(
                        "Sessão não encontrada.",
                        HTTPStatus.UNAUTHORIZED,
                    )
                else:
                    self._send_json(
                        {
                            "authenticated": True,
                            "user": self._user_payload(session),
                        }
                    )
                return

            session = self._current_session()
            if session is None:
                if request_path.startswith("/api/"):
                    self._send_error(
                        "Sua sessão expirou. Entre novamente.",
                        HTTPStatus.UNAUTHORIZED,
                    )
                else:
                    self._redirect("/login")
                return

            if request_path == "/api/admin/users":
                if self._require_admin(session):
                    self._handle_admin_users_list()
                return

            admin_static = {
                "/admin",
                "/admin.html",
                "/admin.css",
                "/admin.js",
            }
            if request_path in admin_static and session.user.role != "admin":
                if request_path in {"/admin", "/admin.html"}:
                    self._redirect("/")
                else:
                    self._send_error(
                        "Acesso exclusivo para administradores.",
                        HTTPStatus.FORBIDDEN,
                    )
                return

            if request_path == "/api/config":
                self._send_json(
                    {
                        "clicksign_configured": bool(
                            os.getenv("CLICKSIGN_ACCESS_TOKEN", "").strip()
                        ),
                        "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
                    }
                )
                return
            self._serve_static(request_path)
        except BrokenPipeError:
            return
        except Exception:
            if getattr(self.server, "verbose", False):
                self.log_error("Falha ao atender GET")
            self._send_error(
                "Não foi possível acessar o serviço.",
                HTTPStatus.SERVICE_UNAVAILABLE,
            )

    def do_POST(self) -> None:
        request_path = unquote(urlparse(self.path).path)
        try:
            if request_path == "/api/auth/login":
                self._handle_login()
                return

            session = self._require_session()
            if session is None:
                return
            if request_path == "/api/auth/logout":
                self._handle_logout(session)
                return
            if not self._valid_csrf(session):
                self._send_error(
                    "Validação de segurança inválida. Atualize a página.",
                    HTTPStatus.FORBIDDEN,
                )
                return

            if request_path == "/api/admin/users":
                if self._require_admin(session):
                    self._handle_admin_user_create()
                return
            if request_path == "/api/analyze":
                self._handle_analyze()
            elif request_path == "/api/generate":
                self._handle_generate()
            else:
                self._send_error("Endereço não encontrado.", HTTPStatus.NOT_FOUND)
        except UserAlreadyExists as exc:
            self._send_error(str(exc), HTTPStatus.CONFLICT)
        except (ValueError, UserManagementError) as exc:
            self._send_error(str(exc))
        except ContractError as exc:
            self._send_error(str(exc))
        except BrokenPipeError:
            return
        except Exception:
            if getattr(self.server, "verbose", False):
                self.log_error("Falha ao atender POST")
            self._send_error(
                "Ocorreu um erro inesperado. Tente novamente.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_PATCH(self) -> None:
        request_path = unquote(urlparse(self.path).path)
        try:
            session = self._require_session()
            if session is None:
                return
            if not self._require_admin(session):
                return
            if not self._valid_csrf(session):
                self._send_error(
                    "Validação de segurança inválida. Atualize a página.",
                    HTTPStatus.FORBIDDEN,
                )
                return

            parts = request_path.strip("/").split("/")
            if len(parts) == 4 and parts[:3] == ["api", "admin", "users"]:
                self._handle_admin_user_update(session, parts[3])
            elif (
                len(parts) == 5
                and parts[:3] == ["api", "admin", "users"]
                and parts[4] == "status"
            ):
                self._handle_admin_user_status(session, parts[3])
            else:
                self._send_error(
                    "Endereço não encontrado.",
                    HTTPStatus.NOT_FOUND,
                )
        except ManagedUserNotFound as exc:
            self._send_error(str(exc), HTTPStatus.NOT_FOUND)
        except (ProtectedAdministrator, UserAlreadyExists) as exc:
            self._send_error(str(exc), HTTPStatus.CONFLICT)
        except (ValueError, UserManagementError) as exc:
            self._send_error(str(exc))
        except BrokenPipeError:
            return
        except Exception:
            if getattr(self.server, "verbose", False):
                self.log_error("Falha ao atender PATCH")
            self._send_error(
                "Ocorreu um erro inesperado. Tente novamente.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_DELETE(self) -> None:
        request_path = unquote(urlparse(self.path).path)
        try:
            session = self._require_session()
            if session is None:
                return
            if not self._require_admin(session):
                return
            if not self._valid_csrf(session):
                self._send_error(
                    "Validação de segurança inválida. Atualize a página.",
                    HTTPStatus.FORBIDDEN,
                )
                return

            parts = request_path.strip("/").split("/")
            if len(parts) == 4 and parts[:3] == ["api", "admin", "users"]:
                self._handle_admin_user_delete(session, parts[3])
            else:
                self._send_error(
                    "Endereço não encontrado.",
                    HTTPStatus.NOT_FOUND,
                )
        except ManagedUserNotFound as exc:
            self._send_error(str(exc), HTTPStatus.NOT_FOUND)
        except ProtectedAdministrator as exc:
            self._send_error(str(exc), HTTPStatus.CONFLICT)
        except UserManagementError as exc:
            self._send_error(str(exc))
        except BrokenPipeError:
            return
        except Exception:
            if getattr(self.server, "verbose", False):
                self.log_error("Falha ao atender DELETE")
            self._send_error(
                "Ocorreu um erro inesperado. Tente novamente.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _handle_analyze(self) -> None:
        payload = self._read_json()
        with tempfile.TemporaryDirectory(prefix="analise-contratos-") as temp_name:
            directory = Path(temp_name)
            template = self._save_upload(
                payload.get("template"), directory, {".docx"}, "o modelo Word"
            )
            spreadsheet = self._save_upload(
                payload.get("spreadsheet"),
                directory,
                {".xlsx", ".csv"},
                "a planilha",
            )
            result = analyze_inputs(template, spreadsheet, payload.get("sheet_name"))
            self._send_json(result)

    def _handle_generate(self) -> None:
        payload = self._read_json()
        with tempfile.TemporaryDirectory(prefix="lote-contratos-") as temp_name:
            directory = Path(temp_name)
            template = self._save_upload(
                payload.get("template"), directory, {".docx"}, "o modelo Word"
            )
            spreadsheet = self._save_upload(
                payload.get("spreadsheet"),
                directory,
                {".xlsx", ".csv"},
                "a planilha",
            )
            zip_path = directory / "contratos_gerados.zip"
            clicksign_options = dict(payload.get("clicksign") or {})
            clicksign_options["access_token"] = (
                os.getenv("CLICKSIGN_ACCESS_TOKEN", "").strip()
                or str(clicksign_options.get("access_token", "")).strip()
            )
            summary = generate_contracts_zip(
                template,
                spreadsheet,
                payload.get("mapping") or {},
                zip_path,
                sheet_name=payload.get("sheet_name"),
                output_format=payload.get("output_format", "pdf"),
                filename_variable=payload.get(
                    "filename_variable", "nome_responsavel"
                ),
                clicksign=clicksign_options,
                clicksign_log_path=DATA_DIR / "clicksign_envios.csv",
            )
            body = zip_path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header(
            "Content-Disposition", 'attachment; filename="contratos_gerados.zip"'
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Generated", str(summary["generated"]))
        self.send_header("X-Errors", str(summary["errors"]))
        self.send_header("X-Pdf-Fallbacks", str(summary["pdf_fallbacks"]))
        self.send_header("X-Clicksign-Sent", str(summary["sent"]))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interface visual do SignTime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ContractHandler)
    server.verbose = args.verbose
    url = f"http://{args.host}:{args.port}"
    print(f"SignTime aberto em {url}")
    print("Mantenha esta janela aberta enquanto estiver usando o sistema.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSistema encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
