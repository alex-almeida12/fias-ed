"""Cópia de trabalho, normalização e corte em chunks.

O original nunca é tocado (§17). Os chunks existem só para o ASR; a diarização
recebe o arquivo normalizado inteiro, porque é na fronteira entre chunks que a
troca de falante se perde.
"""
import shutil
import subprocess  # nosec B404 - lista de argumentos, sem shell (§57)
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.audio.storage import store_root
from app.aulas.service import current_audio
from app.models import Audio

JANELA_PADRAO_MS = 600_000


@dataclass(frozen=True)
class Chunk:
    indice: int
    inicio_ms: int
    duracao_ms: int
    caminho: Path


def planejar_chunks(duracao_ms: int, janela_ms: int = JANELA_PADRAO_MS) -> list[tuple[int, int]]:
    if duracao_ms <= 0:
        raise ValueError("duração precisa ser positiva")
    plano: list[tuple[int, int]] = []
    inicio = 0
    while inicio < duracao_ms:
        plano.append((inicio, min(janela_ms, duracao_ms - inicio)))
        inicio += janela_ms
    return plano


def _rodar(args: list[str]) -> None:
    subprocess.run(  # nosec B603 B607 - lista de argumentos, sem shell
        args, check=True, capture_output=True, timeout=3600)


def normalizar(origem: Path, destino: Path) -> None:
    """Cópia de trabalho em 16 kHz, mono, PCM 16 bits — o que os dois modelos esperam."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    _rodar(["ffmpeg", "-nostdin", "-y", "-i", str(origem),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destino)])


def cortar(origem: Path, plano: list[tuple[int, int]], dir_destino: Path) -> list[Chunk]:
    dir_destino.mkdir(parents=True, exist_ok=True)
    chunks: list[Chunk] = []
    for indice, (inicio_ms, duracao_ms) in enumerate(plano):
        caminho = dir_destino / f"chunk_{indice:04d}.wav"
        _rodar(["ffmpeg", "-nostdin", "-y", "-i", str(origem),
                "-ss", f"{inicio_ms / 1000:.3f}", "-t", f"{duracao_ms / 1000:.3f}",
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(caminho)])
        chunks.append(Chunk(indice, inicio_ms, duracao_ms, caminho))
    return chunks


def extrair_trecho(origem: Path, inicio_ms: int, fim_ms: int, destino: Path) -> None:
    """Recorta um trecho do áudio original para audição avulsa (Task 8: ouvir a
    amostra de uma voz antes de escolher qual é a do professor). Sempre grava em
    WAV — o áudio original pode estar em qualquer um dos formatos aceitos, e a
    resposta HTTP só carrega um Content-Type."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    _rodar(["ffmpeg", "-nostdin", "-y", "-i", str(origem), "-ss", f"{inicio_ms / 1000:.3f}",
            "-t", f"{(fim_ms - inicio_ms) / 1000:.3f}", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", str(destino)])


def work_path(aula_id: uuid.UUID) -> Path:
    """Caminho da cópia de trabalho — derivado só do UUID da aula, nunca de nome vindo do professor."""
    return store_root() / "work" / f"{aula_id}.wav"


def chunks_dir(aula_id: uuid.UUID) -> Path:
    """Diretório dos chunks — derivado só do UUID da aula."""
    return store_root() / "chunks" / str(aula_id)


def limpar_chunks(dir_destino: Path) -> None:
    """Apaga o diretório de chunks depois do uso. Silencioso se ele não existir."""
    shutil.rmtree(dir_destino, ignore_errors=True)


def audio_original(db: Session, aula_id: uuid.UUID) -> Audio | None:
    """O áudio is_original da aula — reaproveita a consulta de app.aulas.service.current_audio
    em vez de duplicá-la aqui."""
    return current_audio(db, aula_id)
