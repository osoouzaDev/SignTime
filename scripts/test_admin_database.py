"""Teste descartável das operações administrativas no PostgreSQL."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from sqlalchemy import text


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from auth.admin_service import (  # noqa: E402
    ManagedUserNotFound,
    ProtectedAdministrator,
    create_managed_user,
    delete_managed_user,
    get_managed_user,
    list_managed_users,
    set_managed_user_active,
    update_managed_user,
)
from auth.database import session_scope  # noqa: E402
from auth.service import (  # noqa: E402
    InvalidCredentials,
    authenticate_user,
    create_user,
    find_active_session,
    issue_session,
)


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    admin = None
    managed = None
    try:
        admin = create_user(
            username=f"admin_teste_{suffix}",
            password=f"Admin-Teste-{suffix}!",
            full_name="Administrador temporário",
            role="admin",
        )
        managed = create_managed_user(
            username=f"usuario_teste_{suffix}",
            password=f"Usuario-Teste-{suffix}!",
            full_name="Usuário temporário",
            email=f"teste-{suffix}@example.invalid",
            role="user",
        )

        if managed.id not in {user.id for user in list_managed_users()}:
            raise AssertionError("O usuário criado não apareceu na listagem.")

        updated_password = f"Nova-Senha-{suffix}!"
        managed = update_managed_user(
            user_id=managed.id,
            actor_user_id=admin.id,
            username=f"usuario_editado_{suffix}",
            full_name="Usuário editado",
            email=None,
            role="user",
            password=updated_password,
        )
        if managed.full_name != "Usuário editado" or managed.email is not None:
            raise AssertionError("Os dados editados não foram persistidos.")
        authenticate_user(managed.username, updated_password)

        issued = issue_session(managed.id)
        if find_active_session(issued.token) is None:
            raise AssertionError("A sessão de teste não foi criada.")
        managed = set_managed_user_active(
            user_id=managed.id,
            actor_user_id=admin.id,
            is_active=False,
        )
        if managed.is_active or find_active_session(issued.token) is not None:
            raise AssertionError("A desativação não revogou o acesso.")
        try:
            authenticate_user(managed.username, updated_password)
        except InvalidCredentials:
            pass
        else:
            raise AssertionError("Um usuário desativado conseguiu entrar.")

        managed = set_managed_user_active(
            user_id=managed.id,
            actor_user_id=admin.id,
            is_active=True,
        )
        if not managed.is_active:
            raise AssertionError("A reativação do usuário falhou.")
        authenticate_user(managed.username, updated_password)

        for protected_action in (
            lambda: set_managed_user_active(
                user_id=admin.id,
                actor_user_id=admin.id,
                is_active=False,
            ),
            lambda: delete_managed_user(
                user_id=admin.id,
                actor_user_id=admin.id,
            ),
        ):
            try:
                protected_action()
            except ProtectedAdministrator:
                pass
            else:
                raise AssertionError("A proteção da própria conta não funcionou.")

        delete_managed_user(user_id=managed.id, actor_user_id=admin.id)
        try:
            get_managed_user(managed.id)
        except ManagedUserNotFound:
            pass
        else:
            raise AssertionError("O usuário continuou no banco após a exclusão.")
        managed = None

        print("Cadastro, listagem, edição, status e exclusão validados no banco.")
    finally:
        with session_scope() as database:
            if managed is not None:
                database.execute(
                    text("delete from private.users where id = :id"),
                    {"id": managed.id},
                )
            if admin is not None:
                database.execute(
                    text("delete from private.users where id = :id"),
                    {"id": admin.id},
                )


if __name__ == "__main__":
    main()
