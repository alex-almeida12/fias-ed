import uuid

from sqlalchemy.orm import Session

from app.audio.probe import ProbeError, probe
from app.audio.storage import abs_path, delete_file
from app.audio.validation import ValidationFailed, check
from app.aulas.service import pending_upload
from app.core.logging import log_event
from app.jobs.queue import finish_job
from app.models import Audio, Aula, Job


def handle_validate_audio(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    upload = pending_upload(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or upload is None:
        finish_job(db, job)
        db.commit()
        return
    ext = upload.internal_filename.rsplit(".", 1)[-1]
    try:
        result = probe(abs_path(upload.path))
        mime = check(ext, result)
    except ProbeError:
        code = "AUDIO_CORRUPTED"
    except ValidationFailed as exc:
        code = exc.code
    else:
        db.add(Audio(id=uuid.uuid4(), aula_id=aula.id, original_filename=upload.original_filename,
                     internal_filename=upload.internal_filename, path=upload.path, mime_type=mime,
                     size_bytes=upload.size_bytes, duration_ms=result.duration_ms, sha256=upload.sha256,
                     channels=result.channels, sample_rate=result.sample_rate, is_original=True,
                     derived_from_audio_id=None))
        db.delete(upload)
        aula.status, aula.error_code = "AUDIO_VALIDATED", None
        finish_job(db, job)
        db.commit()
        log_event("audio_validated", aula_id=aula.id, job_id=job.id)
        return
    rel = upload.path
    db.delete(upload)
    aula.status, aula.error_code = "ERROR", code
    finish_job(db, job)
    db.commit()
    delete_file(rel)
    log_event("audio_rejected", aula_id=aula.id, job_id=job.id, error_code=code)


HANDLERS = {"validate_audio": handle_validate_audio}
