"""Teste ponta a ponta descartável das APIs e permissões administrativas."""

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


def new_opener() -> tuple[urllib.request.OpenerDirector, http.cookiejar.CookieJar]:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def json_request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    csrf_token: str = "",
) -> tuple[int, dict]:
    headers = {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def login(opener, jar, base_url: str, username: str, password: str) -> str:
    status, payload = json_request(
        opener,
        f"{base_url}/api/auth/login",
        method="POST",
        payload={"username": username, "password": password},
    )
    if status != 200 or not payload.get("authenticated"):
        raise AssertionError("Não foi possível autenticar o usuário de teste.")
    token = next((cookie.value for cookie in jar if cookie.name == CSRF_COOKIE), "")
    if not token:
        raise AssertionError("O cookie CSRF não foi recebido.")
    return token


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    admin = regular = managed_id = None
    admin_password = f"Admin-HTTP-{suffix}!"
    regular_password = f"Regular-HTTP-{suffix}!"

    admin = create_user(
        username=f"admin_http_{suffix}",
        password=admin_password,
        full_name="Administrador HTTP",
        role="admin",
    )
    regular = create_user(
        username=f"regular_http_{suffix}",
        password=regular_password,
        full_name="Usuário HTTP",
        role="user",
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
    server.verbose = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        regular_opener, regular_jar = new_opener()
        login(
            regular_opener,
            regular_jar,
            base_url,
            regular.username,
            regular_password,
        )
        status, _ = json_request(regular_opener, f"{base_url}/api/admin/users")
        if status != 403:
            raise AssertionError("Um usuário comum acessou a API administrativa.")

        admin_opener, admin_jar = new_opener()
        csrf_token = login(
            admin_opener,
            admin_jar,
            base_url,
            admin.username,
            admin_password,
        )
        with admin_opener.open(f"{base_url}/admin", timeout=15) as response:
            if b'id="users-table-body"' not in response.read():
                raise AssertionError("O painel administrativo não foi servido.")

        status, payload = json_request(
            admin_opener,
            f"{base_url}/api/admin/users",
        )
        if status != 200 or not isinstance(payload.get("users"), list):
            raise AssertionError("A listagem administrativa falhou.")

        status, payload = json_request(
            admin_opener,
            f"{base_url}/api/admin/users",
            method="POST",
            csrf_token=csrf_token,
            payload={
                "username": f"gerenciado_http_{suffix}",
                "full_name": "Gerenciado HTTP",
                "email": None,
                "role": "user",
                "password": f"Gerenciado-HTTP-{suffix}!",
            },
        )
        if status != 201:
            raise AssertionError(f"O cadastro via API falhou: {payload}")
        managed_id = payload["user"]["id"]

        status, payload = json_request(
            admin_opener,
            f"{base_url}/api/admin/users/{managed_id}",
            method="PATCH",
            csrf_token=csrf_token,
            payload={
                "username": f"editado_http_{suffix}",
                "full_name": "Gerenciado editado",
                "email": f"editado-{suffix}@example.invalid",
                "role": "user",
                "password": "",
            },
        )
        if status != 200 or payload["user"]["full_name"] != "Gerenciado editado":
            raise AssertionError("A edição via API falhou.")

        for active in (False, True):
            status, payload = json_request(
                admin_opener,
                f"{base_url}/api/admin/users/{managed_id}/status",
                method="PATCH",
                csrf_token=csrf_token,
                payload={"is_active": active},
            )
            if status != 200 or payload["user"]["is_active"] is not active:
                raise AssertionError("A alteração de status via API falhou.")

        status, _ = json_request(
            admin_opener,
            f"{base_url}/api/admin/users/{admin.id}/status",
            method="PATCH",
            csrf_token=csrf_token,
            payload={"is_active": False},
        )
        if status != 409:
            raise AssertionError("A API permitiu desativar a própria conta.")

        status, payload = json_request(
            admin_opener,
            f"{base_url}/api/admin/users/{managed_id}",
            method="DELETE",
            csrf_token=csrf_token,
        )
        if status != 200 or not payload.get("deleted"):
            raise AssertionError("A exclusão via API falhou.")
        managed_id = None

        print("Painel, permissões e APIs administrativas validados.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        with session_scope() as database:
            for user_id in (managed_id, regular.id if regular else None, admin.id if admin else None):
                if user_id:
                    database.execute(
                        text("delete from private.users where id = :id"),
                        {"id": user_id},
                    )


if __name__ == "__main__":
    main()
