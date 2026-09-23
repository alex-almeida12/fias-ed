import os
import shutil
import time
import uuid
from datetime import timedelta

from app.audio.prepare import work_path
from app.audio.storage import ensure_dirs, limpar_temporarios_antigos, store_root
from app.fias import service as fias_service
from app.jobs import handlers, queue
from app.jobs.worker import run_once
from app.ml.fakes import ASRFalso, ClassificadorFalso, DiarizadorFalso
from app.ml.protocols import SegmentoASR, TurnoDiar
from app.models import Audio, AudioUpload, Aula, Job, utcnow
from tests.audio_fixtures import make_audio, upload
from tests.helpers import login, make_aula, make_user


def _processar(client, db, tmp_path, src):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    assert upload(client, aula.id, src).status_code == 201
    r = client.post(f"/api/aulas/{aula.id}/processar")
    assert r.status_code == 202 and r.json()["job_ativo"] is True
    return aula


def test_valid_audio_reaches_audio_validated(client, db, tmp_path):
    aula = _processar(client, db, tmp_path, make_audio(tmp_path / "aula.wav"))
    assert run_once(db) is True
    body = client.get(f"/api/aulas/{aula.id}").json()
    # `job_ativo is False` aqui era resíduo da W1, quando o pipeline de fato
    # terminava em AUDIO_VALIDATED. Hoje o próprio handle_validate_audio deixa
    # prepare_audio na fila, na mesma transação em que grava o status — logo a
    # aula recém-validada tem sim job ativo. O que este teste prova continua
    # sendo o mesmo: a validação deu certo e produziu a linha Audio correta.
    assert body["status"] == "AUDIO_VALIDATED" and body["job_ativo"] is True
    assert db.query(Job).filter_by(aula_id=aula.id, type="prepare_audio", status="queued").count() == 1
    assert body["audio"]["mime_type"] == "audio/wav" and body["audio"]["channels"] == 1
    assert db.query(AudioUpload).count() == 0
    audio = db.query(Audio).one()
    assert audio.is_original and audio.derived_from_audio_id is None and (store_root() / audio.path).exists()


def test_fake_extension_ends_in_error_and_file_removed(client, db, tmp_path):
    flac = make_audio(tmp_path / "a.flac", fmt="flac")
    fake = tmp_path / "gravacao.mp3"
    shutil.copy(flac, fake)
    aula = _processar(client, db, tmp_path, fake)
    path = db.query(AudioUpload).one().path
    run_once(db)
    body = client.get(f"/api/aulas/{aula.id}").json()
    assert body["status"] == "ERROR" and body["error_code"] == "AUDIO_FORMAT_MISMATCH"
    assert body["error_message"].startswith("Este arquivo não parece ser um áudio")
    assert not (store_root() / path).exists()


def test_non_audio_is_corrupted(client, db, tmp_path):
    fake = tmp_path / "a.wav"
    fake.write_text("texto")
    aula = _processar(client, db, tmp_path, fake)
    run_once(db)
    assert client.get(f"/api/aulas/{aula.id}").json()["error_code"] == "AUDIO_CORRUPTED"


