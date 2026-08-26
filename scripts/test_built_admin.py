"""Valida o painel administrativo dentro do executável compilado."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.request
import uuid
from pathlib import Path

from sqlalchemy import text


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from auth.database import session_scope  # noqa: E402
from auth.service import create_user  # noqa: E402


def request_json(opener, url, *, method="GET", payload=None, csrf=""):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with opener.open(request, timeout=25) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8769")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    suffix = uuid.uuid4().hex[:12]
    password = f"Admin-EXE-{suffix}!"
    admin = create_user(
        username=f"admin_exe_{suffix}",
        password=password,
        full_name="Administrador executável",
        role="admin",
    )
    managed_id = None
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    try:
        status, payload = request_json(
            opener,
            f"{base_url}/api/auth/login",
            method="POST",
            payload={"username": admin.username, "password": password},
        )
        if status != 200 or not payload.get("authenticated"):
            raise AssertionError("O login administrativo do executável falhou.")
        csrf = next(
            (cookie.value for cookie in jar if cookie.name == "signtime_csrf"),
            "",
        )
        if not csrf:
            raise AssertionError("O executável não emitiu o token CSRF.")

        with opener.open(f"{base_url}/admin", timeout=20) as response:
            if b'id="users-table-body"' not in response.read():
                raise AssertionError("O executável não incluiu o painel administrativo.")

        status, payload = request_json(opener, f"{base_url}/api/admin/users")
        if status != 200 or not isinstance(payload.get("users"), list):
            raise AssertionError("A listagem do executável falhou.")

        status, payload = request_json(
            opener,
            f"{base_url}/api/admin/users",
            method="POST",
            csrf=csrf,
            payload={
                "username": f"usuario_exe_{suffix}",
                "full_name": "Usuário do executável",
                "email": None,
                "role": "user",
                "password": f"Usuario-EXE-{suffix}!",
            },
        )
        if status != 201:
            raise AssertionError("O cadastro no executável falhou.")
        managed_id = payload["user"]["id"]

        status, payload = request_json(
            opener,
            f"{base_url}/api/admin/users/{managed_id}/status",
            method="PATCH",
            csrf=csrf,
            payload={"is_active": False},
        )
        if status != 200 or payload["user"]["is_active"]:
            raise AssertionError("A desativação no executável falhou.")

        status, payload = request_json(
            opener,
            f"{base_url}/api/admin/users/{managed_id}",
            method="DELETE",
            csrf=csrf,
        )
        if status != 200 or not payload.get("deleted"):
            raise AssertionError("A exclusão no executável falhou.")
        managed_id = None
        print("Executável validado com o painel administrativo completo.")
    finally:
        with session_scope() as database:
            for user_id in (managed_id, admin.id):
                if user_id:
                    database.execute(
                        text("delete from private.users where id = :id"),
                        {"id": user_id},
                    )


if __name__ == "__main__":
    main()
