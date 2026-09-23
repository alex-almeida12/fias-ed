from app.ml.protocols import SegmentoASR, TurnoDiar
from app.models import Falante
from app.pipeline.align import alinhar, criar_falantes_provisorios, resumo_por_voz
from app.transcricao.service import segmentos_ordenados, transcricao_da_aula


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


def test_segmento_que_contem_o_turno_inteiro():
    """O inverso do caso anterior: turno curto dentro de um trecho longo. A
    sobreposição é a duração do turno."""
    segs = [SegmentoASR(0, 10_000, "fala longa")]
    turnos = [TurnoDiar(3_000, 4_000, "A")]
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


def _transcricao_da(db, aula):
    return transcricao_da_aula(db, aula.id)


def _falantes_da(db, aula):
    t = _transcricao_da(db, aula)
    return db.query(Falante).filter_by(transcricao_id=t.id).all()


def test_segmentos_com_start_ms_identico_nao_trocam_de_voz(db, aula_transcrita):
    """Dois trechos começando no mesmo milissegundo. Se criar_falantes_provisorios
    refizesse a consulta por conta própria em vez de usar a lista recebida, ela
    ignoraria a ordem que o chamador escolheu e devolveria a dela — sujeita à
    ordem física do Postgres para start_ms empatado, que não tem por que
    coincidir com a do chamador.

    Para não depender de o Postgres "por acaso" desempatar de um jeito ou de
    outro (o que tornaria esta prova instável), a lista é passada na ordem
    OPOSTA à da consulta original (`reversed`). Uma implementação que honra a
    lista recebida por identidade acerta sempre, com qualquer ordem física.
    Uma implementação que refaz a consulta ignora a inversão e erra de forma
    determinística — não é uma questão de sorte do Postgres."""
    transcricao = _transcricao_da(db, aula_transcrita)
    originais = segmentos_ordenados(db, transcricao)
    originais[0].start_ms = originais[1].start_ms = 5_000
    db.commit()
    linhas = list(reversed(originais))
    rotulos = ["A", "B"] + [None] * (len(linhas) - 2)
    criar_falantes_provisorios(db, transcricao, linhas, rotulos)
    db.refresh(linhas[0])
    db.refresh(linhas[1])
    rotulo_de = {f.id: f.diarization_label for f in _falantes_da(db, aula_transcrita)}
    assert rotulo_de[linhas[0].falante_id] == "A"
    assert rotulo_de[linhas[1].falante_id] == "B"