def test_processar_requires_pending_upload_and_no_active_job(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = client.post(f"/api/aulas/{aula.id}/processar")
    assert r.status_code == 409 and r.json()["error_code"] == "AULA_STATE"
    upload(client, aula.id, make_audio(tmp_path / "a.wav"))
    client.post(f"/api/aulas/{aula.id}/processar")
    r = client.post(f"/api/aulas/{aula.id}/processar")
    assert r.status_code == 409 and r.json()["error_code"] == "AULA_BUSY"


def test_run_once_without_jobs(db):
    assert run_once(db) is False


def test_stale_job_is_requeued_then_failed(db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    job = Job(type="validate_audio", aula_id=aula.id, status="running", attempts=1,
              locked_at=utcnow() - timedelta(minutes=31))
    db.add(job)
    db.commit()
    queue.recover_stale(db)
    db.refresh(job)
    assert job.status == "queued" and job.locked_at is None
    job.status, job.attempts, job.locked_at = "running", 3, utcnow() - timedelta(minutes=31)
    db.commit()
    queue.recover_stale(db)
    db.refresh(job)
    assert job.status == "failed" and job.error_code == "JOB_FAILED"
    assert db.get(Aula, aula.id).status == "ERROR"


def test_handler_exception_is_retried(db, monkeypatch):
    from app.jobs import handlers
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    db.add(Job(type="validate_audio", aula_id=aula.id))
    db.commit()

    def boom(db_, job_):
        raise RuntimeError("falha simulada")

    monkeypatch.setitem(handlers.HANDLERS, "validate_audio", boom)
    run_once(db)
    job = db.query(Job).one()
    assert job.status == "queued" and job.attempts == 1
    run_once(db)
    run_once(db)
    db.refresh(job)
    assert job.status == "failed" and db.get(Aula, aula.id).error_code == "JOB_FAILED"


def test_claim_skips_locked_rows(db):
    from app.core.db import SessionLocal, get_engine
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    db.add(Job(type="validate_audio", aula_id=aula.id))
    db.commit()
    with SessionLocal(bind=get_engine()) as other:
        from sqlalchemy import select
        other.scalar(select(Job).with_for_update())  # segura a linha
        assert queue.claim_next(db) is None
        other.rollback()
    assert queue.claim_next(db) is not None


def test_job_for_deleted_aula_is_closed(db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    aula.deleted_at = utcnow()
    db.add(Job(type="validate_audio", aula_id=aula.id))
    db.commit()
    run_once(db)
    assert db.query(Job).one().status == "done"


# Rodada de conserto 1 da Task 8 (Important): tmp/ guarda tanto upload em andamento
# (upload_audio) quanto trechos avulsos de audição (extrair_trecho) — os dois só saem de
# lá no caminho feliz. Uma desconexão do cliente no meio do envio, ou antes de o
# BackgroundTask do trecho rodar, deixa o arquivo órfão para sempre; nenhum handler
# fecha esse caso sozinho, então a varredura é periódica, no worker, ao lado de
# recover_stale — mesma ideia, texto diferente.
def _idade(horas: float) -> float:
    return time.time() - horas * 3600


def test_limpar_temporarios_antigos_preserva_recente_e_apaga_velho(app_instance):
    ensure_dirs()
    tmp = store_root() / "tmp"
    velho = tmp / "orfao-velho.wav"
    novo = tmp / "orfao-novo.wav"
    velho.write_bytes(b"x")
    novo.write_bytes(b"y")
    seis_horas_e_um_minuto_atras = _idade(6) - 60
    os.utime(velho, (seis_horas_e_um_minuto_atras, seis_horas_e_um_minuto_atras))
    limpar_temporarios_antigos()
    assert not velho.exists()
    assert novo.exists()


def test_limpar_temporarios_antigos_nao_mata_upload_lento_dentro_do_prazo(app_instance):
    """O limite de upload do projeto é 1,5 GB; seis horas é a folga deliberada para um
    envio lento e genuíno não ser apagado no meio (o `mtime` do arquivo é renovado a
    cada chunk escrito por upload_audio, então um upload de verdade em andamento nunca
    fica "velho" enquanto estiver escrevendo)."""
    ensure_dirs()
    em_andamento = store_root() / "tmp" / "upload-em-andamento.wav"
    em_andamento.write_bytes(b"x")
    cinco_horas_e_meia_atras = _idade(5.5)
    os.utime(em_andamento, (cinco_horas_e_meia_atras, cinco_horas_e_meia_atras))
    limpar_temporarios_antigos()
    assert em_andamento.exists()


def test_run_once_tambem_varre_temporarios_antigos(db, app_instance):
    ensure_dirs()
    velho = store_root() / "tmp" / "orfao-velho.wav"
    velho.write_bytes(b"x")
    antigo = _idade(6) - 60
    os.utime(velho, (antigo, antigo))
    run_once(db)
    assert not velho.exists()


def test_run_once_tambem_varre_copias_de_trabalho_orfas(db, app_instance):
    """A varredura precisa estar ligada no laço do worker, e não só existir: os
    97 MB de órfãos encontrados em disco eram de aulas excluídas por um código
    que não conhecia a cópia de trabalho, e é esta chamada que dá conta deles
    sem ninguém apagar arquivo à mão."""
    ensure_dirs()
    orfao = work_path(uuid.uuid4())
    orfao.parent.mkdir(parents=True, exist_ok=True)
    orfao.write_bytes(b"RIFF")
    run_once(db)
    assert not orfao.exists()


# ---- A corrente anda sozinha -------------------------------------------------------
#
# Cada teste de estágio (test_audio_prepare, test_job_transcribe, test_job_diarize,
# test_job_fias) enfileira o seu próprio job à mão, então nenhum deles percebe um
# elo faltando entre dois estágios — a suite inteira ficava verde enquanto, em
# produção, a aula parava em AUDIO_VALIDATED para sempre. Este teste é sobre o
# encadeamento, não sobre o conteúdo de cada estágio.


def _esvaziar_a_fila(db, limite: int = 20) -> None:
    """Roda o worker até a fila secar, como o laço de `main()` faria.

    Não há um único `enqueue` neste arquivo de teste a partir daqui: se a aula
    avança, é porque cada handler enfileirou o estágio seguinte."""
    for _ in range(limite):
        if not run_once(db):
            return
    raise AssertionError(f"a fila não secou em {limite} rodadas do worker")


def _status(client, aula) -> str:
    return client.get(f"/api/aulas/{aula.id}").json()["status"]


def test_aula_validada_percorre_o_pipeline_ate_o_fim_sem_ajuda(client, db, tmp_path, monkeypatch):
    """Critério de aceitação 1 do spec: uma aula que chega a AUDIO_VALIDATED
    percorre o pipeline até FIAS_COMPLETED.

    Quem põe o primeiro job na fila é POST /processar, e quem põe o último é POST
    /transcricao/concluir — os dois caminhos de produção. Tudo entre eles tem de
    ser costurado pelos próprios handlers.

    Os modelos reais não estão presentes na suíte: os dublês entram pelos mesmos
    pontos que os testes de cada estágio já usam (os protocolos da Task 3)."""
    monkeypatch.setattr(handlers, "obter_asr", lambda: ASRFalso([
        SegmentoASR(0, 40_000, "a professora explica a questão"),
        SegmentoASR(40_000, 60_000, "o aluno responde a pergunta")]))
    monkeypatch.setattr(handlers, "obter_diarizador", lambda: DiarizadorFalso([
        TurnoDiar(0, 40_000, "SPEAKER_00"), TurnoDiar(40_000, 60_000, "SPEAKER_01")]))
    monkeypatch.setattr(fias_service, "obter_classificador", lambda: ClassificadorFalso(categoria_fixa=5))

    aula = _processar(client, db, tmp_path, make_audio(tmp_path / "aula.wav"))
    _esvaziar_a_fila(db)
    # A fila secou por conta própria exatamente onde o spec manda esperar o humano.
    assert _status(client, aula) == "READY_FOR_SPEAKER_REVIEW"

    # As duas paradas deliberadas: "qual destas vozes é você?" e "a revisão está boa".
    assert client.post(f"/api/aulas/{aula.id}/vozes/escolher", json={"rotulo": "voz-1"}).status_code == 200
    assert client.post(f"/api/aulas/{aula.id}/transcricao/concluir").status_code == 200
    _esvaziar_a_fila(db)
    assert _status(client, aula) == "FIAS_COMPLETED"
    assert db.query(Job).filter_by(aula_id=aula.id, status="failed").count() == 0
