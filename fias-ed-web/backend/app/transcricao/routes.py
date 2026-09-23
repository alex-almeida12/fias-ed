"""Rotas das Tasks 8 e 9: "qual destas vozes é você?" e a revisão da transcrição.

Segue o estilo de app.aulas.routes — posse verificada por get_owned_aula (e, para
um trecho isolado, get_owned_segmento), o efeito de fato mora em
app.transcricao.service, log_event só no que muda de estado. O rótulo interno do
diarizador nunca aparece aqui: `vozes_da_aula` já devolve as vozes na ordem que a
rota numera como "voz-1", "voz-2"…
"""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import aula_payload, current_audio, get_owned_aula
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.core.messages import error_message
from app.models import Falante
from app.transcricao.service import (VozDesconhecida, atribuir_papeis, get_owned_segmento,
                                     revisar_segmento, segmento_payload, segmentos_do_bloco,
                                     total_blocos, transcricao_da_aula, vozes_da_aula)

router = APIRouter()


class EscolhaIn(BaseModel):
    rotulo: str


class SegmentoPatch(BaseModel):
    texto: str | None = Field(default=None, max_length=4000)
    papel: Literal["PROFESSOR", "ALUNO"] | None = None
    version: int


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


@router.get("/aulas/{aula_id}/transcricao")
def obter_transcricao(aula_id: uuid.UUID, bloco: int = 0, actor: Actor = Depends(current_actor),
                      db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    transcricao = transcricao_da_aula(db, aula.id)
    if transcricao is None:
        raise AppError(404, "TRANSCRICAO_NAO_ENCONTRADA", "Esta aula ainda não tem transcrição.")
    audio = current_audio(db, aula.id)
    linhas = segmentos_do_bloco(db, transcricao, bloco)
    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    return {"bloco": bloco, "blocos": total_blocos(audio.duration_ms if audio is not None else 0),
            "segmentos": [segmento_payload(seg, papel) for seg, papel in linhas]}


@router.patch("/segmentos/{segmento_id}")
def editar_segmento(segmento_id: uuid.UUID, body: SegmentoPatch, actor: Actor = Depends(current_actor),
                    db: Session = Depends(get_db)):
    seg, aula_id = get_owned_segmento(db, actor, segmento_id)
    ok = revisar_segmento(db, seg, texto=body.texto, papel=body.papel, version_esperada=body.version)
    if not ok:
        raise AppError(409, "SEGMENTO_DESATUALIZADO", error_message("SEGMENTO_DESATUALIZADO"))
    audit(db, actor, "segmento", seg.id, "update")
    db.commit()
    db.refresh(seg)
    falante = db.get(Falante, seg.falante_id)
    log_event("segmento_editado", aula_id=aula_id)
    return segmento_payload(seg, falante.role)


@router.post("/aulas/{aula_id}/transcricao/concluir")
def concluir_transcricao(aula_id: uuid.UUID, actor: Actor = Depends(current_actor),
                         db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if aula.status != "READY_FOR_TRANSCRIPT_REVIEW":
        raise AppError(409, "AULA_STATE", "Esta aula não está em revisão de transcrição.")
    aula.status, aula.error_code = "READY_FOR_FIAS", None
    audit(db, actor, "aula", aula.id, "update")
    db.commit()
    log_event("revisao_concluida", aula_id=aula.id)
    return aula_payload(db, aula)
