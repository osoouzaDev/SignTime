"""Teste de integração descartável da autenticação com o PostgreSQL."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from sqlalchemy import text


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from auth.database import session_scope  # noqa: E402
from auth.service import (  # noqa: E402
    InvalidCredentials,
    authenticate_user,
    create_user,
    find_active_session,
    issue_session,
    revoke_session,
    validate_csrf,
)


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    username = f"teste_auth_{suffix}"
    password = f"SignTime-Teste-{suffix}!"
    user = None

    try:
        user = create_user(
            username=username,
            password=password,
            full_name="Teste temporário SignTime",
            role="user",
        )

        try:
            authenticate_user(username, "senha-incorreta")
        except InvalidCredentials:
            pass
        else:
            raise AssertionError("Uma senha incorreta foi aceita.")

        with session_scope() as database:
            attempts = database.execute(
                text(
                    "select failed_login_attempts from private.users where id = :id"
                ),
                {"id": user.id},
            ).scalar_one()
        if attempts != 1:
            raise AssertionError("A tentativa incorreta não foi persistida.")

        authenticated = authenticate_user(username, password)
        if authenticated.id != user.id:
            raise AssertionError("O usuário autenticado não corresponde ao criado.")

        issued = issue_session(user.id)
        active = find_active_session(issued.token)
        if active is None or active.user.id != user.id:
            raise AssertionError("A sessão criada não pôde ser recuperada.")
        if not validate_csrf(active, issued.csrf_token):
            raise AssertionError("A proteção CSRF não validou o token correto.")

        revoke_session(issued.token)
        if find_active_session(issued.token) is not None:
            raise AssertionError("A sessão continuou ativa após o logout.")

        print("Autenticação validada no banco com sucesso.")
    finally:
        if user is not None:
            with session_scope() as database:
                database.execute(
                    text("delete from private.users where id = :id"),
                    {"id": user.id},
                )


if __name__ == "__main__":
    main()
