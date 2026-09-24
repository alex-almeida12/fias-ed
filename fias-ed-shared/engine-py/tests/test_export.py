import csv
import hashlib
import io
import json
import zipfile

import jsonschema
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from fias_ed_engine.export import (TABLES, ExportPrivacyError, ExportRulesVersionError, build_dataset,
                                   to_csv_files, to_json, write_zip)
from fias_ed_engine.intervals import SpeechSpan
from fias_ed_engine.paths import SCHEMAS_DIR
from fias_ed_engine.rules import load_rules

SCHEMA = json.loads((SCHEMAS_DIR / "export" / "lesson_dataset.schema.json").read_text(encoding="utf-8"))
RULES_VERSION = load_rules("fias_rules")["rules_version"]
PROC = {"app_version": "web-0.1.0", "fias_model": "fias-bertimbau-ptbr-frente3", "fias_model_hash": "625d32a2",
        "asr_model": "faster-whisper-small", "asr_model_hash": "x", "diarization_model": "pyannote",
        "rules_version": RULES_VERSION}


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
        "transcript_source", "silence_source", "n_segments", "n_intervals", "rules_version"]
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


# ---- Defeito A: o silêncio do dataset vem da evidência de fala ----------------

def aula_com_pausa(speech=None, lid="01926b3e-7a1c-7c3e-9f00-00000000000a"):
    """Os 30 s da armadilha do motor: o ASR entrega UM segmento contínuo porque
    o vad_filter colou a pausa para dentro dele, e o diarizador diz que dos 30 s
    só 12 s tiveram fala. As duas fontes dão o mesmo número de marcas (10) e
    categorias diferentes — por isso "mudou" não prova nada, só o número certo."""
    item = lesson(lid=lid)
    item["lesson"]["duration_ms"] = 30_000
    item["segments"] = [{"segment_id": "s1", "start_ms": 0, "end_ms": 30_000, "role": "PROFESSOR",
                         "pred_raw": 5, "pred_role_constrained": 5, "confidence": 0.9, "uncertain": False,
                         "text_pseudonymized": "Vamos ao exercício da página dez."}]
    if speech is not None:
        item["speech"] = speech
    return item


