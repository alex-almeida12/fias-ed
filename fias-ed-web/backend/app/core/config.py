from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    migrator_database_url: str | None = None
    audio_store: Path = Path("/data/audio")
    shared_dir: Path = Path("/opt/fias-ed-shared")
    device_id: str = "fias-ed-web"
    max_upload_bytes: int = 1_610_612_736
    min_audio_seconds: int = 60
    max_audio_seconds: int = 9_000
    session_idle_minutes: int = 120
    session_absolute_hours: int = 12
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    job_poll_seconds: float = 2.0
    job_stale_minutes: int = 30
    job_max_attempts: int = 3
    models_dir: str = "/models"
    models_registry: str = "/shared/scientific-config/models.json"
    asr_size: str = "small"
    asr_model_id: str = "faster-whisper-small"
    diar_model_id: str = "pyannote-speaker-diarization-3.1"
    clf_model_id: str = "fias-bertimbau-ptbr-frente3"
    usar_modelos_falsos: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
