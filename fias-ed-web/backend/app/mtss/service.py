"""MTSS Tier 1: o que o motor interpretou da aula, qualificado pelo QTI, e
gravado como o professor vai ler depois da aula.

Nenhuma regra científica é implementada aqui: `fias_ed_engine.mtss.evaluate`
decide quais regras disparam e com que framing, `qualify` diz se o QTI
concorda com cada uma, e `recommendations` decide o texto de cada
recomendação. Este módulo só escolhe as entradas — a codificação da aula (via
`codificacao_da_aula`, mesmo motivo de `triangulacao/service.py`: para que o
MTSS nunca interprete uma aula diferente da que acabou de ser codificada) e a
triangulação vigente (via `triangular`, recomputada aqui em vez de lida da
tabela, pelo mesmo motivo) — e persiste exatamente o que o motor devolveu, na
ordem em que devolveu. Nenhuma prioridade, pontuação ou reordenação é
calculada aqui: a decisão de mostrar recomendações concordantes primeiro é de
apresentação e pertence à tela (Task 11).

O sistema não emite veredito sobre o professor: toda regra chega com
`framing` do próprio motor (nunca reescrito aqui) e `validation_status`
sempre PENDING_SCIENTIFIC_VALIDATION — honestidade científica declarada, não
escondida.
"""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fias_ed_engine.mtss import build_facts, evaluate, qualify, recommendations
from fias_ed_engine.rules import load_rules

from app.fias.service import codificacao_da_aula
from app.models import Aula, IndicadorFIAS, InterpretacaoMTSS, RecomendacaoMTSS
from app.triangulacao.service import triangular


def interpretar(db: Session, aula: Aula) -> tuple[list[dict], list[dict]]:
    """Devolve (regras disparadas e já qualificadas, recomendações)."""
    regras = load_rules("fias_rules")
    codificacao = codificacao_da_aula(db, aula, regras)
    linhas = db.scalars(select(IndicadorFIAS).where(IndicadorFIAS.aula_id == aula.id,
                                                     IndicadorFIAS.deleted_at.is_(None))).all()
    indices = {i.index_id: {"value": i.value} for i in linhas}
    fatos = build_facts(codificacao.intervals, indices)
    disparadas = evaluate(fatos, load_rules("mtss_rules"))
    # `triangular` recomputa e regrava a triangulação — não lê a tabela — pelo
    # mesmo motivo de `codificacao_da_aula` acima: qualificar contra uma
    # triangulação gravada em outro momento arrisca comparar aulas diferentes
    # em silêncio. Isso produz um segundo `commit` nesta chamada, e cada um
    # deixa o banco consistente por si.
    pares = triangular(db, aula)
    qualificadas = qualify(disparadas, pares, load_rules("pedagogical_rules"))
    recs = recommendations(qualificadas, load_rules("pedagogical_rules"))

    db.execute(delete(InterpretacaoMTSS).where(InterpretacaoMTSS.aula_id == aula.id))
    db.execute(delete(RecomendacaoMTSS).where(RecomendacaoMTSS.aula_id == aula.id))
    for regra in qualificadas:
        db.add(InterpretacaoMTSS(
            aula_id=aula.id, rule_id=regra["rule_id"], tier1_dimension=regra["tier1_dimension"],
            framing=regra["framing"], interpretation=regra["interpretation"], evidence=regra["evidence"],
            evidence_segment_categories=regra["evidence_segment_categories"],
            source_reference=regra["source_reference"], validation_status=regra["validation_status"],
            rules_version=regra["rules_version"], qti_agreement=regra["qti_agreement"],
            qti_evidence=regra["qti_evidence"], divergence_question=regra["divergence_question"]))

    # qti_agreement da recomendação é cópia do campo da regra que a originou
    # (rec["rule_id"]) — `recommendations` não carrega esse campo, só o
    # rule_id, então é preciso buscá-lo de volta em `qualificadas`.
    qti_agreement_por_regra = {q["rule_id"]: q["qti_agreement"] for q in qualificadas}
    for rec in recs:
        db.add(RecomendacaoMTSS(
            aula_id=aula.id, recommendation_id=rec["recommendation_id"], rule_id=rec["rule_id"],
            text=rec["text"], validation_status=rec["validation_status"],
            source_reference=rec["source_reference"], qti_agreement=qti_agreement_por_regra[rec["rule_id"]]))
    db.commit()
    return qualificadas, recs
