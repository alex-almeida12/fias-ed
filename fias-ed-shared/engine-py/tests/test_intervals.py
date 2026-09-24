import pytest

from fias_ed_engine.intervals import (CodedSegment as S, Mark, SpeechSpan as F, code_lesson,
                                      segments_to_intervals, transition_matrix)
from fias_ed_engine.rules import load_rules

R = load_rules("fias_rules")


def test_empty_audio_is_all_silence():
    assert segments_to_intervals([], 9000, R) == [10, 10, 10]


def test_partial_last_interval_counts():
    assert len(segments_to_intervals([], 7000, R)) == 3


def test_segment_spanning_intervals():
    assert segments_to_intervals([S(500, 7000, 5)], 9000, R) == [5, 5, 5]


def test_gap_interval_is_silence():
    segs = [S(0, 3000, 4), S(6000, 9000, 8)]
    assert segments_to_intervals(segs, 9000, R) == [4, 10, 8]


def test_invalid_segment_rejected():
    with pytest.raises(ValueError):
        segments_to_intervals([S(3000, 1000, 5)], 9000, R)
    with pytest.raises(ValueError):
        segments_to_intervals([S(0, 1000, 11)], 9000, R)


def test_invalid_speech_span_rejected():
    with pytest.raises(ValueError):
        segments_to_intervals([], 9000, R, [F(5000, 1000)])


# ---- Regra 3: 3 s é taxa mínima de amostragem, não balde ----------------------

def test_toda_mudanca_de_categoria_vira_marca():
    """Duas categorias dentro do mesmo intervalo de 3 s são as duas registradas.
    Sob a regra de balde a de 1 s sumia e sobrava só [4]."""
    assert segments_to_intervals([S(0, 1000, 5), S(1000, 3000, 4)], 3000, R) == [5, 4]


def test_segmento_minoritario_aparece_no_lugar_certo_da_linha_do_tempo():
    """O que prova a mudança não é a contagem de marcas — é a POSIÇÃO. Meio
    segundo de fala do aluno entre dois trechos longos do professor tem de
    aparecer ENTRE os dois, e não no começo nem no fim."""
    segs = [S(0, 10_000, 5), S(10_000, 10_500, 8), S(10_500, 20_000, 5)]
    assert segments_to_intervals(segs, 20_000, R) == [5, 5, 5, 5, 8, 5, 5, 5, 5]


def test_a_transicao_do_segmento_minoritario_chega_na_matriz():
    """E a marca no lugar certo tem de virar as duas transições certas: é para
    isso que a matriz 10×10 existe."""
    segs = [S(0, 10_000, 5), S(10_000, 10_500, 8), S(10_500, 20_000, 5)]
    m = transition_matrix(segments_to_intervals(segs, 20_000, R), R)
    assert m[5 - 1][8 - 1] == 1 and m[8 - 1][5 - 1] == 1


def test_todo_segmento_codificado_aparece_ao_menos_uma_vez():
    """Invariante central: nenhuma fala curta pode ficar invisível. Vinte
    segmentos de 150 ms alternando categoria dentro de um intervalo de 3 s."""
    segs = [S(i * 150, (i + 1) * 150, 4 if i % 2 else 5) for i in range(20)]
    seq = segments_to_intervals(segs, 3000, R)
    assert len(seq) == 20 and set(seq) == {4, 5}


def test_o_relogio_dos_3_s_reinicia_a_cada_mudanca():
    """Grade global marcaria em 0, 3000 e 6000; o relógio que reinicia marca a
    mudança e conta 3 s dali — a marca seguinte cai em 4000, não em 6000."""
    codificacao = code_lesson([S(0, 1000, 5), S(1000, 9000, 4)], 9000, R)
    assert [m.start_ms for m in codificacao.marks] == [0, 1000, 4000, 7000]


def test_funde_vizinhos_de_mesma_categoria_antes_de_marcar():
    """Sem fusão o picotamento do ASR viraria três marcas e duas transições
    5→5 que ninguém observou."""
    segs = [S(0, 1000, 5), S(1000, 2000, 5), S(2000, 3000, 5)]
    assert segments_to_intervals(segs, 3000, R) == [5]


