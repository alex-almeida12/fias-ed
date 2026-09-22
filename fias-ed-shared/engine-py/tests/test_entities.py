import json

import jsonschema
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from fias_ed_engine.paths import SCHEMAS_DIR

ENT = SCHEMAS_DIR / "entities"
NAMES = ["professor", "escola", "turma", "disciplina", "aula", "audio", "transcricao", "segmento", "falante",
         "classificacao_fias", "indicador_fias", "questionario_qti", "resposta_qti", "resultado_qti",
         "triangulacao", "resultado_mtss", "recomendacao", "relatorio", "processamento", "modelo_ia"]


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


REG = Registry().with_resources((_load(p)["$id"], Resource.from_contents(_load(p))) for p in ENT.glob("*.schema.json"))


def validator(name):
    return Draft202012Validator(_load(ENT / f"{name}.schema.json"), registry=REG, format_checker=FormatChecker())


def test_all_twenty_present():
    assert sorted(p.name.removesuffix(".schema.json") for p in ENT.glob("*.schema.json") if not p.name.startswith("_")) == sorted(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_schema_valid_and_example_validates(name):
    Draft202012Validator.check_schema(_load(ENT / f"{name}.schema.json"))
    validator(name).validate(_load(ENT / "examples" / f"{name}.json"))


@pytest.mark.parametrize("name", NAMES)
def test_rejects_unknown_field(name):
    ex = _load(ENT / "examples" / f"{name}.json") | {"student_name": "Fulano"}
    with pytest.raises(jsonschema.ValidationError):
        validator(name).validate(ex)


def test_base_fields_required():
    ex = _load(ENT / "examples" / "aula.json")
    del ex["sync_status"]
    with pytest.raises(jsonschema.ValidationError):
        validator("aula").validate(ex)


def test_no_sensitive_fields_anywhere():
    forbidden = {"student_name", "nome_aluno", "cpf", "email", "voice_embedding", "embedding", "audio_blob", "blob"}
    for p in ENT.glob("*.schema.json"):
        assert not forbidden & set(json.dumps(_load(p)).replace('"', " ").split()), p.name
