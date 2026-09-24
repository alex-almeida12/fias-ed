import pytest

from fias_ed_engine.indices import compute_indices
from fias_ed_engine.mtss import build_facts, evaluate, qualify, recommendations, select_evidence_segments
from fias_ed_engine.rules import load_rules
from fias_ed_engine.traceability import find_untraced

F = load_rules("fias_rules")
M = load_rules("mtss_rules")
P = load_rules("pedagogical_rules")

DIVERGENCE_TEXT_WARMTH = (
    "O áudio registra pouco elogio verbal; os estudantes percebem proximidade — "
    "o que, além da fala, pode explicar essa diferença?"
)


def facts(iv):
    return build_facts(iv, compute_indices(iv, F))


def ids(fired):
    return [f["rule_id"] for f in fired]


def by_rule(qualified):
    return {q["rule_id"]: q for q in qualified}


def tri(pair_id, values, available=True):
    """Monta um par de triangulação sintético, só com o que `qualify` lê."""
    return {
        "pair_id": pair_id,
        "fias": {"kind": "categories", "ref": [], "value": None},
        "qti": [{"octant": oc, "label": oc, "value": v} for oc, v in values.items()],
        "qti_available": available,
        "reflection_question": f"pergunta padrão de {pair_id}",
        "source_reference": "teste",
        "validation_status": "engineering_decision",
    }


def with_pair(pair_id, values, available=True):
    """Triangulação completa (como `triangulate` sempre devolve, um item por
    par), com o par `pair_id` substituído pelos valores do teste. Os demais
    ficam com um valor neutro, só para existir — nenhum teste olha para eles."""
    neutral = {
        "TRI_WARMTH": {"oc2": 3.0, "oc3": 3.0},
        "TRI_INFLUENCE": {"oc1": 3.0, "oc8": 3.0},
        "TRI_STUDENT_VOICE": {"oc4": 3.0},
        "TRI_TENSION": {"oc6": 3.0, "oc7": 3.0},
    }
    return [tri(pid, values if pid == pair_id else v, available if pid == pair_id else True)
            for pid, v in neutral.items()]


def test_traced():
    assert find_untraced(M) == [] and find_untraced(P) == []


def test_every_recommendation_id_exists():
    known = {r["recommendation_id"] for r in P["recommendations"]}
    for r in M["rules"]:
        assert set(r["recommendation_ids"]) <= known, r["rule_id"]


def test_build_facts_modal_and_counts():
    f = facts([5, 5, 4, 8, 10])
    assert f["modal_teacher_category"] == 5 and f["count_cat_8"] == 1 and f["count_cat_9"] == 0
    assert f["ID_RATIO"] == 0.5


def test_modal_tie_takes_lowest_and_none_without_teacher():
    assert facts([4, 5])["modal_teacher_category"] == 4
    assert facts([8, 10])["modal_teacher_category"] is None


def test_expositive_lesson_fires_expected_rules():
    fired = evaluate(facts([5, 5, 5, 4, 8, 8, 10]), M)
    assert ids(fired) == ["MTSS_EXPOSITIVE_PREDOMINANCE", "MTSS_DIRECT_OVER_INDIRECT",
                          "MTSS_NO_STUDENT_INITIATIVE", "MTSS_NO_IDEA_UPTAKE", "MTSS_NO_PRAISE",
                          "MTSS_QUESTIONS_PRESENT"]
    assert fired[0]["evidence"]["count_cat_5"] == 3
    assert fired[0]["framing"] == "reflection"


def test_disabled_threshold_rules_never_fire():
    fired = evaluate(facts([5, 5, 5, 5, 8]), M)
    assert not any(r.startswith("MTSS_FU_") for r in ids(fired))


def test_none_fact_is_false():
    fired = evaluate(facts([4, 4, 10]), M)  # ID_RATIO None (sem cat. 5–7)
    assert "MTSS_DIRECT_OVER_INDIRECT" not in ids(fired)


def test_any_and_present_ops():
    rules = {"rules_version": "1.0.0", "rules": [{
        "rule_id": "MTSS_T", "rules_version": "1.0.0", "tier1_dimension": "x", "framing": "strength",
        "conditions": {"any": [{"fact": "PIR", "op": "present"}, {"fact": "count_cat_9", "op": "gt", "value": 5}]},
        "evidence": ["PIR"], "interpretation": "Este padrão pode indicar algo.", "recommendation_ids": [],
        "source_reference": "teste", "validation_status": "engineering_decision", "enabled": True}]}
    assert ids(evaluate(facts([8, 9]), rules)) == ["MTSS_T"]
    assert ids(evaluate(facts([4]), rules)) == []


