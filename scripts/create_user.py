"""Cria usuários do SignTime com senha Argon2id."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from auth.service import UserAlreadyExists, create_user  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Criar usuário do SignTime")
    parser.add_argument("--username", help="Login do usuário")
    parser.add_argument("--full-name", help="Nome completo")
    parser.add_argument("--email", help="E-mail opcional")
    parser.add_argument("--role", choices=("admin", "user"), default="user")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    username = args.username or input("Usuário: ").strip()
    full_name = args.full_name or input("Nome completo: ").strip()
    email = args.email if args.email is not None else input("E-mail (opcional): ").strip()
    password = getpass.getpass("Senha: ")
    confirmation = getpass.getpass("Confirme a senha: ")
    if password != confirmation:
        print("As senhas não coincidem.")
        return 1
    try:
        user = create_user(
            username=username,
            password=password,
            full_name=full_name,
            email=email or None,
            role=args.role,
        )
    except (ValueError, UserAlreadyExists) as exc:
        print(str(exc))
        return 1
    print(f"Usuário {user.username} criado com o perfil {user.role}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
