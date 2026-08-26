"""Teste ponta a ponta descartável do login HTTP do SignTime."""

from __future__ import annotations

import http.cookiejar
import json
import sys
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from sqlalchemy import text


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app import CSRF_COOKIE, ContractHandler, ThreadingHTTPServer  # noqa: E402
from auth.database import session_scope  # noqa: E402
from auth.service import create_user  # noqa: E402


def expect_http_error(opener, request, status: int) -> None:
    try:
        opener.open(request, timeout=10)
    except urllib.error.HTTPError as exc:
        if exc.code != status:
            raise AssertionError(f"Esperado HTTP {status}, recebido {exc.code}.") from exc
    else:
        raise AssertionError(f"A requisição deveria retornar HTTP {status}.")


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    username = f"teste_http_{suffix}"
    password = f"SignTime-HTTP-{suffix}!"
    user = create_user(
        username=username,
        password=password,
        full_name="Teste HTTP SignTime",
        role="user",
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
    server.verbose = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    try:
        with opener.open(f"{base_url}/", timeout=10) as response:
            if response.geturl() != f"{base_url}/login":
                raise AssertionError("A área interna não redirecionou para o login.")
            if b'id="login-form"' not in response.read():
                raise AssertionError("A tela de login não foi carregada.")

        expect_http_error(opener, f"{base_url}/api/config", 401)

        login_body = json.dumps(
            {"username": username, "password": password}
        ).encode("utf-8")
        login_request = urllib.request.Request(
            f"{base_url}/api/auth/login",
            data=login_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with opener.open(login_request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("authenticated"):
                raise AssertionError("O endpoint não confirmou o login.")

        with opener.open(f"{base_url}/api/auth/session", timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if payload["user"]["username"] != username:
                raise AssertionError("A sessão retornou outro usuário.")

        csrf_token = next(
            (cookie.value for cookie in cookie_jar if cookie.name == CSRF_COOKIE),
            "",
        )
        if not csrf_token:
            raise AssertionError("O cookie de proteção CSRF não foi criado.")
        logout_request = urllib.request.Request(
            f"{base_url}/api/auth/logout",
            data=b"{}",
            headers={"X-CSRF-Token": csrf_token},
            method="POST",
        )
        with opener.open(logout_request, timeout=10) as response:
            if response.status != 200:
                raise AssertionError("O logout não foi concluído.")

        expect_http_error(opener, f"{base_url}/api/auth/session", 401)
        print("Login HTTP, sessão, proteção de rotas e logout validados.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        with session_scope() as database:
            database.execute(
                text("delete from private.users where id = :id"),
                {"id": user.id},
            )


if __name__ == "__main__":
    main()
