"""Lê o registro de modelos do fias-ed-shared e confere integridade (§66, §67).

A lista de hashes é do shared, não daqui: manter uma cópia local criaria duas
fontes de verdade que divergem em silêncio.
"""
import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


class ModeloInvalido(Exception):
    def __init__(self, code: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.code = code


def _caminho_registro() -> Path:
    return Path(os.environ.get("FIAS_ED_MODELS_REGISTRY") or get_settings().models_registry)


@lru_cache(maxsize=1)
def carregar_registro() -> dict:
    caminho = _caminho_registro()
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModeloInvalido("MODELO_REGISTRO_ILEGIVEL", f"registro ilegível: {caminho}") from exc


def entrada(model_id: str) -> dict:
    for m in carregar_registro().get("models", []):
        if m.get("model_id") == model_id:
            return m
    raise ModeloInvalido("MODELO_NAO_REGISTRADO", f"modelo fora do registro: {model_id}")


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def verificar_artefatos(model_id: str, base: Path) -> None:
    m = entrada(model_id)
    for proibido in m.get("forbidden_files", []):
        if any(base.rglob(proibido)):
            raise ModeloInvalido("MODELO_ARQUIVO_PROIBIDO", f"arquivo proibido presente: {proibido}")
    for art in m.get("artifacts", []):
        caminho = base / art["relative_path"]
        if not caminho.is_file():
            raise ModeloInvalido("MODELO_ARTEFATO_AUSENTE", f"artefato ausente: {art['relative_path']}")
        if _sha256(caminho) != art["sha256"]:
            raise ModeloInvalido("MODELO_SHA256_DIVERGENTE", f"sha256 divergente: {art['relative_path']}")