def test_recommendations_dedup_in_order():
    fired = evaluate(facts([5, 5, 5, 4, 8, 8, 10]), M)
    recs = recommendations(fired, P)
    rid = [r["recommendation_id"] for r in recs]
    assert rid[0] == "PED_CHECK_UNDERSTANDING" and len(rid) == len(set(rid))
    assert all(r["validation_status"] == "draft_pending_researcher_review" for r in recs)


def test_select_evidence_segments():
    segs = [{"segment_id": "a", "start_ms": 0, "text": "x", "category": 5, "confidence": 0.6},
            {"segment_id": "b", "start_ms": 10, "text": "y", "category": 5, "confidence": 0.9},
            {"segment_id": "c", "start_ms": 20, "text": "z", "category": 4, "confidence": 0.99},
            {"segment_id": "d", "start_ms": 5, "text": "w", "category": 5, "confidence": 0.6}]
    assert [s["segment_id"] for s in select_evidence_segments(segs, 5, limit=2)] == ["b", "a"]


# --- qualify: qualificação de cada recomendação disparada à luz do QTI ---

FIRED_EXPOSITIVE = evaluate(facts([5, 5, 5, 4, 8, 8, 10]), M)


def test_qualify_rule_without_pair_is_unpaired():
    q = by_rule(qualify(FIRED_EXPOSITIVE, with_pair("TRI_WARMTH", {"oc2": 3.0, "oc3": 3.0}), P))
    assert q["MTSS_QUESTIONS_PRESENT"]["qti_agreement"] == "unpaired"
    assert q["MTSS_QUESTIONS_PRESENT"]["qti_evidence"] is None
    assert q["MTSS_QUESTIONS_PRESENT"]["divergence_question"] is None


def test_qualify_no_qti_available():
    triang = with_pair("TRI_WARMTH", {"oc2": 3.0, "oc3": 3.0}, available=False)
    q = by_rule(qualify(FIRED_EXPOSITIVE, triang, P))
    assert q["MTSS_NO_PRAISE"]["qti_agreement"] == "no_qti"
    assert q["MTSS_NO_PRAISE"]["qti_evidence"] is None
    assert q["MTSS_NO_PRAISE"]["divergence_question"] is None


def test_qualify_agrees_low_band():
    triang = with_pair("TRI_WARMTH", {"oc2": 2.0, "oc3": 2.0})
    q = by_rule(qualify(FIRED_EXPOSITIVE, triang, P))
    r = q["MTSS_NO_PRAISE"]
    assert r["qti_agreement"] == "agree"
    assert r["qti_evidence"]["pair_id"] == "TRI_WARMTH"
    assert r["qti_evidence"]["mean"] == 2.0
    assert r["divergence_question"] is None


def test_qualify_disagrees_high_band_and_asks_question():
    triang = with_pair("TRI_WARMTH", {"oc2": 4.0, "oc3": 4.0})
    q = by_rule(qualify(FIRED_EXPOSITIVE, triang, P))
    r = q["MTSS_NO_PRAISE"]
    assert r["qti_agreement"] == "disagree"
    assert r["divergence_question"] == DIVERGENCE_TEXT_WARMTH


def test_qualify_middle_band_is_inconclusive():
    triang = with_pair("TRI_WARMTH", {"oc2": 3.0, "oc3": 3.0})
    q = by_rule(qualify(FIRED_EXPOSITIVE, triang, P))
    r = q["MTSS_NO_PRAISE"]
    assert r["qti_agreement"] == "inconclusive"
    assert r["divergence_question"] is None


def test_qualify_reverses_direction_for_high_agrees_when():
    fired = evaluate(facts([7]), M)
    assert "MTSS_REACTIVE_MANAGEMENT_PRESENT" in ids(fired)
    triang = with_pair("TRI_TENSION", {"oc6": 4.0, "oc7": 4.0})
    q = by_rule(qualify(fired, triang, P))
    assert q["MTSS_REACTIVE_MANAGEMENT_PRESENT"]["qti_agreement"] == "agree"


