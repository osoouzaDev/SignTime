"""Conexão segura e reutilizável com o PostgreSQL do SignTime."""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


PROJECT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DIR / ".env", override=False)


class DatabaseConfigurationError(RuntimeError):
    """Indica que a conexão do banco ainda não foi configurada."""


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise DatabaseConfigurationError(
            "A variável DATABASE_URL não foi configurada."
        )
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Cria um pool pequeno, adequado ao backend web do SignTime."""

    sslmode = os.getenv("DATABASE_SSLMODE", "require").strip() or "require"
    return create_engine(
        _database_url(),
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        connect_args={"sslmode": sslmode},
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Entrega uma sessão e garante commit ou rollback automático."""

    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> bool:
    """Valida a conexão sem revelar host, usuário ou senha."""

    with get_engine().connect() as connection:
        return connection.execute(text("select 1")).scalar_one() == 1
