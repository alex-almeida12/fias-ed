from pathlib import Path

from app.core.config import get_settings


def store_root() -> Path:
    return get_settings().audio_store


def ensure_dirs() -> None:
    for sub in ("tmp", "original"):
        (store_root() / sub).mkdir(parents=True, exist_ok=True)


def abs_path(rel: str) -> Path:
    root = store_root().resolve()
    path = (root / rel).resolve()
    if root not in path.parents:
        raise ValueError("caminho fora do armazenamento de áudio")
    return path


def delete_file(rel: str) -> None:
    abs_path(rel).unlink(missing_ok=True)
