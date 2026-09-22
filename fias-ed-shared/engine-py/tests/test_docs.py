import pytest

from fias_ed_engine.language import find_forbidden
from fias_ed_engine.paths import SHARED_ROOT

DOCS = SHARED_ROOT / "docs"
REQUIRED = {
    "RESEARCH_INVENTORY.md": ["FIAS", "QTI", "MTSS", "AIED Unplugged", "PENDING_SCIENTIFIC_VALIDATION"],
    "ANALISE_MODELOS_EXISTENTES.md": ["token_type_ids", "0,7915", "BERTimbau", "CC BY-NC-SA", "training_args.bin"],
    "MODELS.md": ["SHA-256", "verify_models.py"],
    "FIAS.md": ["ID_RATIO", "3 s", "Flanders", "PTR"],
    "QTI.md": ["QTI-24", "Inseguro", "Incerto", "Wubbels", "extract_qti.py"],
    "MTSS.md": ["Tier 1", "enabled", "Formas_de_Uso"],
    "SCIENTIFIC_TRACEABILITY.md": ["source_reference", "validation_status", "CAP4"],
    "SCIENTIFIC_REPRODUCIBILITY.md": ["rules_version", "fias_model_hash", "conformance"],
    "DATABASE_MODEL.md": ["UUID", "sync_status", "BLOB"],
    "ENTITY_DICTIONARY.md": ["classificacao_fias", "pred_role_constrained"],
    "PRIVACY.md": ["retenção", "TCLE", "ALUNO", "biometria"],
    "FUTURE_SYNC.md": ["PENDING_SYNC", "CONFLICT"],
    "FUTURE_SYNC_API.md": ["device_id", "version"],
}
# Documentos que DESCREVEM o vocabulário proibido podem citá-lo entre crases; o teste ignora trechos em `...`.
import re


@pytest.mark.parametrize("name,terms", REQUIRED.items())
def test_doc_exists_with_key_terms(name, terms):
    text = (DOCS / name).read_text(encoding="utf-8")
    for t in terms:
        assert t in text, f"{name} sem '{t}'"


@pytest.mark.parametrize("name", REQUIRED)
def test_doc_language(name):
    text = re.sub(r"`[^`]*`", "", (DOCS / name).read_text(encoding="utf-8"))
    assert find_forbidden(text) == [], name
