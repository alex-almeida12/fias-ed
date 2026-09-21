"""Caminhos do repositório e das fontes externas (somente leitura)."""
import os
from pathlib import Path

SHARED_ROOT = Path(__file__).resolve().parents[3]
RULES_DIR = SHARED_ROOT / "rules"
SCHEMAS_DIR = SHARED_ROOT / "schemas"
CONFORMANCE_DIR = SHARED_ROOT / "conformance"
SCIENTIFIC_CONFIG_DIR = SHARED_ROOT / "scientific-config"
DESIGN_TOKENS_DIR = SHARED_ROOT / "design-tokens"

_MESTRADO = SHARED_ROOT.parents[1]
_DEFAULT_EXPERIMENTS = _MESTRADO / "artigos selecionados" / "experimentos"
_DEFAULT_QTI_SYSTEM = (
    _MESTRADO
    / "Adaptação para o Português Brasileiro do Questionário sobre a Interação do Professor (QTI)"
    / "sistema" / "avalie-seu-professor"
)


def experiments_dir() -> Path:
    return Path(os.environ.get("FIAS_ED_EXPERIMENTS_DIR", _DEFAULT_EXPERIMENTS))


def qti_system_dir() -> Path:
    return Path(os.environ.get("FIAS_ED_QTI_SYSTEM_DIR", _DEFAULT_QTI_SYSTEM))
