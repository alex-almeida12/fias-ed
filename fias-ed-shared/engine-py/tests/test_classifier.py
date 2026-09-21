import math

import pytest

from fias_ed_engine.classifier import constrain_by_role, divergence_rate, softmax
from fias_ed_engine.rules import load_rules

R = load_rules("fias_rules")


def logits_peak(cat, second=None):
    lg = [0.0] * 10
    lg[cat - 1] = 5.0
    if second:
        lg[second - 1] = 4.0
    return lg


def test_softmax_sums_to_one_and_stable():
    p = softmax([1000.0, 1000.0])
    assert math.isclose(sum(p), 1.0) and math.isclose(p[0], 0.5)


def test_teacher_raw_agrees():
    r = constrain_by_role(logits_peak(5), "PROFESSOR", R)
    assert r.pred_raw == 5 and r.pred_role_constrained == 5
    assert math.isclose(r.confidence, r.confidence_raw)


def test_teacher_constrained_away_from_student_category():
    r = constrain_by_role(logits_peak(8, second=3), "PROFESSOR", R)
    assert r.pred_raw == 8 and r.pred_role_constrained == 3
    assert r.confidence < r.confidence_raw


def test_student_constrained_to_8_or_9():
    r = constrain_by_role(logits_peak(5, second=9), "ALUNO", R)
    assert r.pred_role_constrained == 9


def test_uncertain_flag():
    r = constrain_by_role([0.0] * 10, "PROFESSOR", R)
    assert r.uncertain is True and math.isclose(r.confidence, 0.1)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        constrain_by_role([0.0] * 9, "PROFESSOR", R)
    with pytest.raises(ValueError):
        constrain_by_role([0.0] * 10, "SPEAKER_00", R)


def test_divergence_rate():
    a = constrain_by_role(logits_peak(5), "PROFESSOR", R)
    b = constrain_by_role(logits_peak(8, second=3), "PROFESSOR", R)
    assert divergence_rate([a, b]) == 0.5
    assert divergence_rate([]) is None
