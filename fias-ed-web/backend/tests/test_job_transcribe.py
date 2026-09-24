"""Job de transcrição: cada chunk devolve tempos locais ao ASR; o que fica
gravado no banco tem de ser global — um erro de deslocamento numa aula de 90
min produziria um trecho com horário maior que a duração do arquivo, sem
rastro da origem (§18)."""
import uuid

import pytest

from app.audio.prepare import chunks_dir, work_path
from app.core.db import SessionLocal, get_engine
from app.jobs import handlers
from app.jobs.handlers import HANDLERS
from app.jobs.queue import enqueue
from app.ml.fakes import ASRFalso
from app.ml.protocols import SegmentoASR
from app.models import Audio, Aula, Falante, Job, Segmento, Transcricao
from app.transcricao.service import segmentos_asr, texto_efetivo, transcricao_da_aula
from tests.audio_fixtures import make_audio
from tests.helpers import make_aula, make_user

# > JANELA_PADRAO_MS (600_000): força exatamente dois chunks, o que é o ponto
# de maior risco desta task (soma do deslocamento por chunk).
DURACAO_MS = 620_000


@pytest.fixture
def aula_preparada(db, app_instance):
    """Simula o estado em que handle_prepare_audio (Task 4) deixa a aula: cópia
    de trabalho normalizada já em disco, status PREPROCESSING — o preparo acabou e
    o job de transcrição está na fila, ainda sem ter começado. Quem marca
    TRANSCRIBING é este handler, ao começar."""
    prof = make_user(db, "carla")
    aula = make_aula(db, prof, status="PREPROCESSING")
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


def test_transcricao_leva_a_transcribed_com_a_diarizacao_na_fila(db, aula_preparada, asr_falso_por_chunk):
    """TRANSCRIBED é o estado de repouso entre os dois estágios: a transcrição
    acabou, a diarização está enfileirada e ainda não começou. DIARIZING aqui
    afirmaria um trabalho que só handle_diarize faz."""
    _rodar(db, aula_preparada)
    db.refresh(aula_preparada)
    assert aula_preparada.status == "TRANSCRIBED"
    assert db.query(Job).filter_by(aula_id=aula_preparada.id, type="diarize", status="queued").count() == 1


def test_transcribing_so_existe_enquanto_a_transcricao_acontece(db, aula_preparada, monkeypatch):
    """Um teste que só olha o status no fim do handler não distingue "marcou ao
    começar" de "marcou ao terminar". Este olha nos três momentos: com o job na
    fila (PREPROCESSING), dentro de cada chamada ao ASR (TRANSCRIBING, lido por
    outra sessão — ou seja, já commitado, que é o que a tela do professor enxerga)
    e no fim (TRANSCRIBED)."""
    visto: list[str] = []

    class ASREspiao:
        def transcrever(self, caminho, deslocamento_ms):
            with SessionLocal(bind=get_engine()) as outra:
                visto.append(outra.get(Aula, aula_preparada.id).status)
            return [SegmentoASR(deslocamento_ms, deslocamento_ms + 1_000, "oi")]

    monkeypatch.setattr(handlers, "obter_asr", lambda: ASREspiao())
    job = enqueue(db, aula_preparada.id, "transcribe")
    db.commit()
    assert db.get(Aula, aula_preparada.id).status == "PREPROCESSING"
    HANDLERS["transcribe"](db, job)
    assert visto == ["TRANSCRIBING", "TRANSCRIBING"]
    db.refresh(aula_preparada)
    assert aula_preparada.status == "TRANSCRIBED"


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


def test_chunks_sao_apagados_quando_o_asr_levanta(db, aula_preparada, dir_chunks, monkeypatch):
    """A exceção sobe até o worker, que faz rollback e retry. Sem o try/finally em
    volta do corte e da transcrição, os pedaços já cortados ficariam no disco —
    centenas de MB numa aula de 90 min, repetidos a cada tentativa de retry."""
    class ASRQueFalha:
        def transcrever(self, caminho, deslocamento_ms):
            raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(handlers, "obter_asr", lambda: ASRQueFalha())
    job = enqueue(db, aula_preparada.id, "transcribe")
    db.commit()
    with pytest.raises(RuntimeError):
        HANDLERS["transcribe"](db, job)
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


def test_transcribe_preserva_a_copia_de_trabalho_para_a_diarizacao(db, aula_preparada, asr_falso_por_chunk):
    """Os chunks somem no fim deste estágio, a cópia de trabalho não: a diarização
    (o estágio seguinte) recebe o arquivo normalizado inteiro, porque é na
    fronteira entre chunks que a troca de falante se perde. Apagar aqui pouparia
    disco por alguns minutos e quebraria a aula inteira."""
    _rodar(db, aula_preparada)
    db.refresh(aula_preparada)
    assert aula_preparada.status == "TRANSCRIBED"
    assert work_path(aula_preparada.id).exists()


def test_audio_sem_fala_nao_deixa_a_copia_de_trabalho(db, aula_preparada, asr_falso_vazio):
    """AUDIO_SEM_FALA é terminal e a diarização nunca chega a ser enfileirada:
    daqui em diante ninguém lê mais este arquivo."""
    _rodar(db, aula_preparada)
    db.refresh(aula_preparada)
    assert aula_preparada.error_code == "AUDIO_SEM_FALA"
    assert not work_path(aula_preparada.id).exists()


# ---- A confiança de decodificação do ASR ------------------------------------
#
# `Segmento.asr_confidence` existe no schema desde a W2 e nunca era escrito: o
# pipeline descartava os sinais de qualidade do faster-whisper na mesma
# expressão que somava o deslocamento. Campo morto num schema é pior que campo
# ausente — quem lê o schema acha que o número está lá.


def test_confianca_do_asr_chega_ao_banco_no_segmento_certo(db, aula_preparada, monkeypatch):
    """Não basta "o campo foi gravado": um teste assim fica verde se todo
    segmento receber a confiança do primeiro, ou a média da aula. O que trava
    aqui é QUAL valor: o segmento de decodificação ruim (0,31) tem de chegar ao
    banco com 0,31, e o bom com 0,93, cada um no seu trecho."""
    asr = ASRFalso([SegmentoASR(0, 1_000, "oi", 0.93), SegmentoASR(1_000, 2_000, "turma", 0.31)])
    monkeypatch.setattr(handlers, "obter_asr", lambda: asr)
    _rodar(db, aula_preparada)
    transcricao = transcricao_da_aula(db, aula_preparada.id)
    linhas = (db.query(Segmento).filter_by(transcricao_id=transcricao.id)
              .order_by(Segmento.start_ms).all())
    assert [(s.start_ms, s.texto_original_asr, s.asr_confidence) for s in linhas] == [
        (0, "oi", 0.93), (1_000, "turma", 0.31),
        (600_000, "oi", 0.93), (601_000, "turma", 0.31)]


def test_asr_sem_confianca_grava_nulo_e_nao_zero(db, aula_preparada, asr_falso_por_chunk):
    """Zero é uma confiança — a pior possível. "O ASR não informou" é outra
    coisa, e é NULL. Trocar um pelo outro faria uma aula transcrita por uma
    versão anterior parecer a pior aula do conjunto."""
    _rodar(db, aula_preparada)
    transcricao = transcricao_da_aula(db, aula_preparada.id)
    linhas = db.query(Segmento).filter_by(transcricao_id=transcricao.id).all()
    assert linhas and all(s.asr_confidence is None for s in linhas)
