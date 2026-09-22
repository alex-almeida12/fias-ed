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


def upload(client, aula_id, path: Path, filename: str | None = None):
    return client.put(f"/api/aulas/{aula_id}/audio", content=path.read_bytes(),
                      headers={"X-Filename": quote(filename or path.name),
                               "Content-Type": "application/octet-stream"})
