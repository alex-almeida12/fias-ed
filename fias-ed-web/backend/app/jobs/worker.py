import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.audio.prepare import limpar_trabalho_orfao
from app.audio.storage import limpar_temporarios_antigos
from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.core.logging import configure_logging, log_event
from app.jobs import handlers
from app.jobs.queue import claim_next, recover_stale, retry_or_fail
from app.models import Job


HEARTBEAT_FILE = Path("/tmp/fias-ed-worker-heartbeat")  # nosec B108 - lido só pelo healthcheck do container


def beat() -> None:
    HEARTBEAT_FILE.touch()


def run_once(db: Session) -> bool:
    recover_stale(db)
    # Terceiro arquivo temporário sem limpeza garantida no caminho feliz nesta fatia
    # (depois dos pedaços de ASR da Task 5 e da cópia de trabalho da Task 4, esta
    # apagada no fim da diarização) — varredura periódica no mesmo laço que já
    # cuida de jobs travados.
    limpar_temporarios_antigos()
    # A cópia de trabalho tem dois descartes certos (fim da diarização e exclusão
    # da aula) e, ainda assim, esta rede: o worker pode morrer entre fechar o job
    # e apagar o arquivo, e havia órfãos em disco de antes de os dois descartes
    # existirem. Critério de dono, não de idade — veja limpar_trabalho_orfao.
    orfaos = limpar_trabalho_orfao(db)
    if orfaos:
        log_event("trabalho_orfao_removido", n_arquivos=orfaos)
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
        beat()
        with SessionLocal(bind=get_engine()) as db:
            worked = run_once(db)
        if not worked:
            time.sleep(get_settings().job_poll_seconds)


if __name__ == "__main__":
    main()
