import json
import subprocess  # nosec B404 - ffprobe com argumentos em lista (prompt §57)
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    format_name: str
    codec: str
    duration_ms: int
    channels: int
    sample_rate: int


class ProbeError(Exception):
    pass


def probe(path: Path) -> ProbeResult:
    try:
        completed = subprocess.run(  # nosec B603 B607 - lista de argumentos, sem shell
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, timeout=120, check=True)
        data = json.loads(completed.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ProbeError("arquivo ilegível") from exc
    fmt = data.get("format") or {}
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if stream is None or "format_name" not in fmt:
        raise ProbeError("sem stream de áudio")
    try:
        duration = float(fmt.get("duration") or stream.get("duration") or 0)
        return ProbeResult(format_name=fmt["format_name"], codec=stream.get("codec_name", ""),
                           duration_ms=int(round(duration * 1000)), channels=int(stream.get("channels", 0)),
                           sample_rate=int(stream.get("sample_rate", 0)))
    except (TypeError, ValueError) as exc:
        raise ProbeError("metadados inválidos") from exc
