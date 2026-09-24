import datetime as dt
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.core.db import get_db
from app.core.errors import AppError
from app.core.messages import error_message
from app.models import Ciclo
from app.qti.service import importar_relatorio

router = APIRouter()

# relatório do questionário é um CSV de 24 itens; nada legítimo chega perto disso
TAMANHO_MAXIMO = 2 * 1024 * 1024


def _owned_ciclo(db: Session, actor: Actor, ciclo_id: uuid.UUID) -> Ciclo:
    c = db.get(Ciclo, ciclo_id)
    if c is None or c.deleted_at is not None or c.professor_id != actor.effective_professor_id:
        raise AppError(404, "CICLO_NAO_ENCONTRADO", "Ciclo não encontrado.")
    return c


@router.post("/ciclos/{ciclo_id}/qti/importar", status_code=201)
async def importar_qti(ciclo_id: uuid.UUID, coletado_em: dt.date = Form(...), arquivo: UploadFile = File(...),
                       actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    ciclo = _owned_ciclo(db, actor, ciclo_id)
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
           "displayable": coleta.displayable}
