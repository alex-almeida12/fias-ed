from pathlib import Path

from app.ml.fakes import ASRFalso, ClassificadorFalso, DiarizadorFalso
from app.ml.protocols import SegmentoASR, TurnoDiar


def test_asr_falso_respeita_o_deslocamento():
    asr = ASRFalso([SegmentoASR(0, 1000, "olá"), SegmentoASR(1000, 2000, "turma")])
    saida = asr.transcrever(Path("qualquer.wav"), deslocamento_ms=60_000)
    assert [(s.inicio_ms, s.fim_ms) for s in saida] == [(60_000, 61_000), (61_000, 62_000)]
    assert [s.texto for s in saida] == ["olá", "turma"]


def test_diarizador_falso_devolve_os_turnos_configurados():
    turnos = [TurnoDiar(0, 5_000, "SPEAKER_00"), TurnoDiar(5_000, 9_000, "SPEAKER_01")]
    assert DiarizadorFalso(turnos).turnos(Path("x.wav")) == turnos


def test_classificador_falso_devolve_um_vetor_por_par():
    clf = ClassificadorFalso(categoria_fixa=4)
    saida = clf.logits([("a", "b"), ("c", "d")])
    assert len(saida) == 2
    assert all(len(v) == 10 for v in saida)
    # categoria 4 → índice 3, por causa do logit_index_offset = 1
    assert all(max(range(10), key=v.__getitem__) == 3 for v in saida)
