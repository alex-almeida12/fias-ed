import math

from fias_ed_engine.indices import compute_indices
from fias_ed_engine.qti import aggregate
from fias_ed_engine.rules import load_rules
from fias_ed_engine.triangulation import triangulate

F = load_rules("fias_rules")
P = load_rules("pedagogical_rules")
Q = load_rules("qti_config")
IV = [2, 3, 5, 5, 8, 9, 7, 10]


def run(qti):
    return triangulate(IV, compute_indices(IV, F), qti, P, Q)


def test_pairs_with_qti():
    out = run(aggregate([{i: 3 for i in range(1, 25)}] * 10, Q))
    by = {p["pair_id"]: p for p in out}
    assert math.isclose(by["TRI_WARMTH"]["fias"]["value"], 2 / 8)
    assert math.isclose(by["TRI_INFLUENCE"]["fias"]["value"], 2 / 3)
    assert by["TRI_WARMTH"]["qti_available"] is True
    assert [q["label"] for q in by["TRI_WARMTH"]["qti"]] == ["Amigável", "Compreensivo"]
    assert math.isclose(by["TRI_WARMTH"]["qti"][0]["value"], 0.5)


def test_pairs_without_enough_qti():
    out = run(aggregate([{i: 3 for i in range(1, 25)}] * 3, Q))
    assert all(p["qti_available"] is False for p in out)
    assert all(q["value"] is None for p in out for q in p["qti"])


def test_no_verdict_fields():
    out = run(aggregate([], Q))
    for p in out:
        assert not {"verdict", "plane", "classification", "convergence"} & set(p)
