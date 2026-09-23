import json
import logging
import sys

ALLOWED_FIELDS = frozenset({
    "event", "aula_id", "processamento_id", "job_id", "professor_id", "admin_id",
    "status", "duration_ms", "error_code", "error_type", "method", "path",
    "status_code", "attempt", "n_segmentos", "n_vozes",
})

logger = logging.getLogger("fias_ed")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname}
        payload.update(getattr(record, "fields", {"event": record.getMessage()}))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Campos de log não permitidos: {sorted(unknown)}")
    safe = {k: (None if v is None else str(v)) for k, v in fields.items()}
    logger.log(level, event, extra={"fields": {"event": event, **safe}})
