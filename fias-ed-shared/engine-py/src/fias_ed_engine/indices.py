"""Índices FIAS fundamentados (apenas os habilitados em fias_rules.json)."""
from collections import Counter


def category_counts(intervals: list[int]) -> dict[int, int]:
    c = Counter(intervals)
    return {k: c.get(k, 0) for k in range(1, 11)}


def compute_indices(intervals: list[int], rules: dict, n_segments: int = 0,
                    confidences: list[float] | None = None) -> dict[str, dict]:
    counts = category_counts(intervals)
    total = len(intervals)
    mean_conf = sum(confidences) / len(confidences) if confidences else None
    out: dict[str, dict] = {}
    for idx in rules["indices"]:
        if not idx["enabled"]:
            continue
        num = sum(counts[c] for c in idx["numerator"])
        den = total if idx["denominator"] == "all" else sum(counts[c] for c in idx["denominator"])
        value = num / den if den > 0 else None
        out[idx["id"]] = {
            "id": idx["id"],
            "value": value,
            "reason": None if value is not None else "insufficient_data",
            "numerator_count": num,
            "denominator_count": den,
            "evidence": {"n_intervals": total, "n_segments": n_segments, "mean_confidence": mean_conf},
            "validation_status": idx["validation_status"],
            "source_reference": idx["source_reference"],
        }
    return out
