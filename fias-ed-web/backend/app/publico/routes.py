"""As únicas rotas sem autenticação do sistema (§10 da spec).

Router próprio, montado sem a dependência de sessão — a separação é física
para que ninguém acrescente uma rota autenticada aqui por engano, nem o
contrário. Nada que identifique o professor ou a turma sai daqui: quem abre o
link vê as 24 perguntas e a escala, e mais nada.
"""
import datetime as dt
import hashlib
import hmac
from datetime import timezone

from fastapi import APIRouter, Depends, Request, Response
from fias_ed_engine.qti import IncompleteResponseError, QtiImportError, aggregate, score_response
from fias_ed_engine.rules import load_rules
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import ColetaQTI, ConsentimentoQTI, LinkQTI, RespostaQTI, ResultadoQTI, utcnow
from app.qti.links import link_valido

router = APIRouter()

# Cookie do navegador do estudante, sem identidade nenhuma: guarda, para cada
# LinkQTI ao qual este navegador já consentiu nesta sessão (sem max_age —
# morre quando o navegador fecha), um HMAC-SHA256 do `link.id` chaveado por
# `link.token_hash` — nunca o `link.id` cru. `token_hash` já é um segredo por
# link, já vive no banco e nunca sai dele; não introduzimos chave de
# aplicação nova (não há `secret_key` em `Settings`, e criar uma significa
# variável de ambiente nova e um jeito de invalidar consentimento em
# andamento). Sem a assinatura, quem só sabe o `link.id` (que nem chega ao
# estudante, mas não é o único jeito de alguém obtê-lo) conseguiria forjar o
# cookie e gravar resposta sem nunca passar por `/consentir` — achado da
# verificação final da fatia, 2026-09-26. Não é gravado no banco e não tem
# ligação nenhuma com RespostaQTI: é só o que autoriza a própria requisição
# de responder a seguir, exatamente como pedido no design ("o consentimento
# fica na sessão do navegador, não no banco ligado à resposta"). Path
# restrito a /publico para não se misturar com o cookie de sessão do
# professor. A flag `secure` não é fixa: acompanha o esquema de `public_url`
# (ver `_cookie_kwargs`), porque na sala, sem TLS, ela é `http://IP:8081`.
COOKIE_CONSENTIMENTO = "fias_qti_consentimento"


def _cookie_kwargs() -> dict:
    # `Secure` segue o esquema da URL pública. Na sala, sem TLS, ela é http://IP:8081,
    # e os navegadores descartam cookie Secure vindo de http fora de localhost — o
    # estudante aceitaria o convite e levaria 409 em todo envio. Se um dia houver TLS,
    # a URL passa a https e o Secure volta sozinho.
    seguro = get_settings().public_url.startswith("https://")
    return {"httponly": True, "secure": seguro, "samesite": "strict", "path": "/publico"}


def _valor_consentimento(link: LinkQTI) -> str:
    """HMAC-SHA256 do `link.id`, chaveado por `link.token_hash`. Quem tem o
    token consegue calcular este valor — mas quem tem o token já pode chamar
    `/consentir` do jeito certo, então isso não é perda nenhuma."""
    return hmac.new(link.token_hash.encode("utf-8"), str(link.id).encode("utf-8"), hashlib.sha256).hexdigest()


def _link_invalido() -> AppError:
    # Mesma mensagem para token errado, expirado, revogado ou de coleta
    # apagada — `link_valido` já reduziu tudo isso a um None só; distinguir
    # os casos aqui devolveria a informação que a redução existe para
    # esconder.
    return AppError(404, "LINK_INVALIDO", "Este link não está mais disponível.")


def _consentiu_na_sessao(request: Request, link: LinkQTI) -> bool:
    esperado = _valor_consentimento(link)
    valores = request.cookies.get(COOKIE_CONSENTIMENTO, "").split(",")
    return any(hmac.compare_digest(v, esperado) for v in valores)


def _marcar_consentimento_na_sessao(request: Request, response: Response, link: LinkQTI) -> None:
    atuais = {v for v in request.cookies.get(COOKIE_CONSENTIMENTO, "").split(",") if v}
    atuais.add(_valor_consentimento(link))
    response.set_cookie(COOKIE_CONSENTIMENTO, ",".join(atuais), **_cookie_kwargs())


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
    _marcar_consentimento_na_sessao(request, response, link)
    return {"ok": True}


@router.post("/publico/qti/{token}/responder", status_code=201)
def responder(token: str, body: ResponderIn, request: Request, db: Session = Depends(get_db)):
    link = link_valido(db, token)
    if link is None:
        raise _link_invalido()
    if not _consentiu_na_sessao(request, link):
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

    # A trava segue SEMPRE a ordem coleta -> link, a mesma que `criar_link` usa (trava a
    # coleta, depois mexe em link_qti). Sem essa ordem aqui: este envio travaria o LINK
    # primeiro e só pediria a COLETA depois (a FK do INSERT em resposta_qti pede FOR KEY
    # SHARE nela); um `criar_link` concorrente para a mesma data travaria a COLETA
    # primeiro e só pediria a linha do LINK depois (para revogá-la) — cada transação
    # esperando a que a outra segura, ciclo fechado. O Postgres detecta esse deadlock em
    # ~1s e aborta um dos dois lados (500 para o estudante, ou a geração do link falha em
    # silêncio para o professor). Achado da rodada de conserto 1 (revisão), regressão
    # desta tarefa: antes de `criar_link` travar a coleta, esse ciclo não existia.
    # FOR NO KEY UPDATE (key_share=True): conflita com o FOR UPDATE de `criar_link` e
    # com outro envio vivo desta coleta, mas NÃO com o FOR KEY SHARE que a FK do INSERT
    # de `consentir` (em consentimento_qti) pede — consentir continua livre.
    db.execute(select(ColetaQTI.id).where(ColetaQTI.id == link.coleta_id).with_for_update(key_share=True))
    # O limite é conferido sob FOR UPDATE do LinkQTI, na mesma transação do INSERT.
    # `populate_existing` é obrigatório: sem ele o SELECT devolve o objeto que
    # `link_valido` já carregou nesta sessão, com os atributos de antes.
    link_travado = db.execute(select(LinkQTI).where(LinkQTI.id == link.id)
                              .with_for_update()
                              .execution_options(populate_existing=True)).scalar_one()
    # Revalida com a trava na mão: entre `link_valido` e aqui o professor pode ter
    # gerado outro link para a mesma data — o que revoga este — ou revogado à mão.
    agora = dt.datetime.now(timezone.utc)
    if (link_travado.revogado_em is not None or link_travado.deleted_at is not None
            or link_travado.expira_em <= agora):
        db.rollback()
        raise _link_invalido()
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
