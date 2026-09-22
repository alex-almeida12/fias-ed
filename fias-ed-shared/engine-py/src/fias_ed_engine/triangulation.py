"""Triangulação FIAS × QTI: justaposição de evidências, sem classificação automática."""
from .indices import category_counts


def triangulate(intervals: list[int], indices: dict[str, dict], qti_result: dict,
                pedagogical: dict, qti_cfg: dict) -> list[dict]:
    counts = category_counts(intervals)
    total = len(intervals)
    labels = {o["code"]: o["label_pt_br"] for o in qti_cfg["octants"]}
    available = bool(qti_result.get("displayable"))
    out = []
    for pair in pedagogical["triangulation_pairs"]:
        if "index" in pair["fias"]:
            ref = pair["fias"]["index"]
            fias = {"kind": "index", "ref": ref, "value": indices.get(ref, {}).get("value")}
        else:
            cats = pair["fias"]["categories"]
            value = sum(counts[c] for c in cats) / total if total else None
            fias = {"kind": "categories", "ref": cats, "value": value}
        qti = [{"octant": oc, "label": labels[oc],
                "value": qti_result["octants"][oc] if available else None}
               for oc in pair["qti_octants"]]
        out.append({"pair_id": pair["pair_id"], "fias": fias, "qti": qti, "qti_available": available,
                    "reflection_question": pair["reflection_question"],
                    "source_reference": pair["source_reference"],
                    "validation_status": pair["validation_status"]})
    return out
