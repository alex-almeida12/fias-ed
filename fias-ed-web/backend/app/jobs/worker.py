import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.core.logging import configure_logging, log_event
from app.jobs import handlers
from app.jobs.queue import claim_next, recover_stale, retry_or_fail
from app.models import Job


def run_once(db: Session) -> bool:
    recover_stale(db)
    job = claim_next(db)
    if job is None:
        return False
    job_id = job.id
    try:
        handlers.HANDLERS[job.type](db, job)
    except Exception as exc:  # o worker nunca pode morrer por causa de um job
        db.rollback()
        job = db.get(Job, job_id)
        log_event("job_error", level=logging.ERROR, job_id=job_id, error_type=type(exc).__name__,
                  attempt=job.attempts)
        retry_or_fail(db, job)
        db.commit()
    return True


def main() -> None:
    configure_logging()
    log_event("worker_started")
    while True:
        with SessionLocal(bind=get_engine()) as db:
            worked = run_once(db)
        if not worked:
            time.sleep(get_settings().job_poll_seconds)


if __name__ == "__main__":
    main()
