import math
import subprocess
import sys

import pytest

from fias_ed_engine.paths import SHARED_ROOT, qti_system_dir
from fias_ed_engine.qti import IncompleteResponseError, QtiImportError, aggregate, parse_export_csv, score_response
from fias_ed_engine.rules import load_rules
from fias_ed_engine.traceability import find_untraced

CFG = load_rules("qti_config")
A, B = 0.923880, 0.382683


def all_(v):
    return {i: v for i in range(1, 25)}


def where(orders, v, rest):
    return {i: (v if i in orders else rest) for i in range(1, 25)}


def test_config_shape_and_trace():
    assert len(CFG["items"]) == 24
    assert CFG["items"][0]["text_pt_br"] == "sabe conduzir bem a turma"
    assert {o["code"]: o["label_pt_br"] for o in CFG["octants"]}["oc7"] == "Irritável"
    assert find_untraced(CFG) == []


@pytest.mark.skipif(not qti_system_dir().exists(), reason="sistema QTI indisponível")
def test_config_identical_to_frozen_source():
    r = subprocess.run([sys.executable, str(SHARED_ROOT / "scripts" / "extract_qti.py"), "--check"])
    assert r.returncode == 0


def test_octants_extremes():
    assert all(v == 0 for v in score_response(all_(1), CFG)["octants"].values())
    assert all(v == 1 for v in score_response(all_(5), CFG)["octants"].values())
    assert all(math.isclose(v, 0.5) for v in score_response(all_(3), CFG)["octants"].values())


def test_oc1_mixed():
    ans = all_(1) | {1: 5, 9: 4, 17: 3}
    s = score_response(ans, CFG)
    assert math.isclose(s["octants"]["oc1"], 0.75) and s["octants"]["oc2"] == 0


def test_neutral_profile_dimensions_zero():
    s = score_response(all_(3), CFG)
    assert abs(s["agency"]) < 1e-12 and abs(s["communion"]) < 1e-12


def test_only_oc1():
    s = score_response(where([1, 9, 17], 5, 1), CFG)
    assert math.isclose(s["agency"], B * A, abs_tol=1e-12)
    assert math.isclose(s["communion"], B * B, abs_tol=1e-12)


def test_only_oc6():
    s = score_response(where([6, 14, 22], 5, 1), CFG)
    assert math.isclose(s["agency"], -B * B, abs_tol=1e-12)
    assert math.isclose(s["communion"], -B * A, abs_tol=1e-12)


def test_hand_computed_spss_case():
    lik = {1: 5, 2: 3, 3: 2, 4: 1, 5: 1, 6: 2, 7: 3, 8: 5}
    ans = {i: lik[(i - 1) % 8 + 1] for i in range(1, 25)}
    s = score_response(ans, CFG)
    exp_ag = B * (A * 1 + B * 0.5 - B * 0.25 - A * 0 - A * 0 - B * 0.25 + B * 0.5 + A * 1)
    exp_co = B * (B * 1 + A * 0.5 + A * 0.25 + B * 0 - B * 0 - A * 0.25 - A * 0.5 - B * 1)
    assert math.isclose(s["agency"], exp_ag, abs_tol=1e-12)
    assert math.isclose(s["communion"], exp_co, abs_tol=1e-12)


def test_incomplete_rejected():
    ans = all_(2)
    del ans[13]
    with pytest.raises(IncompleteResponseError):
        score_response(ans, CFG)
    with pytest.raises(IncompleteResponseError):
        score_response(all_(2) | {3: 6}, CFG)


def test_aggregate_mean_and_threshold():
    agg = aggregate([all_(1), all_(5)], CFG)
    assert agg["response_count"] == 2 and agg["displayable"] is False
    assert math.isclose(agg["octants"]["oc3"], 0.5)
    agg10 = aggregate([all_(3)] * 10, CFG)
    assert agg10["displayable"] is True


def test_aggregate_empty():
    agg = aggregate([], CFG)
    assert agg == {"response_count": 0, "displayable": False,
                   "octants": {o["code"]: None for o in CFG["octants"]},
                   "agency": None, "communion": None}


def _csv(rows, with_scores=True):
    head = ["response_id", "discipline"] + [f"q{i}" for i in range(1, 25)]
    if with_scores:
        head += [f"oc{i}" for i in range(1, 9)] + ["agency", "communion"]
    lines = [",".join(head)]
    for rid, ans in rows:
        vals = [rid, "Matemática"] + [str(ans[i]) for i in range(1, 25)]
        if with_scores:
            s = score_response(ans, CFG)
            vals += [repr(s["octants"][f"oc{i}"]) for i in range(1, 9)] + [repr(s["agency"]), repr(s["communion"])]
        lines.append(",".join(vals))
    return "\n".join(lines) + "\n"


def test_parse_export_roundtrip():
    rows = [("r1", all_(3)), ("r2", where([1, 9, 17], 5, 1))]
    parsed = parse_export_csv(_csv(rows), CFG)
    assert parsed == [all_(3), where([1, 9, 17], 5, 1)]


def test_parse_export_without_score_columns():
    assert parse_export_csv(_csv([("r1", all_(4))], with_scores=False), CFG) == [all_(4)]


def test_parse_export_detects_tampered_scores():
    text = _csv([("r1", all_(3))]).replace(",0.5,", ",0.9,", 1)
    with pytest.raises(QtiImportError):
        parse_export_csv(text, CFG)


def test_parse_export_missing_column():
    text = _csv([("r1", all_(3))], with_scores=False).replace("q24", "qX")
    with pytest.raises(QtiImportError):
        parse_export_csv(text, CFG)
