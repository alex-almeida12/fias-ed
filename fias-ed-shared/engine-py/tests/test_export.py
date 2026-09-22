import csv
import hashlib
import io
import json
import zipfile

import jsonschema
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from fias_ed_engine.export import TABLES, ExportPrivacyError, build_dataset, to_csv_files, to_json, write_zip
from fias_ed_engine.paths import SCHEMAS_DIR

SCHEMA = json.loads((SCHEMAS_DIR / "export" / "lesson_dataset.schema.json").read_text(encoding="utf-8"))
PROC = {"app_version": "web-0.1.0", "fias_model": "fias-bertimbau-ptbr-frente3", "fias_model_hash": "625d32a2",
        "asr_model": "faster-whisper-small", "asr_model_hash": "x", "diarization_model": "pyannote"}


def lesson(lid="01926b3e-7a1c-7c3e-9f00-000000000001", text=True):
    segs = [
        {"segment_id": "s1", "start_ms": 0, "end_ms": 3000, "role": "PROFESSOR", "pred_raw": 4, "pred_role_constrained": 4, "confidence": 0.9, "uncertain": False},
        {"segment_id": "s2", "start_ms": 3000, "end_ms": 6000, "role": "ALUNO", "pred_raw": 8, "pred_role_constrained": 8, "confidence": 0.8, "uncertain": False},
    ]
    if text:
        segs[0]["text_pseudonymized"] = "[NOME], quanto é três vezes quatro?"
        segs[1]["text_pseudonymized"] = "Doze."
    return {"lesson": {"lesson_id": lid, "lesson_date": "2026-09-21", "disciplina": "Matemática",
                       "turma_id": "01926b3e-7a1c-7c3e-9f00-000000000099", "duration_ms": 9000,
                       "transcript_source": "TRANSCRICAO_REVISADA"},
            "segments": segs, "qti_responses": [{str(i): 3 for i in range(1, 25)}] * 10, "processing": PROC}


def validate(ds):
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(ds)


def test_default_export_has_no_text():
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert all("text_pseudonymized" not in s for s in ds["segments"])
    assert "Doze" not in to_json(ds)


def test_include_text_uses_pseudonymized_only():
    ds = build_dataset([lesson()], include_text=True, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert ds["segments"][0]["text_pseudonymized"].startswith("[NOME]")
    assert ds["manifest"]["include_text"] is True


def test_include_text_refused_without_pseudonymization():
    with pytest.raises(ExportPrivacyError):
        build_dataset([lesson(text=False)], include_text=True, exported_at="2026-09-21T12:00:00Z")


def test_derived_tables_consistent_with_engine():
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    assert [r["category"] for r in ds["intervals"]] == [4, 8, 10]
    by = {r["index_id"]: r for r in ds["indices"]}
    assert by["TT"]["value"] == pytest.approx(1 / 3)
    assert ds["qti_results"][0]["displayable"] is True
    assert len(ds["qti_responses"]) == 10 and ds["qti_responses"][0]["q24"] == 3
    assert sum(r["count"] for r in ds["matrix"]) == 4
    assert {r["pair_id"] for r in ds["triangulation"]} >= {"TRI_WARMTH"}


def test_multiple_lessons():
    ds = build_dataset([lesson(), lesson(lid="01926b3e-7a1c-7c3e-9f00-000000000002")], include_text=False,
                       exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert ds["manifest"]["lesson_count"] == 2
    assert {r["lesson_id"] for r in ds["segments"]} == {"01926b3e-7a1c-7c3e-9f00-000000000001", "01926b3e-7a1c-7c3e-9f00-000000000002"}


def test_never_exports_sensitive_fields():
    raw = lesson()
    raw["lesson"]["professor_name"] = "Fulano"
    raw["segments"][0]["texto_original_asr"] = "Maria, quanto é três vezes quatro?"
    raw["processing"]["audio_path"] = "C:/audio.wav"
    text = to_json(build_dataset([raw], include_text=True, exported_at="2026-09-21T12:00:00Z"))
    for leak in ("Fulano", "Maria", "audio.wav", "professor_name", "texto_original_asr", "audio_path"):
        assert leak not in text


def test_empty_export_rejected():
    with pytest.raises(ValueError):
        build_dataset([], include_text=False, exported_at="2026-09-21T12:00:00Z")


def test_bool_lowercase_in_csv():
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    files = to_csv_files(ds)
    seg_rows = list(csv.DictReader(io.StringIO(files["segments.csv"])))
    assert {r["uncertain"] for r in seg_rows} == {"false"}
    qti_rows = list(csv.DictReader(io.StringIO(files["qti_results.csv"])))
    assert qti_rows[0]["displayable"] == "true"
    for name in ("segments.csv", "qti_results.csv"):
        assert "True" not in files[name] and "False" not in files[name]


def test_empty_table_has_header():
    ds = {t: [] for t in TABLES}
    files = to_csv_files(ds)
    assert csv.DictReader(io.StringIO(files["lessons.csv"])).fieldnames == [
        "lesson_id", "lesson_date", "disciplina", "turma_id", "duration_ms",
        "transcript_source", "n_segments", "n_intervals", "rules_version"]
    assert csv.DictReader(io.StringIO(files["qti_responses.csv"])).fieldnames == \
        ["lesson_id", "response_index"] + [f"q{i}" for i in range(1, 25)]
    assert csv.DictReader(io.StringIO(files["qti_results.csv"])).fieldnames == \
        ["lesson_id", "response_count", "displayable"] + [f"oc{i}" for i in range(1, 9)] + ["agency", "communion"]
    for t in TABLES:
        assert files[f"{t}.csv"].splitlines()[0] != "" and len(files[f"{t}.csv"].splitlines()) == 1


def test_csv_and_zip(tmp_path):
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    files = to_csv_files(ds)
    assert set(files) == {f"{t}.csv" for t in TABLES}
    rows = list(csv.DictReader(io.StringIO(files["segments.csv"])))
    assert rows[0]["segment_id"] == "s1"
    out = tmp_path / "aulas.zip"
    write_zip(ds, out)
    with zipfile.ZipFile(out) as z:
        manifest = json.loads(z.read("manifest.json"))
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(z.read(name)).hexdigest() == digest
