import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio.storage import delete_file
from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import (aula_payload, aula_summary, get_owned_aula, has_active_job,
                               soft_delete_aula)
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Aula, Disciplina, Turma

router = APIRouter()


class AulaIn(BaseModel):
    turma_id: uuid.UUID
    disciplina_id: uuid.UUID
    lesson_date: date
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


def _owned(db: Session, model, obj_id: uuid.UUID, professor_id: uuid.UUID):
    obj = db.get(model, obj_id)
    return obj if obj is not None and obj.deleted_at is None and obj.professor_id == professor_id else None


@router.post("/aulas", status_code=201)
def create_aula(body: AulaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    professor_id = actor.effective_professor_id
    if _owned(db, Turma, body.turma_id, professor_id) is None:
        raise AppError(422, "TURMA_INVALIDA", "Escolha uma das suas turmas.")
    if _owned(db, Disciplina, body.disciplina_id, professor_id) is None:
        raise AppError(422, "DISCIPLINA_INVALIDA", "Escolha uma das suas disciplinas.")
    aula = Aula(professor_id=professor_id, turma_id=body.turma_id, disciplina_id=body.disciplina_id,
                lesson_date=body.lesson_date, note=body.note or None, status="DRAFT")
    db.add(aula)
    db.flush()
    audit(db, actor, "aula", aula.id, "create")
    db.commit()
    log_event("aula_created", aula_id=aula.id)
    return aula_payload(db, aula)


@router.get("/aulas")
def list_aulas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Aula, Turma, Disciplina)
        .join(Turma, Turma.id == Aula.turma_id).join(Disciplina, Disciplina.id == Aula.disciplina_id)
        .where(Aula.professor_id == actor.effective_professor_id, Aula.deleted_at.is_(None))
        .order_by(Aula.lesson_date.desc(), Aula.created_at.desc())).all()
    audit(db, actor, "aula", None, "read")
    db.commit()
    return [aula_summary(a, t, d) for a, t, d in rows]


@router.get("/aulas/{aula_id}")
def get_aula(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    return aula_payload(db, aula)


@router.delete("/aulas/{aula_id}", status_code=204)
def delete_aula(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if has_active_job(db, aula.id):
        raise AppError(409, "AULA_BUSY", "Aguarde o processamento terminar para excluir a aula.")
    paths = soft_delete_aula(db, aula)
    audit(db, actor, "aula", aula.id, "delete")
    db.commit()
    for rel in paths:
        delete_file(rel)
    log_event("aula_deleted", aula_id=aula.id)
