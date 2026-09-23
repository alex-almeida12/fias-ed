from app.ml.protocols import SegmentoASR, TurnoDiar
from app.pipeline.align import alinhar, resumo_por_voz


def test_segmento_inteiramente_dentro_de_um_turno():
    segs = [SegmentoASR(1_000, 2_000, "olá")]
    turnos = [TurnoDiar(0, 5_000, "A")]
    assert alinhar(segs, turnos) == ["A"]


def test_segmento_que_cruza_a_fronteira_fica_com_a_maior_sobreposicao():
    """Review Focus 2: alguém interrompe no meio da frase. O segmento não pode
    ser descartado nem empatar — fica com quem falou mais tempo dentro dele."""
    segs = [SegmentoASR(4_000, 6_000, "espera aí")]
    turnos = [TurnoDiar(0, 4_500, "A"), TurnoDiar(4_500, 9_000, "B")]
    # 500 ms em A, 1500 ms em B
    assert alinhar(segs, turnos) == ["B"]


def test_empate_exato_escolhe_o_turno_que_comeca_antes():
    segs = [SegmentoASR(4_000, 6_000, "meio a meio")]
    turnos = [TurnoDiar(0, 5_000, "A"), TurnoDiar(5_000, 9_000, "B")]
    assert alinhar(segs, turnos) == ["A"]


def test_empate_exato_independe_da_ordem_de_entrada_dos_turnos():
    """O desempate é por quem começou antes, não por quem aparece primeiro na
    lista — turnos fora de ordem não podem inverter o resultado."""
    segs = [SegmentoASR(4_000, 6_000, "meio a meio")]
    turnos = [TurnoDiar(5_000, 9_000, "B"), TurnoDiar(0, 5_000, "A")]
    assert alinhar(segs, turnos) == ["A"]


def test_segmento_sem_sobreposicao_nenhuma_fica_sem_rotulo():
    segs = [SegmentoASR(10_000, 11_000, "eco")]
    turnos = [TurnoDiar(0, 5_000, "A")]
    assert alinhar(segs, turnos) == [None]


def test_sem_turnos_todos_ficam_sem_rotulo():
    segs = [SegmentoASR(0, 1_000, "x"), SegmentoASR(1_000, 2_000, "y")]
    assert alinhar(segs, []) == [None, None]


def test_resumo_agrega_tempo_e_contagem_por_voz():
    segs = [SegmentoASR(0, 2_000, "a"), SegmentoASR(2_000, 3_000, "b"), SegmentoASR(3_000, 9_000, "c")]
    grupos = resumo_por_voz(segs, ["A", "B", "A"])
    por_rotulo = {g.rotulo: g for g in grupos}
    assert por_rotulo["A"].tempo_total_ms == 8_000
    assert por_rotulo["A"].n_segmentos == 2
    assert por_rotulo["B"].tempo_total_ms == 1_000
    # ordenado do que mais falou para o que menos falou
    assert [g.rotulo for g in grupos] == ["A", "B"]


def test_resumo_traz_no_maximo_tres_amostras_por_voz():
    segs = [SegmentoASR(i * 1_000, i * 1_000 + 900, "x") for i in range(10)]
    grupos = resumo_por_voz(segs, ["A"] * 10)
    assert len(grupos[0].amostras) == 3
