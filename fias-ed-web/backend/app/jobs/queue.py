import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Aula, Job, utcnow


def enqueue(db: Session, aula_id: uuid.UUID, job_type: str) -> Job:
    job = Job(type=job_type, aula_id=aula_id, status="queued")
    db.add(job)
    db.flush()
    return job


def claim_next(db: Session) -> Job | None:
    job = db.scalar(select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1)
                    .with_for_update(skip_locked=True))
    if job is None:
        db.rollback()
        return None
    job.status, job.locked_at, job.attempts = "running", utcnow(), job.attempts + 1
    db.commit()
    return job


def finish_job(db: Session, job: Job) -> None:
    job.status, job.finished_at = "done", utcnow()


def fail_job(db: Session, job: Job, code: str) -> None:
    job.status, job.error_code, job.finished_at = "failed", code, utcnow()
    aula = db.get(Aula, job.aula_id)
    if aula is not None and aula.deleted_at is None:
        aula.status, aula.error_code = "ERROR", code


def retry_or_fail(db: Session, job: Job) -> None:
    """Reenfileira o job, ou o marca como falho quando as tentativas se esgotaram.

    Reusado por recover_stale (jobs travados) e pelo caminho de exceção do worker."""
    if job.attempts >= get_settings().job_max_attempts:
        fail_job(db, job, "JOB_FAILED")
    else:
        job.status, job.locked_at = "queued", None


def recover_stale(db: Session) -> None:
    s = get_settings()
    limit = utcnow() - timedelta(minutes=s.job_stale_minutes)
    stale = db.scalars(select(Job).where(Job.status == "running", Job.locked_at < limit)
                       .with_for_update(skip_locked=True)).all()
    for job in stale:
        retry_or_fail(db, job)
    db.commit()
