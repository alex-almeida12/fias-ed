import math

from fias_ed_engine.indices import category_counts, compute_indices
from fias_ed_engine.rules import load_rules

R = load_rules("fias_rules")


def test_counts_have_all_categories():
    c = category_counts([5, 5, 10])
    assert c[5] == 2 and c[10] == 1 and c[1] == 0 and set(c) == set(range(1, 11))


def test_proportions():
    iv = [1, 4, 5, 5, 8, 9, 10, 10]
    r = compute_indices(iv, R)
    assert math.isclose(r["TT"]["value"], 4 / 8)
    assert math.isclose(r["PT"]["value"], 2 / 8)
    assert math.isclose(r["SC"]["value"], 2 / 8)


def test_ratios():
    iv = [1, 4, 5, 5, 8, 9, 10, 10]
    r = compute_indices(iv, R)
    assert math.isclose(r["ID_RATIO"]["value"], 2 / 2)
    assert math.isclose(r["PIR"]["value"], 1 / 2)
    assert math.isclose(r["PUPIL_RESPONSE_RATIO"]["value"], 1 / 2)
    assert r["ID_RATIO"]["numerator_count"] == 2 and r["ID_RATIO"]["denominator_count"] == 2


def test_division_by_zero_is_null_with_reason():
    r = compute_indices([4, 4, 10], R)
    assert r["ID_RATIO"]["value"] is None and r["ID_RATIO"]["reason"] == "insufficient_data"
    assert r["PIR"]["value"] is None


def test_empty_lesson():
    r = compute_indices([], R)
    assert r["TT"]["value"] is None and r["TT"]["reason"] == "insufficient_data"


def test_disabled_indices_not_computed():
    r = compute_indices([1, 5], R)
    assert "TRR" not in r and "ID_REVISED" not in r and "I_A" not in r


def test_evidence_attached():
    r = compute_indices([1, 5, 8], R, n_segments=3, confidences=[0.9, 0.7, 0.8])
    ev = r["TT"]["evidence"]
    assert ev["n_intervals"] == 3 and ev["n_segments"] == 3 and math.isclose(ev["mean_confidence"], 0.8)
    assert r["TT"]["validation_status"] == "validated" and r["TT"]["source_reference"]