def test_marca_nunca_passa_do_fim_da_aula_e_a_linha_do_tempo_fica_inteira():
    segs = [S(0, 1000, 5), S(1000, 7300, 4)]
    marcas = code_lesson(segs, 7300, R).marks
    assert marcas[0].start_ms == 0 and marcas[-1].end_ms == 7300
    assert all(m.end_ms <= 7300 for m in marcas)
    # sem buraco e sem sobreposição entre marcas vizinhas
    assert all(a.end_ms == b.start_ms for a, b in zip(marcas, marcas[1:]))


def test_mark_carrega_o_proprio_tempo():
    assert code_lesson([S(0, 1000, 5)], 1000, R).marks == [Mark(0, 1000, 5)]


# ---- Regra 4: o silêncio vem do diarizador ------------------------------------

def test_silencio_vem_da_fala_do_diarizador_e_nao_das_lacunas_do_asr():
    """A armadilha desta tarefa. O ASR entrega UM segmento contínuo de 30 s
    porque o vad_filter colou a pausa para dentro dele: entre segmentos não há
    lacuna nenhuma, e quem medir silêncio por lacuna de ASR acha zero e passa.
    O diarizador diz que dos 30 s só 12 s tiveram fala."""
    segs = [S(0, 30_000, 5)]
    fala = [F(0, 6000), F(24_000, 30_000)]

    sem_diarizacao = code_lesson(segs, 30_000, R)
    assert sem_diarizacao.silence_ms == 0 and 10 not in sem_diarizacao.intervals

    com_diarizacao = code_lesson(segs, 30_000, R, fala)
    assert com_diarizacao.silence_ms == 18_000
    assert com_diarizacao.intervals == [5, 5, 10, 10, 10, 10, 10, 10, 5, 5]


def test_pausa_abaixo_de_3_s_e_absorvida_pela_categoria_em_curso():
    """Micropausa respiratória não é silêncio pedagogicamente saliente."""
    codificacao = code_lesson([S(0, 9000, 5)], 9000, R, [F(0, 2000), F(4000, 9000)])
    assert codificacao.intervals == [5, 5, 5] and codificacao.silence_ms == 0


def test_lacuna_de_exatamente_3_s_ja_e_silencio():
    codificacao = code_lesson([S(0, 9000, 5)], 9000, R, [F(0, 3000), F(6000, 9000)])
    assert codificacao.silence_ms == 3000 and codificacao.intervals == [5, 10, 5]


def test_segmento_inteiramente_dentro_de_nao_fala_cede_ao_diarizador():
    """Limite declarado da invariante "todo segmento aparece": um segmento que
    cai inteiro dentro de um trecho em que o diarizador não ouviu voz nenhuma
    não é uma fala curta engolida por um vizinho maior — é o ASR e o diarizador
    discordando, e ganha quem mede voz. Deixar o segmento vencer devolveria à
    aula os 78,2 s de não-fala que a regra 4 existe para marcar."""
    segs = [S(0, 4000, 5), S(10_000, 10_500, 8), S(16_000, 20_000, 5)]
    codificacao = code_lesson(segs, 20_000, R, [F(0, 4000), F(16_000, 20_000)])
    assert codificacao.intervals == [5, 5, 10, 10, 10, 10, 5, 5]
    assert codificacao.silence_ms == 12_000 and 8 not in codificacao.intervals


def test_segmento_escondido_atras_de_outro_segmento_ainda_aparece():
    """Aí sim a invariante vale: quem esconderia o segmento é a regra de
    codificação (desempate por início mais cedo), não a evidência de fala."""
    codificacao = code_lesson([S(0, 9000, 5), S(3000, 4000, 8)], 9000, R)
    assert codificacao.intervals == [5, 8, 5, 5]
    marca = next(m for m in codificacao.marks if m.category == 8)
    assert (marca.start_ms, marca.end_ms) == (3000, 4000)


# ---- Confusão: não implementada, e não trocada por silêncio -------------------