def test_qualify_influence_ignores_oc1_leadership():
    triang = with_pair("TRI_INFLUENCE", {"oc1": 5.0, "oc8": 1.5})
    q = by_rule(qualify(FIRED_EXPOSITIVE, triang, P))
    r = q["MTSS_DIRECT_OVER_INDIRECT"]
    assert [o["octant"] for o in r["qti_evidence"]["octants"]] == ["oc8"]
    assert r["qti_evidence"]["mean"] == 1.5
    assert r["qti_agreement"] == "disagree"  # oc8 baixo, agrees_when é "high"


def test_qualify_band_edges_are_exclusive():
    low_edge = qualify(FIRED_EXPOSITIVE, with_pair("TRI_WARMTH", {"oc2": 2.33, "oc3": 2.33}), P)
    high_edge = qualify(FIRED_EXPOSITIVE, with_pair("TRI_WARMTH", {"oc2": 3.67, "oc3": 3.67}), P)
    assert by_rule(low_edge)["MTSS_NO_PRAISE"]["qti_agreement"] == "inconclusive"
    assert by_rule(high_edge)["MTSS_NO_PRAISE"]["qti_agreement"] == "inconclusive"


def test_qualify_does_not_mutate_fired():
    before = [dict(f) for f in FIRED_EXPOSITIVE]
    qualified = qualify(FIRED_EXPOSITIVE, with_pair("TRI_WARMTH", {"oc2": 2.0, "oc3": 2.0}), P)
    assert FIRED_EXPOSITIVE == before
    assert len(qualified) == len(FIRED_EXPOSITIVE)
    assert [q["rule_id"] for q in qualified] == ids(FIRED_EXPOSITIVE)


def test_qualify_falls_back_to_pair_question_when_map_entry_has_no_own():
    """MTSS_DIRECT_OVER_INDIRECT não tem divergence_question própria no mapa:
    em discordância, o texto devolvido tem que vir do par de triangulação."""
    triang = with_pair("TRI_INFLUENCE", {"oc1": 5.0, "oc8": 1.5})
    pair = next(p for p in triang if p["pair_id"] == "TRI_INFLUENCE")
    q = by_rule(qualify(FIRED_EXPOSITIVE, triang, P))
    r = q["MTSS_DIRECT_OVER_INDIRECT"]
    assert r["qti_agreement"] == "disagree"
    assert r["divergence_question"] == pair["reflection_question"]


def test_qualify_prefers_own_divergence_question_over_pair():
    """MTSS_NO_PRAISE tem divergence_question própria no mapa: em discordância,
    o texto tem que vir da entrada do mapa, não do par — e essa entrada
    reconhece que o FIAS capta só comportamento verbal."""
    triang = with_pair("TRI_WARMTH", {"oc2": 4.0, "oc3": 4.0})
    q = by_rule(qualify(FIRED_EXPOSITIVE, triang, P))
    r = q["MTSS_NO_PRAISE"]
    mapping = next(m for m in P["recommendation_qualification"]["map"] if m["rule_id"] == "MTSS_NO_PRAISE")
    assert r["qti_agreement"] == "disagree"
    assert r["divergence_question"] == mapping["divergence_question"]
    assert "além da fala" in r["divergence_question"]


def test_qualification_map_is_consistent_with_rules_and_pairs():
    """Teste estático (não chama `qualify`): todo par citado no mapa existe,
    toda rule_id existe e está habilitada em mtss_rules, e todo octante citado
    existe nos qti_octants do par apontado — no mesmo espírito de
    `test_every_recommendation_id_exists`."""
    known_pair_ids = {p["pair_id"] for p in P["triangulation_pairs"]}
    pairs_by_id = {p["pair_id"]: p for p in P["triangulation_pairs"]}
    enabled_rule_ids = {r["rule_id"] for r in M["rules"] if r["enabled"]}
    for m in P["recommendation_qualification"]["map"]:
        assert m["pair_id"] in known_pair_ids, m["rule_id"]
        assert m["rule_id"] in enabled_rule_ids, m["rule_id"]
        assert set(m["octants"]) <= set(pairs_by_id[m["pair_id"]]["qti_octants"]), m["rule_id"]


