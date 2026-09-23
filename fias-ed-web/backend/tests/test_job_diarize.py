"""Job de diarização: cruza os segmentos já gravados com os turnos que o
separador de vozes devolve, repontando cada segmento para o falante da sua
voz. Falha do separador é erro de produto (§48 exige mensagem humana, não
degradação silenciosa); uma única voz detectada não é erro — pode ser uma
aula expositiva legítima."""
import uuid

import pytest

from app.jobs import handlers
from app.jobs.handlers import HANDLERS
from app.jobs.queue import enqueue
from app.ml.fakes import DiarizadorFalso
from app.ml.protocols import SegmentoASR, TurnoDiar
from app.models import Audio, Falante, Segmento
from app.transcricao.service import criar_transcricao, falante_provisorio, gravar_segmentos, transcricao_da_aula
from tests.helpers import make_aula, make_user

DURACAO_MS = 9_000


@pytest.fixture
def aula_transcrita(db):
    """Simula o estado em que handle_transcribe (Task 5) deixa a aula: um
    falante provisório (role=UNASSIGNED, diarization_label="pendente") ao qual
    todos os segmentos apontam, status DIARIZING."""
    prof = make_user(db, "carla")
    aula = make_aula(db, prof, status="DIARIZING")
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1, duration_ms=DURACAO_MS,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True, derived_from_audio_id=None)
    db.add(audio)
    db.flush()
    transcricao = criar_transcricao(db, aula, audio, "fake-asr")
    provisorio = falante_provisorio(db, transcricao)
    segmentos = [SegmentoASR(0, 4_500, "professor explicando"),
                SegmentoASR(4_500, 9_000, "aluno perguntando")]
    gravar_segmentos(db, transcricao, segmentos, provisorio)
    db.commit()
    return aula


@pytest.fixture
def diarizador_falso_duas_vozes(monkeypatch):
    diarizador = DiarizadorFalso([TurnoDiar(0, 4_500, "SPEAKER_00"), TurnoDiar(4_500, 9_000, "SPEAKER_01")])
    monkeypatch.setattr(handlers, "obter_diarizador", lambda: diarizador)
    return diarizador


@pytest.fixture
def diarizador_falso_uma_voz(monkeypatch):
    diarizador = DiarizadorFalso([TurnoDiar(0, 9_000, "SPEAKER_00")])
    monkeypatch.setattr(handlers, "obter_diarizador", lambda: diarizador)
    return diarizador


@pytest.fixture
def diarizador_que_falha(monkeypatch):
    class DiarizadorQueFalha:
        def turnos(self, caminho):
            raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(handlers, "obter_diarizador", lambda: DiarizadorQueFalha())


def _rodar(db, aula):
    job = enqueue(db, aula.id, "diarize")
    db.commit()
    HANDLERS["diarize"](db, job)


def test_diarize_leva_a_escolha_de_voz(db, aula_transcrita, diarizador_falso_duas_vozes):
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"
    assert aula_transcrita.error_code is None


def test_diarize_nao_grava_agrupamento_de_voz_persistente(db, aula_transcrita, diarizador_falso_duas_vozes):
    """§48: nenhum agrupamento por estudante sobrevive além de UNASSIGNED —
    Falante só conhece PROFESSOR, ALUNO e UNASSIGNED como papel."""
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    falantes = db.query(Falante).filter_by(transcricao_id=t.id).all()
    assert falantes  # a diarização criou ao menos um falante por voz
    assert {f.role for f in falantes} <= {"PROFESSOR", "ALUNO", "UNASSIGNED"}


def test_diarize_repointa_os_segmentos_para_a_voz_certa_e_apaga_o_provisorio(
        db, aula_transcrita, diarizador_falso_duas_vozes):
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    linhas = db.query(Segmento).filter_by(transcricao_id=t.id).order_by(Segmento.start_ms).all()
    falantes = {f.id: f.diarization_label for f in db.query(Falante).filter_by(transcricao_id=t.id).all()}
    assert [falantes[s.falante_id] for s in linhas] == ["SPEAKER_00", "SPEAKER_01"]
    # o provisório da Task 5 não tem mais segmentos apontando para ele: some.
    assert db.query(Falante).filter_by(transcricao_id=t.id, diarization_label="pendente").count() == 0


def test_uma_voz_so_nao_e_erro(db, aula_transcrita, diarizador_falso_uma_voz):
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"


def test_falha_da_diarizacao_vira_erro_com_mensagem_humana(db, aula_transcrita, diarizador_que_falha):
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "ERROR"
    assert aula_transcrita.error_code == "DIARIZACAO_FALHOU"


def test_job_para_aula_excluida_e_fechado_sem_diarizar(db, aula_transcrita, diarizador_falso_duas_vozes):
    from app.models import utcnow
    aula_transcrita.deleted_at = utcnow()
    db.commit()
    job = enqueue(db, aula_transcrita.id, "diarize")
    db.commit()
    HANDLERS["diarize"](db, job)
    db.refresh(job)
    assert job.status == "done"