def test_fala_sem_transcricao_nunca_vira_silencio():
    """O pior erro possível aqui seria trocar silêncio por confusão: são opostos
    acústicos. Um trecho em que o diarizador ouviu voz e o ASR não produziu
    segmento é candidato a confusão, nunca a silêncio — ele é absorvido pela
    categoria em curso. Quem medisse não-fala pelas lacunas ENTRE SEGMENTOS
    marcaria 10 aqui."""
    codificacao = code_lesson([S(0, 3000, 5)], 9000, R, [F(0, 9000)])
    assert codificacao.intervals == [5, 5, 5] and codificacao.silence_ms == 0
    assert 10 not in codificacao.intervals


def test_sobreposicao_de_falantes_nao_e_confusao():
    """Falar por cima e se entender é comportamento normal de sala de aula. A
    evidência de fala não carrega falante justamente para que sobreposição não
    possa virar categoria 10 por engano."""
    codificacao = code_lesson([S(0, 9000, 5)], 9000, R, [F(0, 9000), F(3000, 6000)])
    assert codificacao.intervals == [5, 5, 5]


def test_regra_de_confusao_declarada_como_nao_implementada():
    """A ausência é declarada, não silenciosa: quem ler um resultado desta
    versão precisa saber que a categoria 10 só recebeu silêncio."""
    assert R["confusion"]["implemented"] is False
    assert R["confusion"]["validation_status"] == "PENDING_SCIENTIFIC_VALIDATION"


def test_confusao_nao_pode_ser_ligada_sem_limiar_medido():
    """O interruptor sozinho é o defeito. Enquanto `implemented` for false não
    pode existir limiar nenhum parado no bloco — um número que ninguém mediu,
    esperando alguém virar a chave, é como esta categoria se inverte em
    silêncio. E, se um dia virar true, o limiar e a procedência dele passam a
    ser obrigatórios."""
    c = R["confusion"]
    if c["implemented"]:
        assert c.get("signal") and c.get("threshold") is not None and c.get("threshold_source")
    else:
        assert "threshold" not in c


def test_a_ausencia_de_confusao_e_declarada_com_a_medicao_que_a_sustenta():
    """"Não implementado" sem medição é opinião; com medição é resultado. O
    bloco carrega o que foi medido na aula real em 2026-09-23: quanta
    sobreposição de falantes houve, qual a resolução temporal do sinal
    candidato, e que o cruzamento entre os dois deu negativo."""
    m = R["confusion"]["measurement"]
    assert m["overlap_ms"] == 9348 and m["overlap_events"] == 13
    assert m["overlap_longest_ms"] < 3000, "sobreposição menor que o próprio intervalo de codificação"
    assert m["n_empty_text_segments"] == 0
    assert "30 s" in m["signal_time_resolution"]
    assert m["result"].startswith("negativo")


def test_motor_de_indices_nao_distingue_a_origem_da_categoria_10():
    """Para o FIAS a categoria 10 é uma só: a sequência não carrega de onde ela
    veio, e nenhum índice pode ser computado sobre a diferença."""
    codificacao = code_lesson([], 9000, R, [])
    assert codificacao.intervals == [10, 10, 10]
    assert codificacao.silence_ms == 9000
    assert not hasattr(codificacao, "confusion_ms")


def test_protocolo_desconhecido_e_recusado():
    """Se a regra declarada no fias_rules.json deixar de ser a que este motor
    implementa, ele para em vez de codificar em silêncio a regra errada."""
    regras = {**R, "interval_coding": {**R["interval_coding"], "clock": "global_grid"}}
    with pytest.raises(ValueError):
        segments_to_intervals([S(0, 3000, 5)], 3000, regras)


# ---- Matriz -------------------------------------------------------------------

def test_matrix_pads_with_10():
    m = transition_matrix([4, 8], R)
    assert m[10 - 1][4 - 1] == 1   # 10→4 (padding inicial)
    assert m[4 - 1][8 - 1] == 1    # 4→8
    assert m[8 - 1][10 - 1] == 1   # 8→10 (padding final)
    assert sum(map(sum, m)) == 3


def test_matrix_empty_sequence():
    m = transition_matrix([], R)
    assert m[9][9] == 1 and sum(map(sum, m)) == 1
