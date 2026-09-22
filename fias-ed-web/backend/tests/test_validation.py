import shutil

import pytest

from app.audio.probe import ProbeError, probe
from app.audio.validation import ValidationFailed, check
from app.core.config import get_settings
from tests.audio_fixtures import make_audio


@pytest.mark.parametrize("fmt,mime", [("wav", "audio/wav"), ("flac", "audio/flac"), ("mp3", "audio/mpeg"),
                                      ("m4a", "audio/mp4"), ("aac", "audio/aac")])
def test_valid_formats(tmp_path, fmt, mime):
    result = probe(make_audio(tmp_path / f"a.{fmt}", fmt=fmt))
    assert 60_000 <= result.duration_ms <= 70_000  # AAC/ADTS estima pela taxa de bits
    assert result.channels == 1 and result.sample_rate == 16000
    assert check(fmt, result) == mime


def test_fake_extension_is_mismatch(tmp_path):
    flac = make_audio(tmp_path / "a.flac", fmt="flac")
    fake = tmp_path / "a.mp3"
    shutil.copy(flac, fake)
    with pytest.raises(ValidationFailed) as e:
        check("mp3", probe(fake))
    assert e.value.code == "AUDIO_FORMAT_MISMATCH"


def test_non_audio_file_raises_probe_error(tmp_path):
    fake = tmp_path / "a.wav"
    fake.write_text("isto não é áudio")
    with pytest.raises(ProbeError):
        probe(fake)


def test_duration_limits(tmp_path, monkeypatch):
    with pytest.raises(ValidationFailed) as e:
        check("wav", probe(make_audio(tmp_path / "curto.wav", seconds=5)))
    assert e.value.code == "AUDIO_TOO_SHORT"
    monkeypatch.setenv("MAX_AUDIO_SECONDS", "61")
    get_settings.cache_clear()
    with pytest.raises(ValidationFailed) as e:
        check("wav", probe(make_audio(tmp_path / "longo.wav", seconds=65)))
    assert e.value.code == "AUDIO_TOO_LONG"
    get_settings.cache_clear()
