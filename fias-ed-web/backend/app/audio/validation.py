from app.audio.probe import ProbeResult
from app.core.config import get_settings

# extensão → (format_name aceitos pelo ffprobe, codecs aceitos ou None, MIME gravado)
FORMATS = {
    "mp3": ({"mp3"}, None, "audio/mpeg"),
    "wav": ({"wav"}, None, "audio/wav"),
    "m4a": ({"mov,mp4,m4a,3gp,3g2,mj2"}, {"aac", "alac"}, "audio/mp4"),
    "aac": ({"aac"}, None, "audio/aac"),
    "flac": ({"flac"}, None, "audio/flac"),
}


class ValidationFailed(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def check(ext: str, result: ProbeResult) -> str:
    s = get_settings()
    if ext not in FORMATS:
        raise ValidationFailed("AUDIO_UNSUPPORTED_FORMAT")
    formats, codecs, mime = FORMATS[ext]
    if result.format_name not in formats or (codecs is not None and result.codec not in codecs):
        raise ValidationFailed("AUDIO_FORMAT_MISMATCH")
    if result.channels < 1 or result.sample_rate < 8000 or result.duration_ms <= 0:
        raise ValidationFailed("AUDIO_CORRUPTED")
    if result.duration_ms < s.min_audio_seconds * 1000:
        raise ValidationFailed("AUDIO_TOO_SHORT")
    if result.duration_ms > s.max_audio_seconds * 1000:
        raise ValidationFailed("AUDIO_TOO_LONG")
    return mime
