r"""CLI administrativo do FIAS-ED Web.

Uso interativo (terminal, TTY):
    python -m app.cli create-admin --username U --display-name N
    (a senha é pedida duas vezes via prompt oculto, sem eco na tela)

Uso não interativo (stdin redirecionado, ex.: scripts/CI/containers):
    printf '%s\n%s\n' "$PW" "$PW" | docker compose run -T --rm api \
        python -m app.cli create-admin --username U --display-name N
    (a senha é lida do stdin em duas linhas: senha, depois repetição;
    nunca é ecoada nem registrada em log)
"""

import argparse
import getpass
import sys

from app.core.db import SessionLocal, get_engine
from app.core.errors import AppError
from app.users.service import create_professor


def _read_password(prompt: str) -> str:
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return sys.stdin.readline().rstrip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Cria um administrador local")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name", required=True)
    args = parser.parse_args(argv)

    password = _read_password("Senha do administrador: ")
    if password != _read_password("Repita a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    with SessionLocal(bind=get_engine()) as db:
        try:
            create_professor(db, username=args.username, display_name=args.display_name,
                             role="ADMIN_LOCAL", password=password, must_change_password=False)
            db.commit()
        except AppError as exc:
            print(exc.message, file=sys.stderr)
            return 1
    print("Administrador criado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
