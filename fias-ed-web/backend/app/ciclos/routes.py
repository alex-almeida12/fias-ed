import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.ciclos.schemas import CicloIn, ciclo_out
from app.core.db import get_db
from app.core.errors import AppError
from app.models import Ciclo, Disciplina, Turma

router = APIRouter()


def _owned(db: Session, model, obj_id: uuid.UUID, professor_id: uuid.UUID):
    obj = db.get(model, obj_id)
    return obj if obj is not None and obj.deleted_at is None and obj.professor_id == professor_id else None


def _owned_ciclo(db: Session, actor: Actor, ciclo_id: uuid.UUID) -> Ciclo:
    c = db.get(Ciclo, ciclo_id)
    if c is None or c.deleted_at is not None or c.professor_id != actor.effective_professor_id:
        raise AppError(404, "CICLO_NAO_ENCONTRADO", "Ciclo não encontrado.")
    return c


@router.post("/ciclos", status_code=201)
def criar_ciclo(body: CicloIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    professor_id = actor.effective_professor_id
    if _owned(db, Turma, body.turma_id, professor_id) is None:
        raise AppError(422, "TURMA_INVALIDA", "Escolha uma das suas turmas.")
    if _owned(db, Disciplina, body.disciplina_id, professor_id) is None:
        raise AppError(422, "DISCIPLINA_INVALIDA", "Escolha uma das suas disciplinas.")
    c = Ciclo(turma_id=body.turma_id, disciplina_id=body.disciplina_id, professor_id=professor_id,
              n_aulas_previstas=body.n_aulas_previstas, iniciado_em=body.iniciado_em)
    db.add(c)
    db.flush()
    audit(db, actor, "ciclo", c.id, "create")
    db.commit()
    db.refresh(c)
    return ciclo_out(c)


@router.post("/ciclos/{ciclo_id}/encerrar")
def encerrar_ciclo(ciclo_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    c = _owned_ciclo(db, actor, ciclo_id)
    c.encerrado_em = dt.date.today()
    audit(db, actor, "ciclo", c.id, "update")
    db.commit()
    db.refresh(c)
    return ciclo_out(c)
