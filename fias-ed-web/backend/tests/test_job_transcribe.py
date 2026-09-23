"""Job de transcrição: cada chunk devolve tempos locais ao ASR; o que fica
gravado no banco tem de ser global — um erro de deslocamento numa aula de 90
min produziria um trecho com horário maior que a duração do arquivo, sem
rastro da origem (§18)."""
import uuid

import pytest

from app.audio.prepare import chunks_dir, work_path
from app.jobs import handlers
from app.jobs.handlers import HANDLERS
from app.jobs.queue import enqueue
from app.ml.fakes import ASRFalso
from app.ml.protocols import SegmentoASR
from app.models import Audio, Falante, Segmento, Transcricao
from app.transcricao.service import segmentos_asr, texto_efetivo, transcricao_da_aula
from tests.audio_fixtures import make_audio
from tests.helpers import make_aula, make_user

# > JANELA_PADRAO_MS (600_000): força exatamente dois chunks, o que é o ponto
# de maior risco desta task (soma do deslocamento por chunk).
DURACAO_MS = 620_000


@pytest.fixture
def aula_preparada(db, app_instance):
    """Simula o estado em que handle_prepare_audio (Task 4) deixa a aula: cópia
    de trabalho normalizada já em disco, status TRANSCRIBING."""
    prof = make_user(db, "carla")
    aula = make_aula(db, prof, status="TRANSCRIBING")
    trabalho = work_path(aula.id)
    trabalho.parent.mkdir(parents=True, exist_ok=True)
    make_audio(trabalho, seconds=DURACAO_MS / 1000)
    db.add(Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                path="original/aula.wav", mime_type="audio/wav", size_bytes=trabalho.stat().st_size,
                duration_ms=DURACAO_MS, sha256="0" * 64, channels=1, sample_rate=16000, is_original=True,
                derived_from_audio_id=None))
    db.commit()
    return aula


@pytest.fixture
def dir_chunks(aula_preparada):
    return chunks_dir(aula_preparada.id)


@pytest.fixture
def asr_falso_por_chunk(monkeypatch):
    """Dois segmentos "locais" por chunk. ASRFalso.transcrever soma o deslocamento
    recebido a cada um (ver app/ml/fakes.py) — é exatamente o que o job precisa
    fazer com cada pedaço do áudio antes de gravar."""
    asr = ASRFalso([SegmentoASR(0, 1_000, "oi"), SegmentoASR(1_000, 2_000, "turma")])
    monkeypatch.setattr(handlers, "obter_asr", lambda: asr)
    return asr


@pytest.fixture
def asr_falso_vazio(monkeypatch):
    asr = ASRFalso([])
    monkeypatch.setattr(handlers, "obter_asr", lambda: asr)
    return asr


def _rodar(db, aula):
    job = enqueue(db, aula.id, "transcribe")
    db.commit()
    HANDLERS["transcribe"](db, job)


def test_transcricao_soma_o_deslocamento_de_cada_chunk(db, aula_preparada, asr_falso_por_chunk):
    _rodar(db, aula_preparada)
    t = db.query(Transcricao).filter_by(aula_id=aula_preparada.id).one()
    segmentos = db.query(Segmento).filter_by(transcricao_id=t.id).order_by(Segmento.start_ms).all()
    assert [s.start_ms for s in segmentos] == [0, 1_000, 600_000, 601_000]
    duracao = db.get(Audio, t.audio_id).duration_ms
    assert all(s.end_ms <= duracao for s in segmentos)


def test_segmentos_nascem_ligados_a_um_falante_nao_atribuido(db, aula_preparada, asr_falso_por_chunk):
    """falante_id é NOT NULL; antes da diarização todos apontam para a mesma
    linha com role=UNASSIGNED."""
    _rodar(db, aula_preparada)
    t = db.query(Transcricao).filter_by(aula_id=aula_preparada.id).one()
    segmentos = db.query(Segmento).filter_by(transcricao_id=t.id).all()
    assert all(s.falante_id is not None for s in segmentos)
    assert len({s.falante_id for s in segmentos}) == 1
    falante = db.query(Falante).filter_by(transcricao_id=t.id).one()
    assert falante.role == "UNASSIGNED"
    assert falante.diarization_label == "pendente"


