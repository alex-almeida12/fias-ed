import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Professor, Sessao, utcnow

COOKIE_SESSION = "fias_session"
COOKIE_CSRF = "fias_csrf"
CSRF_HEADER = "X-CSRF-Token"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class NewSession:
    token: str
    csrf: str
    row: Sessao


def create_session(db: Session, professor: Professor) -> NewSession:
    s = get_settings()
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = utcnow()
    row = Sessao(professor_id=professor.id, token_sha256=_sha256(token), csrf_token_sha256=_sha256(csrf),
                 created_at=now, last_seen_at=now,
                 expires_at=now + timedelta(hours=s.session_absolute_hours))
    db.add(row)
    db.flush()
    return NewSession(token, csrf, row)


def resolve_session(db: Session, token: str | None) -> Sessao | None:
    if not token:
        return None
    row = db.scalar(select(Sessao).where(Sessao.token_sha256 == _sha256(token)))
    if row is None:
        return None
    now = utcnow()
    idle_limit = row.last_seen_at + timedelta(minutes=get_settings().session_idle_minutes)
    if row.expires_at <= now or idle_limit <= now:
        db.delete(row)
        db.commit()
        return None
    row.last_seen_at = now
    return row


def delete_all_sessions(db: Session, professor_id: uuid.UUID) -> None:
    db.execute(delete(Sessao).where(Sessao.professor_id == professor_id))


def csrf_ok(sessao: Sessao, header_value: str | None) -> bool:
    return hmac.compare_digest(_sha256(header_value or ""), sessao.csrf_token_sha256)


def set_session_cookies(response: Response, new_session: NewSession) -> None:
    max_age = get_settings().session_absolute_hours * 3600
    common = {"secure": True, "samesite": "strict", "path": "/", "max_age": max_age}
    response.set_cookie(COOKIE_SESSION, new_session.token, httponly=True, **common)
    response.set_cookie(COOKIE_CSRF, new_session.csrf, httponly=False, **common)


def clear_session_cookies(response: Response) -> None:
    for name in (COOKIE_SESSION, COOKIE_CSRF):
        response.delete_cookie(name, path="/", secure=True, samesite="strict")
