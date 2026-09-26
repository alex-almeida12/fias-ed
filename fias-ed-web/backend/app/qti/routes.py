import datetime as dt
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fias_ed_engine.rules import load_rules
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.ciclos.service import ciclo_do_professor
from app.core.db import get_db
from app.core.errors import AppError
from app.core.messages import error_message
from app.models import ColetaQTI, LinkQTI
from app.qti.links import criar_link, revogar
from app.qti.service import coleta_nativa_do_dia, importar_relatorio

router = APIRouter()

# relatório do questionário é um CSV de 24 itens; nada legítimo chega perto disso
TAMANHO_MAXIMO = 2 * 1024 * 1024


@router.post("/ciclos/{ciclo_id}/qti/importar", status_code=201)
async def importar_qti(ciclo_id: uuid.UUID, coletado_em: dt.date = Form(...), arquivo: UploadFile = File(...),
                       actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    ciclo = ciclo_do_professor(db, actor, ciclo_id)
    bruto = await arquivo.read()
    if len(bruto) > TAMANHO_MAXIMO:
        raise AppError(413, "QTI_ARQUIVO_GRANDE", error_message("QTI_ARQUIVO_GRANDE"))
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(422, "QTI_ARQUIVO_ILEGIVEL", error_message("QTI_ARQUIVO_ILEGIVEL")) from exc
    coleta = importar_relatorio(db, ciclo, texto, coletado_em)
    audit(db, actor, "coleta_qti", coleta.id, "create")
    db.commit()
    return {"id": str(coleta.id), "coletado_em": coleta.coletado_em.isoformat(),
           "origem": coleta.origem, "response_count": coleta.response_count,
           "displayable": coleta.displayable,
           "min_responses": load_rules("qti_config")["instrument"]["min_responses"]}


class LinkIn(BaseModel):
    n_estudantes: int = Field(gt=0, le=200)
    dias: int = Field(gt=0, le=90)
    coletado_em: dt.date


@router.post("/ciclos/{ciclo_id}/qti/link", status_code=201)
def gerar_link(ciclo_id: uuid.UUID, body: LinkIn, request: Request,
               actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    ciclo = ciclo_do_professor(db, actor, ciclo_id)
    coleta = coleta_nativa_do_dia(db, ciclo, body.coletado_em)
    link, token = criar_link(db, coleta, n_estudantes=body.n_estudantes, dias=body.dias)
    audit(db, actor, "coleta_qti", coleta.id, "create")
    db.commit()
    # O token viaja só nesta resposta. Não entra em log nem em nenhuma outra
    # rota: `log_event` tem allowlist de campos e não o aceitaria, mas a regra
    # aqui é anterior a ela — não se registra credencial.
    return {"url": f"{request.base_url}responder/{token}".replace("//responder", "/responder"),
            "expira_em": link.expira_em.isoformat(),
            "limite_respostas": link.limite_respostas}


@router.post("/qti/links/{link_id}/revogar", status_code=204)
def revogar_link(link_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    link = db.get(LinkQTI, link_id)
    if link is None:
        raise AppError(404, "LINK_QTI_NAO_ENCONTRADO", "Link não encontrado.")
    coleta = db.get(ColetaQTI, link.coleta_id)
    ciclo_do_professor(db, actor, coleta.ciclo_id)
    revogar(db, link)
    audit(db, actor, "coleta_qti", coleta.id, "update")
    db.commit()
