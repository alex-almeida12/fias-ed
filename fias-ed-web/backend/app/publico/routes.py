"""As únicas rotas sem autenticação do sistema (§10 da spec).

Router próprio, montado sem a dependência de sessão — a separação é física
para que ninguém acrescente uma rota autenticada aqui por engano, nem o
contrário. Nada que identifique o professor ou a turma sai daqui: quem abre o
link vê as 24 perguntas e a escala, e mais nada.
"""
from fastapi import APIRouter, Depends, Request, Response
from fias_ed_engine.qti import IncompleteResponseError, QtiImportError, aggregate, score_response
from fias_ed_engine.rules import load_rules
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.models import ColetaQTI, ConsentimentoQTI, LinkQTI, RespostaQTI, ResultadoQTI, utcnow
from app.qti.links import link_valido

router = APIRouter()

# Cookie do navegador do estudante, sem identidade nenhuma: guarda só os ids
# de LinkQTI para os quais este navegador já consentiu, nesta sessão (sem
# max_age — morre quando o navegador fecha). Não é gravado no banco e não
# tem ligação nenhuma com RespostaQTI: é só o que autoriza a própria
# requisição de responder a seguir, exatamente como pedido no design ("o
# consentimento fica na sessão do navegador, não no banco ligado à
# resposta"). Path restrito a /publico para não se misturar com o cookie de
# sessão do professor.
COOKIE_CONSENTIMENTO = "fias_qti_consentimento"
_COOKIE_KWARGS = {"httponly": True, "secure": True, "samesite": "strict", "path": "/publico"}


def _link_invalido() -> AppError:
    # Mesma mensagem para token errado, expirado, revogado ou de coleta
    # apagada — `link_valido` já reduziu tudo isso a um None só; distinguir
    # os casos aqui devolveria a informação que a redução existe para
    # esconder.
    return AppError(404, "LINK_INVALIDO", "Este link não está mais disponível.")


def _consentiu_na_sessao(request: Request, link_id) -> bool:
    ids = request.cookies.get(COOKIE_CONSENTIMENTO, "").split(",")
    return str(link_id) in ids


def _marcar_consentimento_na_sessao(request: Request, response: Response, link_id) -> None:
    atuais = {v for v in request.cookies.get(COOKIE_CONSENTIMENTO, "").split(",") if v}
    atuais.add(str(link_id))
    response.set_cookie(COOKIE_CONSENTIMENTO, ",".join(atuais), **_COOKIE_KWARGS)


def _registrar_consentimento(db: Session, coleta_id, documento_versao: str) -> None:
    """`aceites` incrementado atomicamente com INSERT ... ON CONFLICT DO
    UPDATE: uma linha por coleta (unicidade de banco, garantida na tarefa
    anterior), e a soma acontece no próprio SQL — nunca lê-e-escreve, que sob
    concorrência perderia incrementos."""
    stmt = pg_insert(ConsentimentoQTI).values(coleta_id=coleta_id, documento_versao=documento_versao, aceites=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ConsentimentoQTI.coleta_id],
        set_={"aceites": ConsentimentoQTI.aceites + 1, "documento_versao": stmt.excluded.documento_versao,
              "updated_at": utcnow()},
    )
    db.execute(stmt)


class ConsentirIn(BaseModel):
    documento_versao: str = Field(min_length=1, max_length=32)


class ResponderIn(BaseModel):
    respostas: dict[str, int]


@router.get("/publico/qti/{token}")
def obter_questionario(token: str, db: Session = Depends(get_db)):
    link = link_valido(db, token)
    if link is None:
        raise _link_invalido()
    cfg = load_rules("qti_config")
    itens = [{"order": item["order"], "text": item["text_pt_br"]} for item in cfg["items"]]
    return {"itens": itens, "escala": cfg["instrument"]["likert"], "stem": cfg["instrument"]["stem"]}


@router.post("/publico/qti/{token}/consentir", status_code=201)
def consentir(token: str, body: ConsentirIn, request: Request, response: Response,
             db: Session = Depends(get_db)):
    link = link_valido(db, token)
    if link is None:
        raise _link_invalido()
    _registrar_consentimento(db, link.coleta_id, body.documento_versao)
    db.commit()
    _marcar_consentimento_na_sessao(request, response, link.id)
    return {"ok": True}


@router.post("/publico/qti/{token}/responder", status_code=201)
def responder(token: str, body: ResponderIn, request: Request, db: Session = Depends(get_db)):
    link = link_valido(db, token)
    if link is None:
        raise _link_invalido()
    if not _consentiu_na_sessao(request, link.id):
        raise AppError(409, "QTI_CONSENTIMENTO_AUSENTE", "É preciso aceitar o convite antes de responder.")

    try:
        respostas = {int(k): v for k, v in body.respostas.items()}
    except (TypeError, ValueError) as exc:
        raise AppError(422, "QTI_RESPOSTA_INVALIDA", "Confira as respostas informadas.") from exc

    cfg = load_rules("qti_config")
    try:
        # Quem valida a escala e a completude é o motor, não o Web.
        score_response(respostas, cfg)
    except (IncompleteResponseError, QtiImportError) as exc:
        raise AppError(422, "QTI_RESPOSTA_INVALIDA", str(exc)) from exc

    # O limite é conferido sob FOR UPDATE do LinkQTI, na mesma transação do
    # INSERT: sem isso, dois envios com uma vaga restante passam os dois pela
    # contagem antes de qualquer um gravar, e o limite vira sugestão.
    link_travado = db.execute(select(LinkQTI).where(LinkQTI.id == link.id).with_for_update()).scalar_one()
    atual = db.scalar(select(func.count()).select_from(RespostaQTI)
                      .where(RespostaQTI.coleta_id == link_travado.coleta_id, RespostaQTI.deleted_at.is_(None)))
    if atual >= link_travado.limite_respostas:
        db.rollback()
        raise AppError(409, "QTI_LIMITE_ATINGIDO", "Este link já recebeu o número máximo de respostas.")

    db.add(RespostaQTI(coleta_id=link_travado.coleta_id, response_index=atual,
                       respostas={str(k): v for k, v in respostas.items()}))
    db.flush()

    brutas = db.scalars(select(RespostaQTI.respostas)
                        .where(RespostaQTI.coleta_id == link_travado.coleta_id,
                               RespostaQTI.deleted_at.is_(None))).all()
    agregado = aggregate([{int(k): v for k, v in r.items()} for r in brutas], cfg)

    coleta = db.get(ColetaQTI, link_travado.coleta_id)
    coleta.response_count = agregado["response_count"]
    coleta.displayable = agregado["displayable"]

    resultado = db.execute(select(ResultadoQTI)
                           .where(ResultadoQTI.coleta_id == link_travado.coleta_id)).scalars().first()
    if resultado is None:
        db.add(ResultadoQTI(coleta_id=link_travado.coleta_id, octantes=agregado["octants"],
                            agency=agregado["agency"], communion=agregado["communion"]))
    else:
        resultado.octantes = agregado["octants"]
        resultado.agency = agregado["agency"]
        resultado.communion = agregado["communion"]

    db.commit()
    return {"ok": True}
