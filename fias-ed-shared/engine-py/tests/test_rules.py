import copy

import jsonschema
import pytest

from fias_ed_engine.rules import load_rules
from fias_ed_engine.traceability import find_untraced


def test_fias_rules_valid_and_versioned():
    r = load_rules("fias_rules")
    assert r["rules_version"] == "2.0.0"
    assert [c["id"] for c in r["categories"]] == list(range(1, 11))


def test_groups_match_cap4():
    r = load_rules("fias_rules")
    by = {c["id"]: c for c in r["categories"]}
    assert {i for i in by if by[i]["influence"] == "indirect"} == {1, 2, 3, 4}
    assert {i for i in by if by[i]["influence"] == "direct"} == {5, 6, 7}
    assert {i for i in by if by[i]["group"] == "student"} == {8, 9}
    assert by[10]["group"] == "silence"


def test_pending_indices_are_disabled():
    r = load_rules("fias_rules")
    for idx in r["indices"]:
        if idx["validation_status"] == "PENDING_SCIENTIFIC_VALIDATION":
            assert idx["enabled"] is False, idx["id"]


def test_enabled_index_requires_formula():
    r = copy.deepcopy(load_rules("fias_rules"))
    bad = next(i for i in r["indices"] if i["id"] == "TRR")
    bad["enabled"] = True
    from fias_ed_engine.rules import validate
    with pytest.raises(jsonschema.ValidationError):
        validate("fias_rules", r)


def test_everything_traced():
    assert find_untraced(load_rules("fias_rules")) == []


def test_find_untraced_detects_missing():
    assert find_untraced({"indices": [{"id": "X", "validation_status": "validated"}]}) == ["$.indices[0]"]
    assert find_untraced({"a": {"source_reference": "ok", "validation_status": "bogus"}}) == ["$.a"]
