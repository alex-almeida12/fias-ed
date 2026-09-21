"""Verifica que todo objeto científico declara fonte e status de validação."""
from typing import Any

STATUSES = {"validated", "PENDING_SCIENTIFIC_VALIDATION",
            "engineering_decision", "draft_pending_researcher_review"}
_MARKERS = ("source_reference", "validation_status", "rule_id")


def _needs_trace(obj: dict, in_list: bool) -> bool:
    return any(k in obj for k in _MARKERS) or (in_list and "id" in obj)


def find_untraced(obj: Any, path: str = "$", in_list: bool = False) -> list[str]:
    bad: list[str] = []
    if isinstance(obj, dict):
        if _needs_trace(obj, in_list):
            ok = (isinstance(obj.get("source_reference"), str)
                  and len(obj["source_reference"].strip()) >= 3
                  and obj.get("validation_status") in STATUSES)
            if not ok:
                bad.append(path)
        for k, v in obj.items():
            bad += find_untraced(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += find_untraced(v, f"{path}[{i}]", in_list=True)
    return bad
