"""Task 8b: o Web persiste a interpretação do MTSS -- uma linha por regra do
Tier 1 disparada, já qualificada pelo QTI, e uma linha por recomendação
pedagógica. Toda a ciência (quais regras disparam, framing, interpretação, se
o QTI concorda) vem de `fias_ed_engine.mtss` (evaluate/qualify/
recommendations); aqui só se prova que:

1. `interpretar` grava uma linha de `interpretacao_mtss` por regra disparada,
   sem duplicar;
2. reexecutar substitui em vez de acumular -- o professor pode reprocessar a
   aula;
3. sem coleta QTI vigente o MTSS continua disparando e gravando
   recomendações -- ele nunca dependeu do questionário para isso, só o
   qualifica depois;
4. com coleta vigente cujos octantes caem na faixa que concorda, a regra
   correspondente sai com "agree" e evidência preenchida;
5. as regras sem par de triangulação saem "unpaired", e isso não é erro;
6. nenhuma recomendação grava veredito sobre o professor;
7. toda linha gravada tem framing "reflection".

`aula_classificada` (conftest raiz) dispara sempre o mesmo conjunto de
regras: um segmento do professor em categoria 5 e um do aluno em categoria 8
(`classificar_para_triangulacao`), o que fixa cinco regras do MTSS --
MTSS_EXPOSITIVE_PREDOMINANCE, MTSS_DIRECT_OVER_INDIRECT,
MTSS_NO_STUDENT_INITIATIVE, MTSS_NO_IDEA_UPTAKE e MTSS_NO_PRAISE, todas com
framing "reflection". Os testes abaixo dependem desse conjunto fixo em vez de
reinventar um cenário -- é o mesmo fixture que `test_triangulacao.py` usa.
"""
import re

from sqlalchemy import select

from app.models import InterpretacaoMTSS, RecomendacaoMTSS
from app.mtss.service import interpretar

UNPAIRED_RULE_IDS = {"MTSS_QUESTIONS_PRESENT", "MTSS_EXPOSITIVE_PREDOMINANCE",
                     "MTSS_INSTRUCTIONS_PREDOMINANCE"}
MAPPED_RULE_IDS = {"MTSS_NO_PRAISE", "MTSS_NO_IDEA_UPTAKE", "MTSS_REACTIVE_MANAGEMENT_PRESENT",
                   "MTSS_NO_STUDENT_INITIATIVE", "MTSS_STUDENT_INITIATIVE_PRESENT",
                   "MTSS_DIRECT_OVER_INDIRECT"}


def test_interpretar_grava_uma_linha_por_regra_disparada_sem_duplicar(db, aula_classificada):
    qualificadas, _ = interpretar(db, aula_classificada)
    assert qualificadas  # a aula do fixture dispara ao menos uma regra

    gravadas = db.scalars(select(InterpretacaoMTSS)
                          .where(InterpretacaoMTSS.aula_id == aula_classificada.id)).all()
    assert len(gravadas) == len(qualificadas)
    assert {g.rule_id for g in gravadas} == {q["rule_id"] for q in qualificadas}
    assert len({g.rule_id for g in gravadas}) == len(gravadas)  # sem duplicada


def test_reexecutar_substitui_em_vez_de_acumular(db, aula_classificada):
    interpretar(db, aula_classificada)
    primeira = db.scalars(select(InterpretacaoMTSS)
                          .where(InterpretacaoMTSS.aula_id == aula_classificada.id)).all()
    assert primeira  # sem regra disparada o teste não protegeria nada

    interpretar(db, aula_classificada)  # o professor reprocessa a mesma aula
    segunda = db.scalars(select(InterpretacaoMTSS)
                         .where(InterpretacaoMTSS.aula_id == aula_classificada.id)).all()
    assert len(segunda) == len(primeira)

    rec_primeira = db.scalars(select(RecomendacaoMTSS)
                              .where(RecomendacaoMTSS.aula_id == aula_classificada.id)).all()
    assert rec_primeira  # idem para as recomendações


def test_sem_coleta_vigente_regras_mapeadas_saem_no_qti_e_recomendacoes_gravadas(db, aula_classificada):
    """`aula_classificada` não tem coleta QTI vigente por padrão (o fixture
    documenta isso). O MTSS nunca dependeu do QTI para disparar -- é isso que
    este teste protege."""
    qualificadas, recs = interpretar(db, aula_classificada)
    por_regra = {q["rule_id"]: q for q in qualificadas}
    disparadas_mapeadas = MAPPED_RULE_IDS & por_regra.keys()
    assert disparadas_mapeadas  # ao menos uma regra mapeada dispara no fixture

    for rule_id in disparadas_mapeadas:
        assert por_regra[rule_id]["qti_agreement"] == "no_qti"
        assert por_regra[rule_id]["qti_evidence"] is None
    assert recs  # sem QTI o MTSS continua gravando recomendações

    # O contrato do retorno não prova o que ficou na tabela -- só quem lê o
    # banco pega uma coluna gravada errada. A tela do relatório lê daqui, não
    # do retorno de `interpretar`.
    gravadas_por_regra = {g.rule_id: g for g in db.scalars(
        select(InterpretacaoMTSS).where(InterpretacaoMTSS.aula_id == aula_classificada.id)).all()}
    for rule_id in disparadas_mapeadas:
        assert gravadas_por_regra[rule_id].qti_agreement == "no_qti"
        assert gravadas_por_regra[rule_id].qti_evidence is None


