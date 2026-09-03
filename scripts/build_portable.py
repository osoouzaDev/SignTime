"""Gera um SignTime.exe portátil ligado somente ao backend HTTPS."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


PROJECT_DIR = Path(__file__).resolve().parents[1]


def validate_api_url(value: str) -> str:
    url = value.strip().rstrip("/")
    parsed = urlparse(url)
    is_local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_local):
        raise ValueError("Use uma URL HTTPS do backend publicado.")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("A URL do backend é inválida.")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", required=True, help="URL HTTPS do backend publicado")
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=PROJECT_DIR / "dist",
        help="Pasta que receberá o executável",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=PROJECT_DIR / "build" / "portable",
        help="Pasta temporária da compilação",
    )
    args = parser.parse_args()

    api_url = validate_api_url(args.api_url)
    dist_dir = args.dist_dir.resolve()
    work_dir = args.work_dir.resolve()
    spec_dir = work_dir / "spec"
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="signtime-build-") as temp_name:
        runtime_hook = Path(temp_name) / "signtime_remote_config.py"
        runtime_hook.write_text(
            "import os\n"
            f"os.environ['SIGNTIME_AUTH_API_URL'] = {json.dumps(api_url)}\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--console",
            "--name",
            "SignTime",
            "--icon",
            str(PROJECT_DIR / "assets" / "brand" / "signtime.ico"),
            "--add-data",
            f"{PROJECT_DIR / 'web'}{os.pathsep}web",
            "--runtime-hook",
            str(runtime_hook),
            "--distpath",
            str(dist_dir),
            "--workpath",
            str(work_dir),
            "--specpath",
            str(spec_dir),
            str(PROJECT_DIR / "app.py"),
        ]
        subprocess.run(command, cwd=PROJECT_DIR, check=True)

    executable = dist_dir / ("SignTime.exe" if os.name == "nt" else "SignTime")
    if not executable.is_file():
        raise RuntimeError("O executável não foi encontrado após a compilação.")
    print(f"Executável portátil criado em: {executable}")
    print("A senha do PostgreSQL não foi incluída no arquivo.")


if __name__ == "__main__":
    main()