@pytest.mark.parametrize("mapping", P["recommendation_qualification"]["map"], ids=lambda m: m["rule_id"])
def test_qualify_agreement_direction_for_every_map_entry(mapping):
    """Percorre as seis entradas do mapa (lidas de P, não copiadas à mão) e
    confirma que um QTI na faixa agrees_when produz "agree" e a faixa oposta
    produz "disagree". A triangulação é montada a partir dos octants e do
    pair_id da própria entrada, para continuar valendo se o mapa crescer.

    O que ele prova: que a lógica de comparação de faixa dentro de `qualify`
    (band == agrees_when → agree, senão disagree) está correta para cada uma
    das seis entradas — protege contra regressão nessa lógica.

    O que ele NÃO prova: que o valor de `agrees_when` de cada entrada é o
    certo. A expectativa de qual faixa deve dar "agree" é derivada do próprio
    `mapping["agrees_when"]` que está sendo exercitado — se esse valor
    estiver errado no arquivo, o teste calcula a expectativa errada também, e
    as duas erradas concordam. Um erro de digitação em `agrees_when` (ex.:
    "low" trocado por "high") não é pego aqui; ver
    `test_qualification_map_matches_researcher_decision_table` para a guarda
    que cobre exatamente isso."""
    bands = P["recommendation_qualification"]["qti_bands"]
    low_value = bands["low_below"] - 0.5
    high_value = bands["high_above"] + 0.5
    fired = [{"rule_id": mapping["rule_id"]}]

    low_values = {oc: low_value for oc in mapping["octants"]}
    high_values = {oc: high_value for oc in mapping["octants"]}

    low_result = by_rule(qualify(fired, with_pair(mapping["pair_id"], low_values), P))[mapping["rule_id"]]
    high_result = by_rule(qualify(fired, with_pair(mapping["pair_id"], high_values), P))[mapping["rule_id"]]

    agree_result = high_result if mapping["agrees_when"] == "high" else low_result
    disagree_result = low_result if mapping["agrees_when"] == "high" else high_result

    assert agree_result["qti_agreement"] == "agree"
    assert disagree_result["qti_agreement"] == "disagree"


def test_qualification_map_matches_researcher_decision_table():
    """Guarda mecânica de uma decisão do pesquisador (docs/ESTADO_DE_VALIDACAO.md
    seção 4.4, docs/PROMPT_MESTRE.md seção 80): as seis direções abaixo não
    mudam sem decisão nova dele.

    Isto é deliberadamente duplicação do arquivo de regras — a tabela está
    escrita à mão aqui, não relida de `P`. Um teste que lê `pedagogical_rules.json`
    para conferir `pedagogical_rules.json` não protege decisão nenhuma (é o
    que `test_qualify_agreement_direction_for_every_map_entry`, acima, admite
    não fazer). Este protege, porque a expectativa mora fora do dado: se o
    arquivo mudar, este teste não muda junto — ele falha.

    Note TRI_INFLUENCE → ["oc8"]: oc1 (Liderança) fica de fora de propósito,
    por efeito de teto (mesma seção 4.4 de ESTADO_DE_VALIDACAO.md). Quem
    "consertar" MTSS_DIRECT_OVER_INDIRECT achando que falta oc1 vai derrubar
    este teste — de propósito, porque essa mudança precisa passar por uma
    decisão nova do pesquisador, não por um ajuste silencioso de código."""
    expected = {
        "MTSS_NO_PRAISE": ("TRI_WARMTH", ["oc2", "oc3"], "low"),
        "MTSS_NO_IDEA_UPTAKE": ("TRI_WARMTH", ["oc2", "oc3"], "low"),
        "MTSS_REACTIVE_MANAGEMENT_PRESENT": ("TRI_TENSION", ["oc7", "oc6"], "high"),
        "MTSS_NO_STUDENT_INITIATIVE": ("TRI_STUDENT_VOICE", ["oc4"], "low"),
        "MTSS_STUDENT_INITIATIVE_PRESENT": ("TRI_STUDENT_VOICE", ["oc4"], "high"),
        "MTSS_DIRECT_OVER_INDIRECT": ("TRI_INFLUENCE", ["oc8"], "high"),
    }
    actual = {
        m["rule_id"]: (m["pair_id"], m["octants"], m["agrees_when"])
        for m in P["recommendation_qualification"]["map"]
    }
    assert actual == expected
