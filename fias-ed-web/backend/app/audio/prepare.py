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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio.storage import store_root, work_rel
from app.aulas.service import current_audio
from app.models import Audio, Aula

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
    return store_root() / work_rel(aula_id)


def descartar_trabalho(aula_id: uuid.UUID) -> None:
    """Apaga a cópia de trabalho da aula. Silenciosa se ela não existir — quem
    chama nunca precisa saber se o estágio anterior chegou a criá-la.

    Chamada no fim do último estágio que lê este arquivo — a diarização — e nos
    caminhos de erro terminal que garantem que ele nunca mais será lido
    (app/jobs/handlers.py)."""
    work_path(aula_id).unlink(missing_ok=True)


def limpar_trabalho_orfao(db: Session) -> int:
    """Apaga cópias de trabalho de aulas excluídas ou inexistentes; devolve
    quantas apagou.

    É a rede embaixo dos dois descartes normais (fim da diarização e exclusão da
    aula), pelo mesmo motivo que existe `limpar_temporarios_antigos`: o worker
    pode morrer entre fechar o job e apagar o arquivo, uma aula pode ter sido
    excluída por uma versão anterior deste código, e um estágio que termina em
    erro terminal nunca mais roda — em todos esses casos sobra um arquivo de
    dezenas ou centenas de MB que ninguém mais vai ler.

    O critério não é idade, e sim dono: o arquivo é de uma aula, então só sai
    quando a aula não existe mais ou está excluída. Idade não serviria — uma aula
    pode passar horas na fila antes da transcrição, com a cópia de trabalho
    pronta e velha, e apagá-la ali quebraria o estágio seguinte.

    Nome que não seja `<uuid>.wav` é deixado quieto: este diretório é escrito só
    por `normalizar`, e apagar o que não se sabe de onde veio é pior do que
    deixar."""
    diretorio = store_root() / "work"
    if not diretorio.is_dir():
        return 0
    arquivos: dict[uuid.UUID, Path] = {}
    for arquivo in diretorio.iterdir():
        if arquivo.suffix != ".wav" or not arquivo.is_file():
            continue
        try:
            arquivos[uuid.UUID(arquivo.stem)] = arquivo
        except ValueError:
            continue
    if not arquivos:
        return 0
    vivas = set(db.scalars(select(Aula.id).where(Aula.id.in_(arquivos.keys()),
                                                 Aula.deleted_at.is_(None))))
    apagados = 0
    for aula_id, arquivo in arquivos.items():
        if aula_id not in vivas:
            arquivo.unlink(missing_ok=True)
            apagados += 1
    return apagados


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
