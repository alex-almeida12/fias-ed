"""Carregamento e validação das regras compartilhadas."""
import json
from functools import lru_cache
from typing import Any

import jsonschema
from referencing import Registry, Resource

from .paths import RULES_DIR, SCHEMAS_DIR

RULE_FILES = ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules")


def _read(path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _registry() -> Registry:
    resources = []
    for p in (SCHEMAS_DIR / "rules").glob("*.schema.json"):
        schema = _read(p)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def validate(name: str, data: Any) -> None:
    schema = _read(SCHEMAS_DIR / "rules" / f"{name}.schema.json")
    jsonschema.Draft202012Validator(schema, registry=_registry()).validate(data)


def load_rules(name: str) -> dict:
    if name not in RULE_FILES:
        raise ValueError(f"Arquivo de regras desconhecido: {name}")
    data = _read(RULES_DIR / f"{name}.json")
    validate(name, data)
    return data