def test_export_mede_silencio_pela_evidencia_de_fala_quando_a_aula_a_traz():
    fala = [SpeechSpan(0, 6000), SpeechSpan(24_000, 30_000)]
    ds = build_dataset([aula_com_pausa(fala)], include_text=False, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    # 18 s de não-fala em dois trechos de 9 s: regra 4 (lacuna >= 3 s) = categoria 10.
    assert [r["category"] for r in ds["intervals"]] == [5, 5, 10, 10, 10, 10, 10, 10, 5, 5]
    assert ds["lessons"][0]["n_intervals"] == 10
    sc = {r["index_id"]: r for r in ds["indices"]}["SC"]
    assert sc["value"] == pytest.approx(0.6) and sc["numerator_count"] == 6 and sc["denominator_count"] == 10
    assert ds["manifest"]["processing"][0]["silence_source"] == "diarization_speech_activity"


def test_export_sem_evidencia_de_fala_cai_nos_segmentos_e_nao_inventa_silencio():
    """A aula processada antes da versão que grava a evidência: mesmo `total_ms`,
    mesmas marcas em quantidade, nenhuma categoria 10 — e o manifesto diz que o
    silêncio desta aula foi medido pela outra fonte."""
    ds = build_dataset([aula_com_pausa()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert [r["category"] for r in ds["intervals"]] == [5] * 10
    sc = {r["index_id"]: r for r in ds["indices"]}["SC"]
    assert sc["value"] == pytest.approx(0.0) and sc["numerator_count"] == 0
    assert ds["manifest"]["processing"][0]["silence_source"] == "asr_segments"


def test_manifesto_separa_as_duas_fontes_no_mesmo_dataset():
    """Metade das aulas com a evidência, metade sem: o dataset é permitido (as
    duas estão na mesma versão de regras), mas tem de dizer qual é qual."""
    com = aula_com_pausa([SpeechSpan(0, 6000), SpeechSpan(24_000, 30_000)])
    sem = aula_com_pausa(lid="01926b3e-7a1c-7c3e-9f00-00000000000b")
    ds = build_dataset([com, sem], include_text=False, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert {p["lesson_id"]: p["silence_source"] for p in ds["manifest"]["processing"]} == {
        "01926b3e-7a1c-7c3e-9f00-00000000000a": "diarization_speech_activity",
        "01926b3e-7a1c-7c3e-9f00-00000000000b": "asr_segments"}


def test_lessons_csv_traz_a_fonte_do_silencio_de_cada_aula():
    """Quem abre só as planilhas não tem o manifesto por perto: a declaração tem
    de estar na linha da aula, lida do CSV de verdade. Duas aulas idênticas menos
    pela evidência de fala têm de sair com valores DIFERENTES e corretos — ler o
    dicionário antes de virar CSV não provaria que a coluna chega ao arquivo."""
    com = aula_com_pausa([SpeechSpan(0, 6000), SpeechSpan(24_000, 30_000)])
    sem = aula_com_pausa(lid="01926b3e-7a1c-7c3e-9f00-00000000000b")
    ds = build_dataset([com, sem], include_text=False, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    linhas = list(csv.DictReader(io.StringIO(to_csv_files(ds)["lessons.csv"])))
    assert {r["lesson_id"]: r["silence_source"] for r in linhas} == {
        "01926b3e-7a1c-7c3e-9f00-00000000000a": "diarization_speech_activity",
        "01926b3e-7a1c-7c3e-9f00-00000000000b": "asr_segments"}
    # E a coluna vizinha continua sendo outra coisa: origem do texto, não do silêncio.
    assert {r["transcript_source"] for r in linhas} == {"TRANSCRICAO_REVISADA"}


def test_coluna_e_manifesto_saem_do_mesmo_valor():
    """Manter a declaração nos dois lugares só é legítimo enquanto os dois vierem
    do mesmo cálculo. Este teste é o que impede a divergência de voltar."""
    com = aula_com_pausa([SpeechSpan(0, 6000), SpeechSpan(24_000, 30_000)])
    sem = aula_com_pausa(lid="01926b3e-7a1c-7c3e-9f00-00000000000b")
    ds = build_dataset([com, sem], include_text=False, exported_at="2026-09-21T12:00:00Z")
    linhas = list(csv.DictReader(io.StringIO(to_csv_files(ds)["lessons.csv"])))
    assert {r["lesson_id"]: r["silence_source"] for r in linhas} ==         {p["lesson_id"]: p["silence_source"] for p in ds["manifest"]["processing"]}


def test_dataset_sem_a_fonte_do_silencio_e_recusado_pelo_schema():
    """Obrigatória, não opcional: um dataset sem a coluna é justamente o dataset
    do qual o analista tiraria média sem perceber."""
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    del ds["lessons"][0]["silence_source"]
    with pytest.raises(jsonschema.ValidationError) as erro:
        validate(ds)
    assert "silence_source" in str(erro.value)


def test_start_ms_do_intervalo_e_o_tempo_da_marca_e_nao_indice_vezes_3_s():
    """Com o relógio que reinicia a cada mudança, a enésima marca não começa em
    n × 3 s: aqui a mudança cai em 1000 ms e as marcas seguem dali. Calcular por
    índice daria [0, 3000, 6000, 9000] — a última começando no fim da aula."""
    item = lesson()
    item["segments"] = [
        {"segment_id": "s1", "start_ms": 0, "end_ms": 1000, "role": "PROFESSOR", "pred_raw": 4,
         "pred_role_constrained": 4, "confidence": 0.9, "uncertain": False, "text_pseudonymized": "Quanto é?"},
        {"segment_id": "s2", "start_ms": 1000, "end_ms": 9000, "role": "PROFESSOR", "pred_raw": 5,
         "pred_role_constrained": 5, "confidence": 0.9, "uncertain": False, "text_pseudonymized": "Explico assim."}]
    item["speech"] = [SpeechSpan(0, 9000)]
    ds = build_dataset([item], include_text=False, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert [(r["interval_index"], r["start_ms"], r["category"]) for r in ds["intervals"]] == [
        (0, 0, 4), (1, 1000, 5), (2, 4000, 5), (3, 7000, 5)]


# ---- Defeito B: versões de regra não se misturam ------------------------------

def test_versoes_de_regra_misturadas_recusadas_dizendo_quais_aulas():
    velha = lesson(lid="01926b3e-7a1c-7c3e-9f00-000000000002")
    velha["processing"] = {**PROC, "rules_version": "1.0.0"}
    with pytest.raises(ExportRulesVersionError) as erro:
        build_dataset([lesson(), velha], include_text=False, exported_at="2026-09-21T12:00:00Z")
    msg = str(erro.value)
    assert "1.0.0: 01926b3e-7a1c-7c3e-9f00-000000000002" in msg
    assert f"{RULES_VERSION}: 01926b3e-7a1c-7c3e-9f00-000000000001" in msg


def test_aula_fora_da_versao_do_motor_recusada_mesmo_sozinha():
    """`build_dataset` recodifica com as regras carregadas agora: exportar uma
    aula de 1.0.0 sozinha produziria tabelas 2.0.0 com carimbo 1.0.0."""
    velha = lesson()
    velha["processing"] = {**PROC, "rules_version": "1.0.0"}
    with pytest.raises(ExportRulesVersionError):
        build_dataset([velha], include_text=False, exported_at="2026-09-21T12:00:00Z")


def test_aula_sem_versao_declarada_recusada():
    muda = lesson()
    muda["processing"] = {k: v for k, v in PROC.items() if k != "rules_version"}
    with pytest.raises(ExportRulesVersionError) as erro:
        build_dataset([muda], include_text=False, exported_at="2026-09-21T12:00:00Z")
    assert "(não declarada)" in str(erro.value)


def test_export_version_acompanha_a_mudanca_de_significado_das_tabelas():
    """`intervals` e `indices` mudaram de grandeza com rules_version 2.0.0;
    um dataset 1.0.0 e um desta versão não se empilham."""
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    assert ds["manifest"]["export_version"] == "2.1.0"
    assert ds["manifest"]["rules_version"] == RULES_VERSION
