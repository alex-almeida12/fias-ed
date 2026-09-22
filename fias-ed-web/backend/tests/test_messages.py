import pytest

from app.core.config import get_settings
from app.core.messages import error_message, format_duration, format_size


@pytest.mark.parametrize("seconds,text", [(60, "1 minuto"), (45 * 60, "45 minutos"), (3600, "1h"),
                                          (9000, "2h30"), (5400, "1h30")])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


@pytest.mark.parametrize("size,text", [(1_610_612_736, "1,5 GB"), (2 * 1024 ** 3, "2 GB"),
                                       (500 * 1024 ** 2, "500 MB")])
def test_format_size(size, text):
    assert format_size(size) == text


def test_messages_use_configured_limits(monkeypatch):
    monkeypatch.setenv("MAX_AUDIO_SECONDS", "5400")
    get_settings.cache_clear()
    assert error_message("AUDIO_TOO_LONG") == \
        "O áudio tem mais de 1h30. Divida a gravação e envie cada parte como uma aula."
    get_settings.cache_clear()


def test_all_codes_have_messages():
    for code in ("AUDIO_FORMAT_MISMATCH", "AUDIO_UNSUPPORTED_FORMAT", "AUDIO_TOO_LONG", "AUDIO_TOO_SHORT",
                 "AUDIO_CORRUPTED", "AUDIO_TOO_LARGE", "AUDIO_LOCKED", "JOB_FAILED"):
        assert error_message(code)
    assert error_message(None) is None
    assert error_message("DESCONHECIDO") == "Algo deu errado. Tente novamente."
