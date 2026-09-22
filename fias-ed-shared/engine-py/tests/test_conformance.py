import json
import math

import pytest

from fias_ed_engine.classifier import constrain_by_role
from fias_ed_engine.indices import compute_indices
from fias_ed_engine.intervals import CodedSegment, segments_to_intervals, transition_matrix
from fias_ed_engine.mtss import build_facts, evaluate
from fias_ed_engine.paths import CONFORMANCE_DIR
from fias_ed_engine.qti import aggregate, score_response
from fias_ed_engine.rules import load_rules
from fias_ed_engine.triangulation import triangulate

F, Q, M, P = (load_rules(n) for n in ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules"))


def _ik(a):
    return {int(k): v for k, v in a.items()}


def run(fn, i):
    if fn == "segments_to_intervals":
        return segments_to_intervals([CodedSegment(**s) for s in i["segments"]], i["total_ms"], F)
    if fn == "transition_matrix":
        return transition_matrix(i["intervals"], F)
    if fn == "compute_indices":
        r = compute_indices(i["intervals"], F, i["n_segments"], i["confidences"])
        return {k: {f: v[f] for f in ("value", "reason", "numerator_count", "denominator_count")} for k, v in r.items()}
    if fn == "constrain_by_role":
        r = constrain_by_role(i["logits"], i["role"], F)
        return {"pred_raw": r.pred_raw, "pred_role_constrained": r.pred_role_constrained,
                "confidence_raw": r.confidence_raw, "confidence": r.confidence, "uncertain": r.uncertain}
    if fn == "score_response":
        return score_response(_ik(i["answers"]), Q)
    if fn == "aggregate_qti":
        return aggregate([_ik(r) for r in i["responses"]], Q)
    if fn == "evaluate_mtss":
        return [f["rule_id"] for f in evaluate(build_facts(i["intervals"], compute_indices(i["intervals"], F)), M)]
    if fn == "triangulate":
        iv = i["intervals"]
        tri = triangulate(iv, compute_indices(iv, F), aggregate([_ik(r) for r in i["qti_responses"]], Q), P, Q)
        return [{"pair_id": t["pair_id"], "fias_value": t["fias"]["value"], "qti_available": t["qti_available"],
                 "qti_values": [q["value"] for q in t["qti"]]} for t in tri]
    raise AssertionError(f"função desconhecida {fn}")


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, abs_tol=1e-9)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


CASES = [(p.stem, c) for p in sorted((CONFORMANCE_DIR / "cases").glob("*.json"))
         for c in json.loads(p.read_text(encoding="utf-8"))["cases"]]


def test_cases_exist_for_every_function():
    fns = {c["function"] for _, c in CASES}
    assert fns == {"segments_to_intervals", "transition_matrix", "compute_indices", "constrain_by_role",
                   "score_response", "aggregate_qti", "evaluate_mtss", "triangulate"}


@pytest.mark.parametrize("group,case", CASES, ids=[c["id"] for _, c in CASES])
def test_case(group, case):
    assert same(run(case["function"], case["input"]), case["expected"])


def test_cases_rules_version_matches():
    for p in (CONFORMANCE_DIR / "cases").glob("*.json"):
        assert json.loads(p.read_text(encoding="utf-8"))["rules_version"] == F["rules_version"]
