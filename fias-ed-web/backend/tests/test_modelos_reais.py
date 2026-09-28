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


def test_bertimbau_em_lote_nao_muda_nenhuma_categoria():
    """§44, no modelo de verdade. A divisão em lotes existe para limitar memória
    (o pico ia a 4,75 GB numa aula de 46 min) e não pode custar resultado.

    O que é exatamente igual é a **entrada**: com padding="max_length" cada par
    vira as mesmas 256 posições, esteja num lote de 16 ou de 381. A saída não é
    bit a bit igual, e não é o laço que muda: o matmul em float32 escolhe ordem
    de redução conforme a dimensão do lote. Por isso o teste afirma o que
    importa e mede o resto — categoria idêntica par a par, e a diferença
    numérica ordens de grandeza abaixo da margem que decide a categoria. Um
    lote de fato quebrado (deslocado, fora de ordem, repetido) não passa por
    aqui: erraria a categoria e a diferença seria da ordem do próprio logit,
    não de 1e-6.
    """
    from app.ml import clf_bertimbau
    from app.ml.clf_bertimbau import BertimbauClassificador, Turno, categoria_de, montar_pares

    pares = montar_pares([Turno(f"essa e a fala numero {i} da aula de teste",
                                "PROFESSOR" if i % 2 else "ALUNO") for i in range(37)])
    clf = BertimbauClassificador()
    original = clf_bertimbau.TAMANHO_DO_LOTE
    try:
        clf_bertimbau.TAMANHO_DO_LOTE = len(pares)
        passagem_unica = clf.logits(pares)
        clf_bertimbau.TAMANHO_DO_LOTE = 16
        em_lote = clf.logits(pares)
    finally:
        clf_bertimbau.TAMANHO_DO_LOTE = original

    assert len(em_lote) == 37 and all(len(v) == 10 for v in em_lote)
    assert [categoria_de(v, 1) for v in em_lote] == [categoria_de(v, 1) for v in passagem_unica]
    maior_dif = max(abs(x - y) for a, b in zip(passagem_unica, em_lote) for x, y in zip(a, b))
    margem = min(sorted(v)[-1] - sorted(v)[-2] for v in passagem_unica)
    assert maior_dif < 1e-4, f"diferença de {maior_dif:g}: isso não é ruído de float32"
    assert maior_dif < margem / 1000, f"diferença {maior_dif:g} perto demais da margem {margem:g}"


def test_bertimbau_em_lote_e_reproduzivel():
    """§44 propriamente dito: a mesma aula reprocessada dá o mesmo resultado. O
    tamanho do lote é fixo, então as duas execuções fazem as mesmas contas na
    mesma ordem — aqui a igualdade é bit a bit, sem tolerância nenhuma."""
    from app.ml.clf_bertimbau import BertimbauClassificador, Turno, montar_pares

    pares = montar_pares([Turno(f"essa e a fala numero {i} da aula de teste",
                                "PROFESSOR" if i % 2 else "ALUNO") for i in range(37)])
    clf = BertimbauClassificador()
    assert clf.logits(pares) == clf.logits(pares)
