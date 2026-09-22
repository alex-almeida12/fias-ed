import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.sessions import COOKIE_SESSION, CSRF_HEADER, csrf_ok, resolve_session
from app.core.db import get_db
from app.core.errors import AppError
from app.models import Professor, Sessao

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class Actor:
    user: Professor
    session: Sessao
    acting_as: Professor | None

    @property
    def effective_professor_id(self) -> uuid.UUID:
        return self.acting_as.id if self.acting_as else self.user.id

    @property
    def is_admin(self) -> bool:
        return self.user.role == "ADMIN_LOCAL"


def _unauthenticated() -> AppError:
    return AppError(401, "UNAUTHENTICATED", "Entre com seu usuário e senha.")


def current_actor_any(request: Request, db: Session = Depends(get_db)) -> Actor:
    sessao = resolve_session(db, request.cookies.get(COOKIE_SESSION))
    if sessao is None:
        raise _unauthenticated()
    user = db.get(Professor, sessao.professor_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        db.delete(sessao)
        db.commit()
        raise _unauthenticated()
    if request.method in _MUTATING and not csrf_ok(sessao, request.headers.get(CSRF_HEADER)):
        raise AppError(403, "CSRF_INVALID", "Sua sessão precisa ser renovada. Recarregue a página.")
    acting = None
    if sessao.acting_as_professor_id is not None:
        target = db.get(Professor, sessao.acting_as_professor_id)
        if user.role == "ADMIN_LOCAL" and target is not None and target.deleted_at is None:
            acting = target
        else:
            sessao.acting_as_professor_id = None
    db.commit()
    return Actor(user=user, session=sessao, acting_as=acting)


def current_actor(actor: Actor = Depends(current_actor_any)) -> Actor:
    if actor.user.must_change_password:
        raise AppError(403, "PASSWORD_CHANGE_REQUIRED", "Troque sua senha provisória para continuar.")
    return actor


def current_admin(actor: Actor = Depends(current_actor)) -> Actor:
    if not actor.is_admin:
        raise AppError(403, "FORBIDDEN", "Você não tem permissão para esta ação.")
    return actor
