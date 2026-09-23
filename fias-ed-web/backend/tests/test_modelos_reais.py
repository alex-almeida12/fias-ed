"""Os modelos reais, com peso em disco. Fora da suíte padrão (marcador `lento`).

São a única verificação de que o ASR e a diarização funcionam de fato — daí as
asserções exigirem conteúdo, não só forma. Um teste que só checa
`isinstance(segmentos, list)` fica verde com o modelo completamente quebrado,
porque uma lista vazia satisfaz qualquer `all(...)`.

Por isso as fixtures são de fala sintetizada (libflite), não do tom de 440 Hz
que o resto da suíte usa: o VAD do Whisper devolve zero segmento para um tom
puro.
"""
import pytest

pytestmark = pytest.mark.lento


def test_whisper_transcreve_fala_de_verdade(wav_fala):
    from app.ml.asr_whisper import WhisperASR
    segmentos = WhisperASR().transcrever(wav_fala, deslocamento_ms=0)
    assert segmentos, "nenhum segmento: o modelo não ouviu a fala do arquivo"
    assert all(s.texto.strip() for s in segmentos)
    assert all(s.fim_ms > s.inicio_ms for s in segmentos)
    assert [s.inicio_ms for s in segmentos] == sorted(s.inicio_ms for s in segmentos)


def test_whisper_e_deterministico(wav_fala):
    """§44: a mesma aula reprocessada tem de dar o mesmo texto."""
    from app.ml.asr_whisper import WhisperASR
    a = WhisperASR().transcrever(wav_fala, 0)
    b = WhisperASR().transcrever(wav_fala, 0)
    assert a, "sem segmento nenhum a comparação de duas listas vazias não prova nada"
    assert [s.texto for s in a] == [s.texto for s in b]
    assert [(s.inicio_ms, s.fim_ms) for s in a] == [(s.inicio_ms, s.fim_ms) for s in b]


def test_deslocamento_e_somado(wav_fala):
    from app.ml.asr_whisper import WhisperASR
    base = WhisperASR().transcrever(wav_fala, 0)
    deslocado = WhisperASR().transcrever(wav_fala, 60_000)
    assert base, "sem segmento nenhum o deslocamento não é exercitado"
    assert [(s.inicio_ms + 60_000, s.fim_ms + 60_000) for s in base] \
        == [(s.inicio_ms, s.fim_ms) for s in deslocado]


def test_pyannote_separa_as_duas_vozes(wav_duas_vozes):
    from app.ml.diar_pyannote import PyannoteDiarizador
    turnos = PyannoteDiarizador().turnos(wav_duas_vozes)
    assert turnos, "nenhum turno: o pipeline não ouviu fala no arquivo"
    assert all(t.fim_ms > t.inicio_ms for t in turnos)
    assert [t.inicio_ms for t in turnos] == sorted(t.inicio_ms for t in turnos)
    assert len({t.rotulo for t in turnos}) > 1, "duas vozes, um rótulo só"
