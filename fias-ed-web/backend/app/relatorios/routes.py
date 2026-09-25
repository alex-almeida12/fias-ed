"""Rota da Task 10: o relatório da aula — a porta de saída única por onde tudo
que o FIAS-ED produziu sobre uma aula chega ao professor de uma vez só: o que
a observação mediu (`IndicadorFIAS`), a triangulação contra a percepção dos
estudantes (`Triangulacao`) e as recomendações pedagógicas do MTSS
(`InterpretacaoMTSS`/`RecomendacaoMTSS`).

**Esta rota só lê.** Nada aqui chama `triangular`, `interpretar`,
`code_lesson` ou qualquer conta do motor — tudo que o relatório mostra já foi
computado e gravado por `avancar` (app/pipeline/estados.py) antes da aula
chegar a `REPORT_READY`. Isso é deliberado, não uma economia de código: se a
rota recalculasse ao abrir, duas visitas à mesma aula poderiam mostrar números
diferentes assim que uma coleta de QTI nova entrasse no ciclo entre elas. O
relatório tem de ser o retrato do que foi computado, não uma leitura nova a
cada visita — é o que o professor lê e pode levar para uma reunião.

Por isso também não chamamos `codificacao_da_aula` (usada em
app/fias/routes.py): ela não tem guarda para aula sem transcrição e
levantaria `AttributeError` cru. Como esta rota só lê tabelas já persistidas,
ela não precisa da codificação nenhuma — só precisa dos `Segmento`s e
`ClassificacaoFIAS` já gravados, para religar a evidência de cada
interpretação MTSS ao trecho de fala que a sustenta (mesmo padrão de
`_observacoes`, app/fias/routes.py:94).

`validation_status` chega ao corpo tal como foi gravado, nunca filtrado:
sempre PENDING_SCIENTIFIC_VALIDATION em `Triangulacao` e `InterpretacaoMTSS`
(docstring dos dois modelos, app/models.py) — honestidade científica
declarada, não um detalhe a esconder. `RecomendacaoMTSS` não carrega essa
mesma garantia: `pedagogical_rules.json` grava hoje
"draft_pending_researcher_review" para toda recomendação, um valor de
VALIDATION_STATUS diferente e igualmente legítimo. O que importa é que o
campo sempre chegue ao corpo tal como está gravado, não que compartilhe um
único valor entre as quatro tabelas.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from fias_ed_engine.mtss import select_evidence_segments
from fias_ed_engine.rules import load_rules

from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import aula_payload, get_owned_aula
from app.core.db import get_db
from app.core.errors import AppError
from app.fias.routes import _indices
from app.models import ClassificacaoFIAS, InterpretacaoMTSS, RecomendacaoMTSS, Segmento, Triangulacao
from app.transcricao.service import texto_efetivo, transcricao_da_aula

router = APIRouter()

# WAITING_QTI é o único estado anterior a REPORT_READY que precisa de mensagem
# própria: é a única espera que depende de uma ação de fora do professor (a
# coleta do questionário da turma), e sem dizer isso a mensagem genérica
# deixaria a pessoa sem saber o que fazer. Os demais estados (ainda
# processando áudio, transcrição, classificação FIAS...) cabem no genérico:
# "o pipeline ainda não terminou" é verdade para todos eles.
_MENSAGEM_WAITING_QTI = ("Esta aula está esperando o questionário (QTI) da turma antes de fechar o "
                         "relatório.")
_MENSAGEM_PADRAO = "Esta aula ainda não tem um relatório pronto: o processamento ainda não terminou."


def _segmentos_para_evidencia(db: Session, aula_id: uuid.UUID) -> list[dict]:
    # transcricao_da_aula pode devolver None só num caminho que get_owned_aula
    # já barraria antes de chegar aqui (a transcrição só é apagada de verdade
    # junto da própria aula, em soft_delete_aula) — mas devolver evidências
    # vazias em vez de estourar é mais barato que provar essa garantia aqui.
    transcricao = transcricao_da_aula(db, aula_id)
    if transcricao is None:
        return []
    linhas = db.execute(
        select(Segmento, ClassificacaoFIAS)
        .join(ClassificacaoFIAS, ClassificacaoFIAS.segmento_id == Segmento.id)
        .where(Segmento.transcricao_id == transcricao.id)
        .order_by(Segmento.start_ms)
    ).all()
    # select_evidence_segments (fias_ed_engine.mtss) espera a chave "category"
    # — mapear pred_role_constrained para category é responsabilidade de quem
    # chama (mesma armadilha que _observacoes, app/fias/routes.py:94-100).
    return [{"category": cls.pred_role_constrained, "confidence": cls.confidence, "start_ms": seg.start_ms,
            "segmento_id": str(seg.id), "trecho": texto_efetivo(seg)} for seg, cls in linhas]


def _evidencias(segmentos: list[dict], categorias: list[int]) -> list[dict]:
    """Até 3 trechos por categoria em `evidence_segment_categories`. Uma
    interpretação sem categorias sai com lista vazia — normal, não erro: nem
    toda regra do MTSS cita evidência de segmento (ex.: MTSS_DIRECT_OVER_INDIRECT,
    que só olha índices agregados)."""
    evidencias = []
    for categoria in categorias:
        evidencias.extend(
            {"segmento_id": e["segmento_id"], "inicio_ms": e["start_ms"], "trecho": e["trecho"]}
            for e in select_evidence_segments(segmentos, categoria, limit=3))
    return evidencias


def _triangulacao_payload(t: Triangulacao) -> dict:
    return {
        "pair_id": t.pair_id,
        "fias": {"kind": t.fias_kind, "ref": t.fias_ref, "value": t.fias_value},
        "qti_values": t.qti_values,
        "qti_available": t.qti_available,
        "reflection_question": t.reflection_question,
        "source_reference": t.source_reference,
        "validation_status": t.validation_status,
    }


def _interpretacao_payload(i: InterpretacaoMTSS, segmentos: list[dict]) -> dict:
    return {
        "rule_id": i.rule_id,
        "tier1_dimension": i.tier1_dimension,
        "framing": i.framing,
        "interpretation": i.interpretation,
        "evidence": i.evidence,
        "evidence_segment_categories": i.evidence_segment_categories,
        "source_reference": i.source_reference,
        "validation_status": i.validation_status,
        "rules_version": i.rules_version,
        "qti_agreement": i.qti_agreement,
        "qti_evidence": i.qti_evidence,
        "divergence_question": i.divergence_question,
        "evidencias": _evidencias(segmentos, i.evidence_segment_categories),
    }


def _recomendacao_payload(r: RecomendacaoMTSS) -> dict:
    return {
        "recommendation_id": r.recommendation_id,
        "rule_id": r.rule_id,
        "text": r.text,
        "validation_status": r.validation_status,
        "source_reference": r.source_reference,
        "qti_agreement": r.qti_agreement,
    }


@router.get("/aulas/{aula_id}/relatorio")
def relatorio_da_aula(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if aula.status != "REPORT_READY":
        mensagem = _MENSAGEM_WAITING_QTI if aula.status == "WAITING_QTI" else _MENSAGEM_PADRAO
        raise AppError(409, "AULA_STATE", mensagem)

    regras = load_rules("fias_rules")
    segmentos = _segmentos_para_evidencia(db, aula.id)

    # Sem order_by de propósito: a tela (Task 11) decide a apresentação (ex.:
    # recomendações concordantes primeiro via qti_agreement, já persistido) —
    # aqui devolve-se na ordem em que o motor gravou.
    triangulacao = db.scalars(select(Triangulacao).where(Triangulacao.aula_id == aula.id)).all()
    interpretacoes = db.scalars(select(InterpretacaoMTSS).where(InterpretacaoMTSS.aula_id == aula.id)).all()
    recomendacoes = db.scalars(select(RecomendacaoMTSS).where(RecomendacaoMTSS.aula_id == aula.id)).all()

    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    return {
        "aula": aula_payload(db, aula),
        "indices": _indices(db, aula.id, regras),
        "triangulacao": [_triangulacao_payload(t) for t in triangulacao],
        "interpretacoes": [_interpretacao_payload(i, segmentos) for i in interpretacoes],
        "recomendacoes": [_recomendacao_payload(r) for r in recomendacoes],
    }
