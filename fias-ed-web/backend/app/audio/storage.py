import time
from pathlib import Path

from app.core.config import get_settings

TEMP_MAX_AGE_HOURS = 6


def store_root() -> Path:
    return get_settings().audio_store


def ensure_dirs() -> None:
    for sub in ("tmp", "original"):
        (store_root() / sub).mkdir(parents=True, exist_ok=True)


def limpar_temporarios_antigos(max_age_hours: float = TEMP_MAX_AGE_HOURS) -> None:
    """Apaga arquivos de tmp/ com mais de `max_age_hours`.

    tmp/ guarda tanto upload em andamento (`upload_audio`) quanto trechos avulsos de
    audição (`extrair_trecho`, Task 8) — os dois só saem de lá no caminho feliz (um
    `os.replace()`, ou o `BackgroundTask` da resposta). Uma desconexão do cliente no
    meio do envio, ou antes de o `BackgroundTask` rodar, deixa o arquivo órfão para
    sempre; nenhum handler fecha esse caso sozinho, por isso a varredura é periódica
    (chamada a cada volta do laço do worker, ao lado de `recover_stale`).

    Seis horas é a folga deliberada: o limite de upload do projeto é 1,5 GB, e o
    `mtime` de um upload em andamento é renovado a cada chunk escrito por
    `upload_audio`, então um envio lento e genuíno não é apagado no meio."""
    tmp = store_root() / "tmp"
    if not tmp.exists():
        return
    limite = time.time() - max_age_hours * 3600
    for arquivo in tmp.iterdir():
        if arquivo.is_file() and arquivo.stat().st_mtime < limite:
            arquivo.unlink(missing_ok=True)


def abs_path(rel: str) -> Path:
    root = store_root().resolve()
    path = (root / rel).resolve()
    if root not in path.parents:
        raise ValueError("caminho fora do armazenamento de áudio")
    return path


def delete_file(rel: str) -> None:
    abs_path(rel).unlink(missing_ok=True)