def test_transcricao_leva_a_diarizing(db, aula_preparada, asr_falso_por_chunk):
    _rodar(db, aula_preparada)
    db.refresh(aula_preparada)
    assert aula_preparada.status == "DIARIZING"


def test_audio_sem_fala_vira_erro_com_mensagem_humana(db, aula_preparada, asr_falso_vazio):
    _rodar(db, aula_preparada)
    db.refresh(aula_preparada)
    assert aula_preparada.status == "ERROR"
    assert aula_preparada.error_code == "AUDIO_SEM_FALA"
    assert db.query(Transcricao).filter_by(aula_id=aula_preparada.id).count() == 0


def test_chunks_sao_apagados_ao_fim(db, aula_preparada, asr_falso_por_chunk, dir_chunks):
    _rodar(db, aula_preparada)
    assert list(dir_chunks.glob("chunk_*.wav")) == []


def test_chunks_sao_apagados_mesmo_sem_fala(db, aula_preparada, asr_falso_vazio, dir_chunks):
    _rodar(db, aula_preparada)
    assert list(dir_chunks.glob("chunk_*.wav")) == []


def test_segmento_gravado_ja_vem_pseudonimizado(db, aula_preparada, monkeypatch):
    """A Task 6 roda antes desta de propósito: gravar_segmentos precisa pseudonimizar
    na primeira escrita, não depois — senão um nome de estudante fica em claro no
    banco (§48)."""
    asr = ASRFalso([SegmentoASR(0, 1_000, "hoje Fernanda respondeu certo")])
    monkeypatch.setattr(handlers, "obter_asr", lambda: asr)
    _rodar(db, aula_preparada)
    # o ASR falso devolve o mesmo texto para os dois chunks (deslocado no tempo);
    # start_ms=0 isola o segmento do primeiro chunk.
    seg = db.query(Segmento).filter_by(texto_original_asr="hoje Fernanda respondeu certo",
                                       start_ms=0).one()
    assert seg.text_pseudonymized == "hoje [NOME] respondeu certo"


# ---- funções produzidas por app/transcricao/service.py que não são exercitadas
# pelos testes do handler acima, mas fazem parte do contrato "Produces" da task ----

def test_transcricao_da_aula_devolve_none_sem_transcricao(db, aula_preparada):
    assert transcricao_da_aula(db, aula_preparada.id) is None


def test_transcricao_da_aula_devolve_a_linha_apos_o_job(db, aula_preparada, asr_falso_por_chunk):
    _rodar(db, aula_preparada)
    t = transcricao_da_aula(db, aula_preparada.id)
    assert t is not None and t.aula_id == aula_preparada.id


def test_segmentos_asr_relê_no_formato_do_protocolo(db, aula_preparada, asr_falso_por_chunk):
    _rodar(db, aula_preparada)
    t = transcricao_da_aula(db, aula_preparada.id)
    relidos = segmentos_asr(db, t)
    assert [(s.inicio_ms, s.fim_ms, s.texto) for s in relidos] == [
        (0, 1_000, "oi"), (1_000, 2_000, "turma"), (600_000, 601_000, "oi"), (601_000, 602_000, "turma"),
    ]


def test_texto_efetivo_prefere_o_revisado():
    seg = Segmento(texto_original_asr="original", texto_revisado="revisado")
    assert texto_efetivo(seg) == "revisado"


def test_texto_efetivo_cai_no_original_sem_revisao():
    seg = Segmento(texto_original_asr="original", texto_revisado=None)
    assert texto_efetivo(seg) == "original"
