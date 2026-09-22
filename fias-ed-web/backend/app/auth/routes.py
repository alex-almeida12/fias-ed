import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import Actor, current_actor_any
from app.auth.passwords import DUMMY_HASH, hash_password, needs_rehash, verify_password
from app.auth.sessions import (clear_session_cookies, create_session, delete_all_sessions,
                               set_session_cookies)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Professor, utcnow
from app.users.service import validate_password

router = APIRouter()


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def me_payload(actor: Actor) -> dict:
    u = actor.user
    return {
        "id": str(u.id), "username": u.username, "display_name": u.display_name, "role": u.role,
        "must_change_password": u.must_change_password,
        "acting_as": ({"id": str(actor.acting_as.id), "display_name": actor.acting_as.display_name}
                      if actor.acting_as else None),
    }


def _login_failed() -> AppError:
    return AppError(401, "LOGIN_FAILED", "Usuário ou senha incorretos.")


@router.post("/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    s, now = get_settings(), utcnow()
    user = db.scalar(select(Professor).where(Professor.username == body.username.strip().lower(),
                                             Professor.deleted_at.is_(None)))
    if user is None or (user.locked_until is not None and user.locked_until > now):
        verify_password(DUMMY_HASH, body.password)
        raise _login_failed()
    if not verify_password(user.password_hash, body.password):
        user.failed_logins += 1
        if user.failed_logins >= s.login_max_failures:
            user.locked_until = now + timedelta(minutes=s.login_lock_minutes)
            user.failed_logins = 0
            log_event("login_locked", level=logging.WARNING, professor_id=user.id)
        db.commit()
        raise _login_failed()
    if not user.is_active:
        raise _login_failed()
    user.failed_logins, user.locked_until = 0, None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    new_session = create_session(db, user)
    db.commit()
    set_session_cookies(response, new_session)
    log_event("login", professor_id=user.id)
    return me_payload(Actor(user=user, session=new_session.row, acting_as=None))


@router.post("/auth/logout", status_code=204)
def logout(response: Response, actor: Actor = Depends(current_actor_any), db: Session = Depends(get_db)):
    db.delete(db.merge(actor.session))
    db.commit()
    clear_session_cookies(response)


@router.get("/auth/me")
def me(actor: Actor = Depends(current_actor_any)):
    return me_payload(actor)


@router.post("/auth/password")
def change_password(body: PasswordIn, response: Response, actor: Actor = Depends(current_actor_any),
                    db: Session = Depends(get_db)):
    user = db.merge(actor.user)
    if not verify_password(user.password_hash, body.current_password):
        raise AppError(401, "PASSWORD_WRONG", "A senha atual não confere.")
    validate_password(body.new_password)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    delete_all_sessions(db, user.id)
    new_session = create_session(db, user)
    db.commit()
    set_session_cookies(response, new_session)
    log_event("password_changed", professor_id=user.id)
    return me_payload(Actor(user=user, session=new_session.row, acting_as=None))
