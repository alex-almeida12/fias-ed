import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import record
from app.auth.deps import Actor, current_admin
from app.auth.routes import me_payload
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Professor

router = APIRouter(prefix="/admin")


class AgirComoIn(BaseModel):
    professor_id: uuid.UUID


@router.post("/agir-como")
def agir_como(body: AgirComoIn, actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    if body.professor_id == actor.user.id:
        raise AppError(422, "AGIR_COMO_PROPRIA_CONTA", "Você já está na sua própria conta.")
    target = db.get(Professor, body.professor_id)
    if target is None or target.deleted_at is not None:
        raise AppError(404, "CONTA_NAO_ENCONTRADA", "Conta não encontrada.")
    actor.session.acting_as_professor_id = target.id
    record(db, admin_id=actor.user.id, professor_id=target.id, resource="professor",
           resource_id=target.id, action="read")
    db.commit()
    log_event("admin_act_as", admin_id=actor.user.id, professor_id=target.id)
    return me_payload(Actor(user=actor.user, session=actor.session, acting_as=target))


@router.delete("/agir-como")
def parar_de_agir(actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    actor.session.acting_as_professor_id = None
    db.commit()
    return me_payload(Actor(user=actor.user, session=actor.session, acting_as=None))
