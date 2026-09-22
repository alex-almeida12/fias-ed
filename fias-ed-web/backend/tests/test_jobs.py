import shutil
from datetime import timedelta

from app.audio.storage import store_root
from app.jobs import queue
from app.jobs.worker import run_once
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
    assert body["status"] == "AUDIO_VALIDATED" and body["job_ativo"] is False
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