def test_regras_sem_par_saem_unpaired_e_nao_e_erro(db, aula_classificada):
    qualificadas, _ = interpretar(db, aula_classificada)
    por_regra = {q["rule_id"]: q for q in qualificadas}
    disparadas_sem_par = UNPAIRED_RULE_IDS & por_regra.keys()
    assert disparadas_sem_par  # ao menos uma das três dispara no fixture

    for rule_id in disparadas_sem_par:
        assert por_regra[rule_id]["qti_agreement"] == "unpaired"
        assert por_regra[rule_id]["qti_evidence"] is None
        assert por_regra[rule_id]["divergence_question"] is None

    # Mesmo motivo do teste anterior: o retorno de `interpretar` é o contrato
    # da função, não prova do que foi gravado -- a tabela é o que a tela lê.
    gravadas_por_regra = {g.rule_id: g for g in db.scalars(
        select(InterpretacaoMTSS).where(InterpretacaoMTSS.aula_id == aula_classificada.id)).all()}
    for rule_id in disparadas_sem_par:
        assert gravadas_por_regra[rule_id].qti_agreement == "unpaired"
        assert gravadas_por_regra[rule_id].qti_evidence is None
        assert gravadas_por_regra[rule_id].divergence_question is None


def test_com_coleta_vigente_regra_correspondente_concorda(db, ciclo, coleta_em, aula_classificada):
    """`coleta_em` (conftest raiz) grava oc8=3.8, acima de high_above=3.67:
    TRI_INFLUENCE (mapeado só por oc8 -- oc1/Liderança fica de fora por
    efeito de teto) cai na faixa "high", que é o agrees_when de
    MTSS_DIRECT_OVER_INDIRECT. Concorda com os octantes padrão do fixture,
    sem precisar inventar valores sintéticos."""
    coleta_em(ciclo, "2026-09-01")  # anterior à data de aula_classificada (2026-09-22)
    qualificadas, _ = interpretar(db, aula_classificada)
    por_regra = {q["rule_id"]: q for q in qualificadas}
    assert "MTSS_DIRECT_OVER_INDIRECT" in por_regra
    regra = por_regra["MTSS_DIRECT_OVER_INDIRECT"]
    assert regra["qti_agreement"] == "agree"
    assert regra["qti_evidence"] is not None
    assert regra["qti_evidence"]["pair_id"] == "TRI_INFLUENCE"

    gravada = db.scalar(select(InterpretacaoMTSS)
                        .where(InterpretacaoMTSS.aula_id == aula_classificada.id,
                               InterpretacaoMTSS.rule_id == "MTSS_DIRECT_OVER_INDIRECT"))
    assert gravada.qti_agreement == "agree"
    assert gravada.qti_evidence is not None

    rec_gravada = db.scalar(select(RecomendacaoMTSS)
                            .where(RecomendacaoMTSS.aula_id == aula_classificada.id,
                                   RecomendacaoMTSS.rule_id == "MTSS_DIRECT_OVER_INDIRECT"))
    assert rec_gravada is not None
    assert rec_gravada.qti_agreement == "agree"


def test_nenhuma_recomendacao_afirma_erro_do_professor(db, aula_classificada):
    _, recs = interpretar(db, aula_classificada)
    assert recs
    for rec in recs:
        assert not re.search(r"\berrou\b|\bincorret|\bdeveria ter\b|\bfalhou\b", rec["text"])

    gravadas = db.scalars(select(RecomendacaoMTSS)
                          .where(RecomendacaoMTSS.aula_id == aula_classificada.id)).all()
    assert gravadas
    for g in gravadas:
        assert not re.search(r"\berrou\b|\bincorret|\bdeveria ter\b|\bfalhou\b", g.text)


def test_toda_interpretacao_tem_framing_reflection(db, aula_classificada):
    qualificadas, _ = interpretar(db, aula_classificada)
    assert qualificadas
    assert all(q["framing"] == "reflection" for q in qualificadas)

    gravadas = db.scalars(select(InterpretacaoMTSS)
                          .where(InterpretacaoMTSS.aula_id == aula_classificada.id)).all()
    assert gravadas
    assert all(g.framing == "reflection" for g in gravadas)
