"""Exportação do dataset de uma ou mais aulas (JSON e ZIP de CSVs). Sem áudio, sem texto por padrão."""
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from .indices import compute_indices
from .intervals import CodedSegment, segments_to_intervals, transition_matrix
from .mtss import build_facts, evaluate, recommendations
from .qti import aggregate
from .rules import load_rules
from .triangulation import triangulate

EXPORT_VERSION = "1.0.0"
TABLES = ("lessons", "segments", "intervals", "matrix", "indices", "qti_responses",
          "qti_results", "mtss", "recommendations", "triangulation")
_LESSON_FIELDS = ("lesson_id", "lesson_date", "disciplina", "turma_id", "duration_ms", "transcript_source")
_SEGMENT_FIELDS = ("segment_id", "start_ms", "end_ms", "role", "pred_raw", "pred_role_constrained", "confidence", "uncertain")
_PROCESSING_FIELDS = ("app_version", "fias_model", "fias_model_hash", "asr_model", "asr_model_hash", "diarization_model")

# Colunas fixas por tabela do CSV, na ordem em que o cabeçalho é escrito —
# sempre as mesmas colunas, com ou sem linhas, para que Web e Android
# exportem arquivos byte-idênticos dado o mesmo dataset (ver DATABASE_MODEL.md).
TABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "lessons": ("lesson_id", *_LESSON_FIELDS[1:], "n_segments", "n_intervals", "rules_version"),
    "segments": ("lesson_id", *_SEGMENT_FIELDS, "text_pseudonymized"),
    "intervals": ("lesson_id", "interval_index", "start_ms", "category"),
    "matrix": ("lesson_id", "from_category", "to_category", "count"),
    "indices": ("lesson_id", "index_id", "value", "reason", "numerator_count", "denominator_count", "validation_status"),
    "qti_responses": ("lesson_id", "response_index", *(f"q{i}" for i in range(1, 25))),
    "qti_results": ("lesson_id", "response_count", "displayable", *(f"oc{i}" for i in range(1, 9)), "agency", "communion"),
    "mtss": ("lesson_id", "rule_id", "tier1_dimension", "framing", "validation_status", "rules_version"),
    "recommendations": ("lesson_id", "recommendation_id", "rule_id", "validation_status"),
    "triangulation": ("lesson_id", "pair_id", "fias_value", "qti_available", "qti_values"),
}


class ExportPrivacyError(ValueError):
    pass


def build_dataset(lessons: list[dict], include_text: bool, exported_at: str) -> dict:
    if not lessons:
        raise ValueError("Nenhuma aula selecionada para exportação.")
    F, Q, M, P = (load_rules(n) for n in ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules"))
    step = int(F["coding"]["interval_seconds"] * 1000)
    ds: dict = {t: [] for t in TABLES}
    processing = []
    for item in lessons:
        meta, segs = item["lesson"], item["segments"]
        lid = meta["lesson_id"]
        if include_text and any(not s.get("text_pseudonymized") for s in segs):
            raise ExportPrivacyError(f"Aula {lid}: há falas sem versão pseudonimizada; exportação com texto recusada.")
        coded = [CodedSegment(s["start_ms"], s["end_ms"], s["pred_role_constrained"]) for s in segs]
        intervals = segments_to_intervals(coded, meta["duration_ms"], F)
        indices = compute_indices(intervals, F, n_segments=len(segs), confidences=[s["confidence"] for s in segs])
        answers = [{int(k): v for k, v in r.items()} for r in item["qti_responses"]]
        qti = aggregate(answers, Q)
        fired = evaluate(build_facts(intervals, indices), M)

        ds["lessons"].append({**{f: meta[f] for f in _LESSON_FIELDS}, "n_segments": len(segs),
                              "n_intervals": len(intervals), "rules_version": F["rules_version"]})
        for s in segs:
            row = {"lesson_id": lid, **{f: s[f] for f in _SEGMENT_FIELDS}}
            if include_text:
                row["text_pseudonymized"] = s["text_pseudonymized"]
            ds["segments"].append(row)
        ds["intervals"] += [{"lesson_id": lid, "interval_index": i, "start_ms": i * step, "category": c}
                            for i, c in enumerate(intervals)]
        m = transition_matrix(intervals, F)
        ds["matrix"] += [{"lesson_id": lid, "from_category": a + 1, "to_category": b + 1, "count": m[a][b]}
                         for a in range(10) for b in range(10) if m[a][b]]
        ds["indices"] += [{"lesson_id": lid, "index_id": k, "value": v["value"], "reason": v["reason"],
                           "numerator_count": v["numerator_count"], "denominator_count": v["denominator_count"],
                           "validation_status": v["validation_status"]} for k, v in indices.items()]
        ds["qti_responses"] += [{"lesson_id": lid, "response_index": n, **{f"q{i}": a[i] for i in range(1, 25)}}
                                for n, a in enumerate(answers)]
        ds["qti_results"].append({"lesson_id": lid, "response_count": qti["response_count"], "displayable": qti["displayable"],
                                  **{f"oc{i}": (qti["octants"] or {}).get(f"oc{i}") for i in range(1, 9)},
                                  "agency": qti["agency"], "communion": qti["communion"]})
        ds["mtss"] += [{"lesson_id": lid, "rule_id": f["rule_id"], "tier1_dimension": f["tier1_dimension"],
                        "framing": f["framing"], "validation_status": f["validation_status"],
                        "rules_version": f["rules_version"]} for f in fired]
        ds["recommendations"] += [{"lesson_id": lid, "recommendation_id": r["recommendation_id"], "rule_id": r["rule_id"],
                                   "validation_status": r["validation_status"]} for r in recommendations(fired, P)]
        ds["triangulation"] += [{"lesson_id": lid, "pair_id": t["pair_id"], "fias_value": t["fias"]["value"],
                                 "qti_available": t["qti_available"], "qti_values": [q["value"] for q in t["qti"]]}
                                for t in triangulate(intervals, indices, qti, P, Q)]
        processing.append({"lesson_id": lid, **{f: item["processing"].get(f) for f in _PROCESSING_FIELDS}})
    ds["manifest"] = {"export_version": EXPORT_VERSION, "rules_version": F["rules_version"], "exported_at": exported_at,
                      "include_text": include_text, "lesson_count": len(lessons), "processing": processing}
    return ds


def to_json(dataset: dict) -> str:
    return json.dumps(dataset, ensure_ascii=False, indent=2)


def _cell(v):
    """Serialização determinística de uma célula CSV (mesmo resultado em Web/Android):
    bool -> "true"/"false" minúsculo; None -> célula vazia; list/dict -> JSON compacto
    (ensure_ascii=False); float -> repr() (representação decimal mais curta que
    recupera o valor exato); demais tipos, sem transformação."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, float):
        return repr(v)
    return v


def to_csv_files(dataset: dict) -> dict[str, str]:
    files = {}
    for t in TABLES:
        rows = dataset[t]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(TABLE_FIELDS[t]), lineterminator="\n", restval="")
        w.writeheader()
        w.writerows({k: _cell(v) for k, v in r.items()} for r in rows)
        files[f"{t}.csv"] = buf.getvalue()
    return files


def write_zip(dataset: dict, path: Path) -> None:
    files = to_csv_files(dataset)
    manifest = {**dataset["manifest"],
                "files": {n: hashlib.sha256(c.encode("utf-8")).hexdigest() for n, c in files.items()}}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content.encode("utf-8"))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
