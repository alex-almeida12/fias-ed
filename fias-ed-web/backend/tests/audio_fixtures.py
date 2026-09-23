import subprocess  # nosec B404 - geração de áudio de teste
from pathlib import Path
from urllib.parse import quote

_CODECS = {
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "mp3": ["-c:a", "libmp3lame"],
    "m4a": ["-c:a", "aac"],
    "aac": ["-c:a", "aac", "-f", "adts"],
}


def make_audio(path: Path, seconds: float = 65, fmt: str = "wav") -> Path:
    subprocess.run(  # nosec B603 B607 - argumentos fixos em lista
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-ac", "1", "-ar", "16000", *_CODECS[fmt], str(path)], check=True)
    return path


# Fala sintética de verdade, via libflite (o filtro `flite` do ffmpeg da imagem).
# Um tom senoidal não serve para exercitar ASR nem diarização: o VAD do Whisper
# descarta o tom inteiro e devolve zero segmento, o que faria qualquer asserção
# sobre "a lista de segmentos" passar com o modelo quebrado.
# As vozes vêm do próprio libflite (`ffmpeg -f lavfi -i flite=list_voices=1`):
# `slt` é feminina, `rms` é masculina — timbres distintos o bastante para a
# diarização ter o que separar. Offline, sem rede e sem licença nova.
VOZ_A = "slt"
VOZ_B = "rms"


def _flite(path: Path, texto: str, voz: str) -> Path:
    if any(c in texto for c in ":'\\"):
        raise ValueError("texto com caractere que o filtergraph do ffmpeg interpreta")
    subprocess.run(  # nosec B603 B607 - argumentos fixos em lista
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"flite=text='{texto}':voice={voz}",
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


def make_fala(path: Path, falas: list[tuple[str, str]]) -> Path:
    """Escreve um wav 16 kHz mono com as falas concatenadas, na ordem dada.

    `falas` é uma lista de (texto, voz).
    """
    partes = [_flite(path.with_name(f"{path.stem}-{i}.wav"), texto, voz)
              for i, (texto, voz) in enumerate(falas)]
    entradas = [arg for parte in partes for arg in ("-i", str(parte))]
    filtro = "".join(f"[{i}:a]" for i in range(len(partes))) + f"concat=n={len(partes)}:v=0:a=1"
    subprocess.run(  # nosec B603 B607 - argumentos fixos em lista
        ["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", filtro,
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(path)], check=True)
    for parte in partes:
        parte.unlink()
    return path


def upload(client, aula_id, path: Path, filename: str | None = None):
    return client.put(f"/api/aulas/{aula_id}/audio", content=path.read_bytes(),
                      headers={"X-Filename": quote(filename or path.name),
                               "Content-Type": "application/octet-stream"})
