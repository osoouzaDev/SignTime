"""Confere a conexão e a estrutura de autenticação sem exibir segredos."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from auth.database import get_engine  # noqa: E402


def main() -> None:
    with get_engine().connect() as connection:
        columns = connection.execute(
            text(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'private' and table_name = 'users'
                order by ordinal_position
                """
            )
        ).scalars().all()
        indexes = connection.execute(
            text(
                """
                select indexname
                from pg_indexes
                where schemaname = 'private' and tablename = 'users'
                order by indexname
                """
            )
        ).scalars().all()
        row_count = connection.execute(
            text("select count(*) from private.users")
        ).scalar_one()
        migration_count = connection.execute(
            text(
                """
                select count(*)
                from supabase_migrations.schema_migrations
                where version = '20260826010000'
                """
            )
        ).scalar_one()
        anon_access, authenticated_access = connection.execute(
            text(
                """
                select
                  has_schema_privilege('anon', 'private', 'usage'),
                  has_schema_privilege('authenticated', 'private', 'usage')
                """
            )
        ).one()

    print(
        {
            "database": "ok",
            "table": "private.users",
            "columns": columns,
            "indexes": indexes,
            "rows": row_count,
            "migration_registered": bool(migration_count),
            "anon_schema_access": anon_access,
            "authenticated_schema_access": authenticated_access,
        }
    )


if __name__ == "__main__":
    main()
