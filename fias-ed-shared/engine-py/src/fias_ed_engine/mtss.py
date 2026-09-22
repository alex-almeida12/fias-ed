"""MTSS Tier 1 descritivo: fatos da aula, avaliação de regras, sugestões e trechos de evidência."""
from .indices import category_counts

_OPS = {
    "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b,
}


def build_facts(intervals: list[int], indices: dict[str, dict]) -> dict:
    counts = category_counts(intervals)
    facts: dict = {f"count_cat_{k}": v for k, v in counts.items()}
    teacher = [(counts[c], -c) for c in range(1, 8) if counts[c] > 0]
    facts["modal_teacher_category"] = -max(teacher)[1] if teacher else None
    for idx_id, res in indices.items():
        facts[idx_id] = res["value"]
    return facts


def _holds(cond: dict, facts: dict) -> bool:
    if "all" in cond:
        return all(_holds(c, facts) for c in cond["all"])
    if "any" in cond:
        return any(_holds(c, facts) for c in cond["any"])
    value = facts.get(cond["fact"])
    if cond["op"] == "present":
        return value is not None
    if cond["op"] == "absent":
        return value is None
    return value is not None and _OPS[cond["op"]](value, cond["value"])


def evaluate(facts: dict, mtss_rules: dict) -> list[dict]:
    fired = []
    for r in mtss_rules["rules"]:
        if not r["enabled"] or not _holds(r["conditions"], facts):
            continue
        fired.append({
            "rule_id": r["rule_id"],
            "tier1_dimension": r["tier1_dimension"],
            "framing": r["framing"],
            "interpretation": r["interpretation"],
            "recommendation_ids": list(r["recommendation_ids"]),
            "evidence": {e: facts.get(e) for e in r["evidence"] if not e.startswith("segments:")},
            "evidence_segment_categories": [int(e.split("=")[1]) for e in r["evidence"] if e.startswith("segments:category=")],
            "source_reference": r["source_reference"],
            "validation_status": r["validation_status"],
            "rules_version": r["rules_version"],
        })
    return fired


def recommendations(fired: list[dict], pedagogical: dict) -> list[dict]:
    by_id = {r["recommendation_id"]: r for r in pedagogical["recommendations"]}
    out, seen = [], set()
    for f in fired:
        for rid in f["recommendation_ids"]:
            if rid in seen:
                continue
            seen.add(rid)
            r = by_id[rid]
            out.append({"recommendation_id": rid, "rule_id": f["rule_id"], "text": r["text"],
                        "validation_status": r["validation_status"], "source_reference": r["source_reference"]})
    return out


def select_evidence_segments(segments: list[dict], category: int, limit: int = 3) -> list[dict]:
    chosen = [s for s in segments if s["category"] == category]
    chosen.sort(key=lambda s: (-s["confidence"], s["start_ms"]))
    return chosen[:limit]
