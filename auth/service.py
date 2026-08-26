"""Regras de usuários, login e sessões persistidas no PostgreSQL."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .database import session_scope
from .security import (
    hash_password,
    new_token,
    password_needs_rehash,
    token_hash,
    token_matches,
    verify_password,
)


class AuthError(RuntimeError):
    """Erro controlado do fluxo de autenticação."""


class InvalidCredentials(AuthError):
    pass


class AccountLocked(AuthError):
    pass


class UserAlreadyExists(AuthError):
    pass


@dataclass(frozen=True)
class UserIdentity:
    id: str
    username: str
    email: str | None
    full_name: str
    role: str


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class ActiveSession:
    id: str
    token_hash: str
    csrf_token_hash: str
    expires_at: datetime
    user: UserIdentity


DUMMY_PASSWORD_HASH = hash_password("SignTime-dummy-password-only")


def _int_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def session_duration_hours() -> int:
    return _int_setting("SESSION_DURATION_HOURS", 8, 1, 168)


def session_duration_seconds() -> int:
    return session_duration_hours() * 60 * 60


def create_user(
    *,
    username: str,
    password: str,
    full_name: str,
    email: str | None = None,
    role: str = "user",
) -> UserIdentity:
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
        raise ValueError("O perfil deve ser admin ou user.")

    password_hash = hash_password(password)
    try:
        with session_scope() as database:
            row = database.execute(
                text(
                    """
                    insert into private.users
                      (username, email, full_name, password_hash, role)
                    values
                      (:username, :email, :full_name, :password_hash, :role)
                    returning id, username, email, full_name, role
                    """
                ),
                {
                    "username": username,
                    "email": email,
                    "full_name": full_name,
                    "password_hash": password_hash,
                    "role": role,
                },
            ).mappings().one()
    except IntegrityError as exc:
        raise UserAlreadyExists("Usuário ou e-mail já cadastrado.") from exc

    return UserIdentity(
        id=str(row["id"]),
        username=row["username"],
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
    )


def authenticate_user(login: str, password: str) -> UserIdentity:
    normalized_login = login.strip()
    if not normalized_login or not password:
        raise InvalidCredentials("Usuário ou senha inválidos.")

    now = datetime.now(timezone.utc)
    max_attempts = _int_setting("LOGIN_MAX_ATTEMPTS", 5, 3, 20)
    lock_minutes = _int_setting("LOGIN_LOCK_MINUTES", 15, 1, 120)
    authenticated_user: UserIdentity | None = None
    authentication_error: AuthError | None = None

    with session_scope() as database:
        row = database.execute(
            text(
                """
                select
                  id, username, email, full_name, role, password_hash,
                  is_active, failed_login_attempts, locked_until
                from private.users
                where lower(username) = lower(:login)
                limit 1
                for update
                """
            ),
            {"login": normalized_login},
        ).mappings().first()

        if row is None:
            verify_password(DUMMY_PASSWORD_HASH, password)
            authentication_error = InvalidCredentials("Usuário ou senha inválidos.")
        elif not row["is_active"]:
            verify_password(row["password_hash"], password)
            authentication_error = InvalidCredentials("Usuário ou senha inválidos.")
        elif row["locked_until"] and row["locked_until"] > now:
            authentication_error = AccountLocked("Acesso temporariamente bloqueado.")
        elif not verify_password(row["password_hash"], password):
            previous_attempts = (
                0
                if row["locked_until"] and row["locked_until"] <= now
                else int(row["failed_login_attempts"])
            )
            attempts = previous_attempts + 1
            new_lock = (
                now + timedelta(minutes=lock_minutes)
                if attempts >= max_attempts
                else None
            )
            database.execute(
                text(
                    """
                    update private.users
                    set failed_login_attempts = :attempts,
                        locked_until = :locked_until
                    where id = :user_id
                    """
                ),
                {
                    "attempts": attempts,
                    "locked_until": new_lock,
                    "user_id": row["id"],
                },
            )
            authentication_error = InvalidCredentials("Usuário ou senha inválidos.")
        else:
            replacement_hash = (
                hash_password(password)
                if password_needs_rehash(row["password_hash"])
                else row["password_hash"]
            )
            database.execute(
                text(
                    """
                    update private.users
                    set failed_login_attempts = 0,
                        locked_until = null,
                        last_login_at = :now,
                        password_hash = :password_hash
                    where id = :user_id
                    """
                ),
                {
                    "now": now,
                    "password_hash": replacement_hash,
                    "user_id": row["id"],
                },
            )
            authenticated_user = UserIdentity(
                id=str(row["id"]),
                username=row["username"],
                email=row["email"],
                full_name=row["full_name"],
                role=row["role"],
            )

    # Levantar a exceção depois do commit preserva a contagem e o bloqueio.
    if authentication_error is not None:
        raise authentication_error
    if authenticated_user is None:
        raise InvalidCredentials("Usuário ou senha inválidos.")
    return authenticated_user


def issue_session(user_id: str) -> IssuedSession:
    session_token = new_token()
    csrf_token = new_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=session_duration_hours())
    with session_scope() as database:
        database.execute(
            text(
                """
                insert into private.user_sessions
                  (user_id, token_hash, csrf_token_hash, expires_at)
                values
                  (:user_id, :token_hash, :csrf_token_hash, :expires_at)
                """
            ),
            {
                "user_id": user_id,
                "token_hash": token_hash(session_token),
                "csrf_token_hash": token_hash(csrf_token),
                "expires_at": expires_at,
            },
        )
    return IssuedSession(session_token, csrf_token, expires_at)


def find_active_session(session_token: str) -> ActiveSession | None:
    if not session_token:
        return None
    session_token_hash = token_hash(session_token)
    with session_scope() as database:
        row = database.execute(
            text(
                """
                select
                  s.id as session_id,
                  s.token_hash,
                  s.csrf_token_hash,
                  s.expires_at,
                  u.id as user_id,
                  u.username,
                  u.email,
                  u.full_name,
                  u.role
                from private.user_sessions s
                join private.users u on u.id = s.user_id
                where s.token_hash = :token_hash
                  and s.revoked_at is null
                  and s.expires_at > now()
                  and u.is_active = true
                limit 1
                """
            ),
            {"token_hash": session_token_hash},
        ).mappings().first()
        if row is None:
            return None
        database.execute(
            text(
                """
                update private.user_sessions
                set last_seen_at = now()
                where id = :session_id
                  and last_seen_at < now() - interval '5 minutes'
                """
            ),
            {"session_id": row["session_id"]},
        )

    return ActiveSession(
        id=str(row["session_id"]),
        token_hash=row["token_hash"],
        csrf_token_hash=row["csrf_token_hash"],
        expires_at=row["expires_at"],
        user=UserIdentity(
            id=str(row["user_id"]),
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            role=row["role"],
        ),
    )


def validate_csrf(active_session: ActiveSession, csrf_token: str) -> bool:
    return bool(csrf_token) and token_matches(
        active_session.csrf_token_hash, csrf_token
    )


def revoke_session(session_token: str) -> None:
    if not session_token:
        return
    with session_scope() as database:
        database.execute(
            text(
                """
                update private.user_sessions
                set revoked_at = now()
                where token_hash = :token_hash and revoked_at is null
                """
            ),
            {"token_hash": token_hash(session_token)},
        )


def cleanup_expired_sessions() -> int:
    with session_scope() as database:
        result = database.execute(
            text(
                """
                delete from private.user_sessions
                where expires_at < now() - interval '7 days'
                   or revoked_at < now() - interval '7 days'
                """
            )
        )
        return int(result.rowcount or 0)
