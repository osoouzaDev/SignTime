"""Operações de administração de usuários do SignTime."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .database import session_scope
from .security import hash_password
from .service import UserAlreadyExists, create_user


class UserManagementError(RuntimeError):
    """Erro controlado exibido no painel administrativo."""


class ManagedUserNotFound(UserManagementError):
    pass


class ProtectedAdministrator(UserManagementError):
    pass


@dataclass(frozen=True)
class ManagedUser:
    id: str
    username: str
    email: str | None
    full_name: str
    role: str
    is_active: bool
    failed_login_attempts: int
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        payload = asdict(self)
        for key in ("locked_until", "last_login_at", "created_at", "updated_at"):
            value = payload[key]
            payload[key] = value.isoformat() if value else None
        return payload


def _valid_id(user_id: str) -> str:
    try:
        return str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ManagedUserNotFound("Usuário não encontrado.") from exc


def _normalize_fields(
    *, username: str, full_name: str, email: str | None, role: str
) -> tuple[str, str, str | None, str]:
    username = username.strip()
    full_name = full_name.strip()
    email = email.strip() if email else None
    role = role.strip().lower()
    if not username or len(username) > 80:
        raise ValueError("Informe um usuário com até 80 caracteres.")
    if not full_name or len(full_name) > 160:
        raise ValueError("Informe o nome completo com até 160 caracteres.")
    if email and len(email) > 320:
        raise ValueError("O e-mail excede 320 caracteres.")
    if role not in {"admin", "user"}:
        raise ValueError("O perfil deve ser administrador ou usuário.")
    return username, full_name, email, role


def _from_row(row) -> ManagedUser:
    return ManagedUser(
        id=str(row["id"]),
        username=row["username"],
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        failed_login_attempts=int(row["failed_login_attempts"]),
        locked_until=row["locked_until"],
        last_login_at=row["last_login_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _select_columns() -> str:
    return """
      id, username, email, full_name, role, is_active,
      failed_login_attempts, locked_until, last_login_at,
      created_at, updated_at
    """


def list_managed_users() -> list[ManagedUser]:
    with session_scope() as database:
        rows = database.execute(
            text(
                f"""
                select {_select_columns()}
                from private.users
                order by is_active desc, role asc, lower(full_name), lower(username)
                """
            )
        ).mappings().all()
    return [_from_row(row) for row in rows]


def get_managed_user(user_id: str) -> ManagedUser:
    valid_id = _valid_id(user_id)
    with session_scope() as database:
        row = database.execute(
            text(
                f"""
                select {_select_columns()}
                from private.users
                where id = :user_id
                """
            ),
            {"user_id": valid_id},
        ).mappings().first()
    if row is None:
        raise ManagedUserNotFound("Usuário não encontrado.")
    return _from_row(row)


def create_managed_user(
    *,
    username: str,
    password: str,
    full_name: str,
    email: str | None = None,
    role: str = "user",
) -> ManagedUser:
    user = create_user(
        username=username,
        password=password,
        full_name=full_name,
        email=email,
        role=role,
    )
    return get_managed_user(user.id)


def _active_admin_count(database) -> int:
    return int(
        database.execute(
            text(
                """
                select count(*)
                from private.users
                where role = 'admin' and is_active = true
                """
            )
        ).scalar_one()
    )


def update_managed_user(
    *,
    user_id: str,
    actor_user_id: str,
    username: str,
    full_name: str,
    email: str | None,
    role: str,
    password: str | None = None,
) -> ManagedUser:
    valid_id = _valid_id(user_id)
    actor_id = _valid_id(actor_user_id)
    username, full_name, email, role = _normalize_fields(
        username=username,
        full_name=full_name,
        email=email,
        role=role,
    )
    password_hash = hash_password(password) if password else None

    try:
        with session_scope() as database:
            current = database.execute(
                text(
                    """
                    select id, role, is_active
                    from private.users
                    where id = :user_id
                    for update
                    """
                ),
                {"user_id": valid_id},
            ).mappings().first()
            if current is None:
                raise ManagedUserNotFound("Usuário não encontrado.")
            if valid_id == actor_id and role != "admin":
                raise ProtectedAdministrator(
                    "Você não pode remover o próprio perfil de administrador."
                )
            if (
                current["role"] == "admin"
                and current["is_active"]
                and role != "admin"
                and _active_admin_count(database) <= 1
            ):
                raise ProtectedAdministrator(
                    "O SignTime precisa manter pelo menos um administrador ativo."
                )

            row = database.execute(
                text(
                    f"""
                    update private.users
                    set username = :username,
                        full_name = :full_name,
                        email = :email,
                        role = :role,
                        password_hash = coalesce(:password_hash, password_hash),
                        password_changed_at = case
                          when :password_hash is null then password_changed_at
                          else now()
                        end,
                        failed_login_attempts = case
                          when :password_hash is null then failed_login_attempts
                          else 0
                        end,
                        locked_until = case
                          when :password_hash is null then locked_until
                          else null
                        end
                    where id = :user_id
                    returning {_select_columns()}
                    """
                ),
                {
                    "username": username,
                    "full_name": full_name,
                    "email": email,
                    "role": role,
                    "password_hash": password_hash,
                    "user_id": valid_id,
                },
            ).mappings().one()
            if password_hash:
                database.execute(
                    text(
                        """
                        update private.user_sessions
                        set revoked_at = now()
                        where user_id = :user_id and revoked_at is null
                        """
                    ),
                    {"user_id": valid_id},
                )
    except IntegrityError as exc:
        raise UserAlreadyExists("Usuário ou e-mail já cadastrado.") from exc
    return _from_row(row)


def set_managed_user_active(
    *, user_id: str, actor_user_id: str, is_active: bool
) -> ManagedUser:
    valid_id = _valid_id(user_id)
    actor_id = _valid_id(actor_user_id)
    if valid_id == actor_id and not is_active:
        raise ProtectedAdministrator("Você não pode desativar a própria conta.")

    with session_scope() as database:
        current = database.execute(
            text(
                """
                select id, role, is_active
                from private.users
                where id = :user_id
                for update
                """
            ),
            {"user_id": valid_id},
        ).mappings().first()
        if current is None:
            raise ManagedUserNotFound("Usuário não encontrado.")
        if (
            not is_active
            and current["role"] == "admin"
            and current["is_active"]
            and _active_admin_count(database) <= 1
        ):
            raise ProtectedAdministrator(
                "O SignTime precisa manter pelo menos um administrador ativo."
            )
        row = database.execute(
            text(
                f"""
                update private.users
                set is_active = :is_active,
                    failed_login_attempts = case when :is_active then 0 else failed_login_attempts end,
                    locked_until = case when :is_active then null else locked_until end
                where id = :user_id
                returning {_select_columns()}
                """
            ),
            {"is_active": bool(is_active), "user_id": valid_id},
        ).mappings().one()
        if not is_active:
            database.execute(
                text(
                    """
                    update private.user_sessions
                    set revoked_at = now()
                    where user_id = :user_id and revoked_at is null
                    """
                ),
                {"user_id": valid_id},
            )
    return _from_row(row)


def delete_managed_user(*, user_id: str, actor_user_id: str) -> None:
    valid_id = _valid_id(user_id)
    actor_id = _valid_id(actor_user_id)
    if valid_id == actor_id:
        raise ProtectedAdministrator("Você não pode excluir a própria conta.")

    with session_scope() as database:
        current = database.execute(
            text(
                """
                select id, role, is_active
                from private.users
                where id = :user_id
                for update
                """
            ),
            {"user_id": valid_id},
        ).mappings().first()
        if current is None:
            raise ManagedUserNotFound("Usuário não encontrado.")
        if (
            current["role"] == "admin"
            and current["is_active"]
            and _active_admin_count(database) <= 1
        ):
            raise ProtectedAdministrator(
                "O SignTime precisa manter pelo menos um administrador ativo."
            )
        database.execute(
            text("delete from private.users where id = :user_id"),
            {"user_id": valid_id},
        )
