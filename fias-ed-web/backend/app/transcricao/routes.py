"""Rotas da Task 8: "qual destas vozes é você?".

Segue o estilo de app.aulas.routes — posse verificada por get_owned_aula, o
efeito de fato mora em app.transcricao.service, log_event só no que muda de
estado. O rótulo interno do diarizador nunca aparece aqui: `vozes_da_aula` já
devolve as vozes na ordem que a rota numera como "voz-1", "voz-2"…
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import aula_payload, get_owned_aula
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.transcricao.service import VozDesconhecida, atribuir_papeis, vozes_da_aula

router = APIRouter()


class EscolhaIn(BaseModel):
    rotulo: str


@router.get("/aulas/{aula_id}/vozes")
def listar_vozes(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    grupos = vozes_da_aula(db, aula)
    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    return {"vozes": [{"rotulo": f"voz-{i + 1}", "tempo_total_ms": g.tempo_total_ms,
                       "n_segmentos": g.n_segmentos,
                       "amostras": [{"inicio_ms": a, "fim_ms": b} for a, b in g.amostras]}
                      for i, g in enumerate(grupos)]}


@router.post("/aulas/{aula_id}/vozes/escolher")
def escolher_voz(aula_id: uuid.UUID, body: EscolhaIn, actor: Actor = Depends(current_actor),
                 db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if aula.status != "READY_FOR_SPEAKER_REVIEW":
        raise AppError(409, "AULA_STATE", "Esta aula não está esperando a escolha da voz.")
    try:
        atribuir_papeis(db, aula, body.rotulo)
    except VozDesconhecida:
        raise AppError(422, "VOZ_INVALIDA", "Escolha uma das vozes da lista.") from None
    aula.status, aula.error_code = "READY_FOR_TRANSCRIPT_REVIEW", None
    audit(db, actor, "aula", aula.id, "update")
    db.commit()
    log_event("voz_escolhida", aula_id=aula.id)
    return aula_payload(db, aula)
