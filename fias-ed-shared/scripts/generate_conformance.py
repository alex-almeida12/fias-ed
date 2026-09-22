"""Gera conformance/cases/*.json a partir de entradas definidas aqui e do motor de referência."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.classifier import constrain_by_role  # noqa: E402
from fias_ed_engine.indices import compute_indices  # noqa: E402
from fias_ed_engine.intervals import CodedSegment, segments_to_intervals, transition_matrix  # noqa: E402
from fias_ed_engine.mtss import build_facts, evaluate  # noqa: E402
from fias_ed_engine.paths import CONFORMANCE_DIR  # noqa: E402
from fias_ed_engine.qti import aggregate, score_response  # noqa: E402
from fias_ed_engine.rules import load_rules  # noqa: E402
from fias_ed_engine.triangulation import triangulate  # noqa: E402

F, Q, M, P = (load_rules(n) for n in ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules"))


def ans(fn):
    return {str(i): fn(i) for i in range(1, 25)}


def to_int_keys(a):
    return {int(k): v for k, v in a.items()}


SEGMENT_CASES = [
    ("seg-empty", "Áudio sem fala vira silêncio", [], 9000),
    ("seg-partial-last", "Último intervalo parcial conta", [], 7000),
    ("seg-largest", "Maior cobertura vence", [(0, 1000, 5), (1000, 3000, 4)], 3000),
    ("seg-tie", "Empate: segmento que começa antes", [(0, 1500, 5), (1500, 3000, 8)], 3000),
    ("seg-span", "Segmento cobrindo vários intervalos", [(500, 7000, 5)], 9000),
    ("seg-gap", "Intervalo sem fala = 10", [(0, 3000, 4), (6000, 9000, 8)], 9000),
    ("seg-unsorted", "Entrada fora de ordem", [(6000, 9000, 8), (0, 3000, 4)], 9000),
]
INTERVAL_SEQS = [
    ("lesson-expositive", [5, 5, 5, 4, 8, 8, 10]),
    ("lesson-dialogic", [4, 8, 3, 9, 2, 4, 8, 3, 10]),
    ("lesson-teacher-only-indirect", [4, 4, 10]),
    ("lesson-empty", []),
    ("lesson-reactive", [5, 7, 6, 7, 8, 10]),
    ("lesson-instructions-predominance", [6, 6, 6, 8, 10]),
    ("lesson-tie-5-6", [5, 6, 8, 10]),
]
LOGIT_CASES = [
    ("role-agree", [0, 0, 0, 0, 5, 0, 0, 0, 0, 0], "PROFESSOR"),
    ("role-teacher-diverge", [0, 0, 4, 0, 0, 0, 0, 5, 0, 0], "PROFESSOR"),
    ("role-student-diverge", [0, 0, 0, 0, 5, 0, 0, 0, 4, 0], "ALUNO"),
    ("role-flat-uncertain", [0.0] * 10, "PROFESSOR"),
]
QTI_ANSWERS = [
    ("qti-all-1", ans(lambda i: 1)),
    ("qti-all-5", ans(lambda i: 5)),
    ("qti-all-3", ans(lambda i: 3)),
    ("qti-only-oc1", ans(lambda i: 5 if i in (1, 9, 17) else 1)),
    ("qti-only-oc6", ans(lambda i: 5 if i in (6, 14, 22) else 1)),
    ("qti-spss-hand", ans(lambda i: {1: 5, 2: 3, 3: 2, 4: 1, 5: 1, 6: 2, 7: 3, 8: 5}[(i - 1) % 8 + 1])),
]


def main() -> None:
    out_dir = CONFORMANCE_DIR / "cases"
    out_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list] = {k: [] for k in ("intervals", "matrix", "indices", "classifier", "qti", "mtss", "triangulation")}
    for cid, desc, segs, total in SEGMENT_CASES:
        inp = {"segments": [{"start_ms": a, "end_ms": b, "category": c} for a, b, c in segs], "total_ms": total}
        exp = segments_to_intervals([CodedSegment(a, b, c) for a, b, c in segs], total, F)
        groups["intervals"].append({"id": cid, "function": "segments_to_intervals", "description": desc, "input": inp, "expected": exp})
    for cid, iv in INTERVAL_SEQS:
        groups["matrix"].append({"id": f"matrix-{cid}", "function": "transition_matrix", "description": cid, "input": {"intervals": iv}, "expected": transition_matrix(iv, F)})
        idx = compute_indices(iv, F, n_segments=len(iv), confidences=[0.8] * len(iv))
        groups["indices"].append({"id": f"indices-{cid}", "function": "compute_indices", "description": cid,
            "input": {"intervals": iv, "n_segments": len(iv), "confidences": [0.8] * len(iv)},
            "expected": {k: {f: v[f] for f in ("value", "reason", "numerator_count", "denominator_count")} for k, v in idx.items()}})
        fired = evaluate(build_facts(iv, compute_indices(iv, F)), M)
        groups["mtss"].append({"id": f"mtss-{cid}", "function": "evaluate_mtss", "description": cid, "input": {"intervals": iv}, "expected": [f["rule_id"] for f in fired]})
    for cid, lg, role in LOGIT_CASES:
        r = constrain_by_role(lg, role, F)
        groups["classifier"].append({"id": cid, "function": "constrain_by_role", "description": cid, "input": {"logits": lg, "role": role},
            "expected": {"pred_raw": r.pred_raw, "pred_role_constrained": r.pred_role_constrained, "confidence_raw": r.confidence_raw, "confidence": r.confidence, "uncertain": r.uncertain}})
    for cid, a in QTI_ANSWERS:
        groups["qti"].append({"id": cid, "function": "score_response", "description": cid, "input": {"answers": a}, "expected": score_response(to_int_keys(a), Q)})
    for cid, n in (("qti-agg-below-min", 3), ("qti-agg-min", 10)):
        responses = [QTI_ANSWERS[2][1]] * (n - 1) + [QTI_ANSWERS[3][1]]
        groups["qti"].append({"id": cid, "function": "aggregate_qti", "description": cid, "input": {"responses": responses},
            "expected": aggregate([to_int_keys(r) for r in responses], Q)})
    for cid, iv in INTERVAL_SEQS[:2]:
        for qn in (3, 10):
            responses = [QTI_ANSWERS[2][1]] * qn
            tri = triangulate(iv, compute_indices(iv, F), aggregate([to_int_keys(r) for r in responses], Q), P, Q)
            groups["triangulation"].append({"id": f"tri-{cid}-{qn}", "function": "triangulate", "description": f"{cid} com {qn} respostas QTI",
                "input": {"intervals": iv, "qti_responses": responses},
                "expected": [{"pair_id": t["pair_id"], "fias_value": t["fias"]["value"], "qti_available": t["qti_available"], "qti_values": [q["value"] for q in t["qti"]]} for t in tri]})
    meta = {"rules_version": F["rules_version"]}
    for name, cases in groups.items():
        (out_dir / f"{name}.json").write_text(json.dumps({**meta, "cases": cases}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {len(cases)} casos")


if __name__ == "__main__":
    main()
