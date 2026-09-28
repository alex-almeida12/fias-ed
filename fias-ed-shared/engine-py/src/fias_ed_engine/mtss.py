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


def qualify(fired: list[dict], triangulation: list[dict], pedagogical: dict) -> list[dict]:
    """Qualifica cada regra disparada à luz do QTI, sem alterar o que a disparou.

    As regras continuam sendo decididas pelo FIAS. Isto só acrescenta a leitura
    dos estudantes ao lado, e só onde regra e par de triangulação compartilham
    um fato. O corte em faixas existe apenas do lado do QTI: do lado do FIAS a
    própria condição da regra já classificou, com referência à literatura.
    """
    qual = pedagogical["recommendation_qualification"]
    bands = qual["qti_bands"]
    low_below, high_above = bands["low_below"], bands["high_above"]
    by_rule = {m["rule_id"]: m for m in qual["map"]}
    by_pair = {p["pair_id"]: p for p in triangulation}

    out = []
    for f in fired:
        item = dict(f)
        mapping = by_rule.get(f["rule_id"])
        if mapping is None:
            item["qti_agreement"] = "unpaired"
            item["qti_evidence"] = None
            item["divergence_question"] = None
            out.append(item)
            continue

        pair = by_pair[mapping["pair_id"]]
        if not pair["qti_available"]:
            item["qti_agreement"] = "no_qti"
            item["qti_evidence"] = None
            item["divergence_question"] = None
            out.append(item)
            continue

        octants = [q for q in pair["qti"] if q["octant"] in mapping["octants"]]
        mean = sum(o["value"] for o in octants) / len(octants)
        if mean < low_below:
            band = "low"
        elif mean > high_above:
            band = "high"
        else:
            band = None  # faixa média: inconclusivo

        if band is None:
            agreement = "inconclusive"
        elif band == mapping["agrees_when"]:
            agreement = "agree"
        else:
            agreement = "disagree"

        item["qti_agreement"] = agreement
        item["qti_evidence"] = {"pair_id": mapping["pair_id"], "octants": octants, "mean": mean}
        item["divergence_question"] = (
            mapping.get("divergence_question", pair["reflection_question"])
            if agreement == "disagree" else None
        )
        out.append(item)
    return out


def select_evidence_segments(segments: list[dict], category: int, limit: int = 3) -> list[dict]:
    """Escolhe até `limit` segmentos de evidência para uma categoria FIAS.

    `segments` é uma lista de dicionários com as chaves `category` (a
    categoria FIAS já atribuída ao segmento, ex. a partir de
    `ClassificacaoFIAS.pred_role_constrained` resolvida pelo chamador) e
    `confidence` (a confiança dessa classificação), além de `start_ms` para
    o desempate. Isso é distinto de outras estruturas de segmento usadas
    alhures no motor (ex. `export.py`, `classifier.py`), que carregam
    `pred_role_constrained`/`pred_raw` em vez de `category`; é
    responsabilidade de quem chama esta função mapear `pred_role_constrained`
    para `category` antes de passar os segmentos aqui. Ver `MTSS.md`.
    """
    chosen = [s for s in segments if s["category"] == category]
    chosen.sort(key=lambda s: (-s["confidence"], s["start_ms"]))
    return chosen[:limit]
