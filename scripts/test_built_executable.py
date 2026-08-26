"""Valida o executável compilado contra o banco e os endpoints de acesso."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from sqlalchemy import text


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from auth.database import session_scope  # noqa: E402
from auth.service import create_user  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8767")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    suffix = uuid.uuid4().hex[:12]
    username = f"teste_exe_{suffix}"
    password = f"SignTime-EXE-{suffix}!"
    user = create_user(
        username=username,
        password=password,
        full_name="Teste executável SignTime",
        role="user",
    )

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    try:
        login_request = urllib.request.Request(
            f"{base_url}/api/auth/login",
            data=json.dumps(
                {"username": username, "password": password}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with opener.open(login_request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("authenticated"):
                raise AssertionError("O executável não confirmou o login.")

        with opener.open(f"{base_url}/api/auth/session", timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if payload["user"]["username"] != username:
                raise AssertionError("O executável retornou outro usuário.")

        csrf_token = next(
            (
                cookie.value
                for cookie in cookie_jar
                if cookie.name == "signtime_csrf"
            ),
            "",
        )
        if not csrf_token:
            raise AssertionError("O executável não criou a proteção CSRF.")

        logout_request = urllib.request.Request(
            f"{base_url}/api/auth/logout",
            data=b"{}",
            headers={"X-CSRF-Token": csrf_token},
            method="POST",
        )
        with opener.open(logout_request, timeout=15) as response:
            if response.status != 200:
                raise AssertionError("O logout do executável falhou.")

        try:
            opener.open(f"{base_url}/api/auth/session", timeout=15)
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise
        else:
            raise AssertionError("A sessão do executável continuou ativa.")

        print("Executável validado com login, sessão e logout.")
    finally:
        with session_scope() as database:
            database.execute(
                text("delete from private.users where id = :id"),
                {"id": user.id},
            )


if __name__ == "__main__":
    main()
