import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import MIN_PASSWORD_LENGTH, hash_password
from app.core.errors import AppError
from app.models import Professor

_USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,64}$")


def normalize_username(raw: str) -> str:
    username = raw.strip().lower()
    if not _USERNAME_RE.match(username):
        raise AppError(422, "USERNAME_INVALID",
                       "Use de 3 a 64 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado.")
    return username


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AppError(422, "PASSWORD_TOO_SHORT",
                       f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")


def create_professor(db: Session, *, username: str, display_name: str, role: str, password: str,
                     must_change_password: bool) -> Professor:
    username = normalize_username(username)
    validate_password(password)
    if db.scalar(select(Professor.id).where(Professor.username == username)):
        raise AppError(409, "USERNAME_TAKEN", "Este nome de usuário já está em uso.")
    professor = Professor(username=username, display_name=display_name.strip(), role=role,
                          password_hash=hash_password(password),
                          must_change_password=must_change_password)
    db.add(professor)
    db.flush()
    return professor
