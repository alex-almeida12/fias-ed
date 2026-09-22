from fias_ed_engine.indices import compute_indices
from fias_ed_engine.mtss import build_facts, evaluate, recommendations, select_evidence_segments
from fias_ed_engine.rules import load_rules
from fias_ed_engine.traceability import find_untraced

F = load_rules("fias_rules")
M = load_rules("mtss_rules")
P = load_rules("pedagogical_rules")


def facts(iv):
    return build_facts(iv, compute_indices(iv, F))


def ids(fired):
    return [f["rule_id"] for f in fired]


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
