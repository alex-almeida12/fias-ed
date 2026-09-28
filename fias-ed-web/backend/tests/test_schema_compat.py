"""Início do schema_compatibility_test (prompt §79): tabelas × schemas do shared."""
import json

import pytest
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.config import get_settings
from app.models import Base

ENTITY_TABLES = ["professor", "escola", "turma", "disciplina", "aula", "audio", "processamento",
                 "transcricao", "falante", "segmento", "classificacao_fias", "indicador_fias",
                 "modelo_ia"]


def load_schema(name: str):
    folder = get_settings().shared_dir / "schemas" / "entities"
    base = json.loads((folder / "_base.schema.json").read_text(encoding="utf-8"))
    schema = json.loads((folder / f"{name}.schema.json").read_text(encoding="utf-8"))
    props, required = dict(base["properties"]), set(base["required"])
    for part in schema["allOf"]:
        if "properties" in part:
            props.update(part["properties"])
            required |= set(part.get("required", []))
    return props, required


def allows_null(spec: dict) -> bool:
    t = spec.get("type")
    return isinstance(t, list) and "null" in t


def expected_types(spec: dict) -> tuple:
    if "enum" in spec:
        return (Enum,)
    t = spec["type"]
    if isinstance(t, list):
        t = next(x for x in t if x != "null")
    if t == "string":
        return {"uuid": (UUID,), "date-time": (DateTime,), "date": (Date,)}.get(spec.get("format"), (String, Text))
    return {"integer": (Integer, BigInteger), "number": (Float,), "boolean": (Boolean,), "object": (JSONB,)}[t]


@pytest.mark.parametrize("table", ENTITY_TABLES)
def test_table_matches_shared_schema(table):
    props, required = load_schema(table)
    cols = Base.metadata.tables[table].columns
    for name, spec in props.items():
        assert name in cols, f"{table}.{name} ausente"
        col = cols[name]
        assert isinstance(col.type, expected_types(spec)), f"{table}.{name}: tipo {col.type!r}"
        if "enum" in spec:
            # spec["enum"] pode incluir None quando o JSON Schema expressa nulidade
            # dentro do próprio enum (ex.: indicador_fias.reason); a nulidade da coluna
            # já é conferida abaixo por allows_null, então None nunca é um rótulo válido
            # de sqlalchemy.Enum e é descartado aqui.
            esperado = {v for v in spec["enum"] if v is not None}
            assert set(col.type.enums) == esperado, f"{table}.{name}: enum difere"
        if "maxLength" in spec:
            assert col.type.length == spec["maxLength"], f"{table}.{name}: tamanho difere"
        if allows_null(spec):
            assert col.nullable, f"{table}.{name} deveria aceitar nulo"
        elif name in required:
            assert not col.nullable, f"{table}.{name} deveria ser NOT NULL"


def test_migrations_match_models(migrator_engine):
    from alembic import command
    from tests.conftest import alembic_config
    command.check(alembic_config())  # levanta erro se models e migrações divergirem
