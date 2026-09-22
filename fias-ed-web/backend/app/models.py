import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer,
                        MetaData, String, literal_column)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

AULA_STATUS = (
    "DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "PREPROCESSING", "TRANSCRIBING", "TRANSCRIBED",
    "DIARIZING", "READY_FOR_SPEAKER_REVIEW", "READY_FOR_TRANSCRIPT_REVIEW", "READY_FOR_FIAS",
    "FIAS_COMPLETED", "WAITING_QTI", "QTI_COMPLETED", "TRIANGULATED", "MTSS_INTERPRETED",
    "REPORT_READY", "ERROR",
)
SYNC_STATUS = ("LOCAL_ONLY", "PENDING_SYNC", "SYNCED", "CONFLICT")
ROLES = ("ADMIN_LOCAL", "PROFESSOR")
REGIONS = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
MIME_TYPES = ("audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac", "audio/flac", "audio/x-flac")
TRANSCRIPT_SOURCES = ("ASR_ORIGINAL", "TRANSCRICAO_REVISADA")
JOB_STATUS = ("queued", "running", "done", "failed")
ADMIN_ACTIONS = ("read", "create", "update", "delete", "upload", "process")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _device_id() -> str:
    return get_settings().device_id


def _enum(values: tuple, name: str) -> Enum:
    return Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class EntityMixin:
    """Campos comuns do _base.schema.json do shared."""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow,
                                                 nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, onupdate=literal_column("version + 1"),
                                         nullable=False)
    sync_status: Mapped[str] = mapped_column(_enum(SYNC_STATUS, "sync_status"), default="LOCAL_ONLY",
                                             nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), default=_device_id, nullable=False)


class Professor(EntityMixin, Base):
    __tablename__ = "professor"
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(_enum(ROLES, "role"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Escola(EntityMixin, Base):
    __tablename__ = "escola"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_key: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    municipality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(_enum(REGIONS, "region"), nullable=True)


class Turma(EntityMixin, Base):
    __tablename__ = "turma"
    escola_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escola.id"), nullable=False)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    school_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[str | None] = mapped_column(String(60), nullable=True)


class Disciplina(EntityMixin, Base):
    __tablename__ = "disciplina"
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Aula(EntityMixin, Base):
    __tablename__ = "aula"
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    turma_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("turma.id"), nullable=False)
    disciplina_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disciplina.id"), nullable=False)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(_enum(AULA_STATUS, "aula_status"), default="DRAFT", nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Audio(EntityMixin, Base):
    __tablename__ = "audio"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_filename: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(_enum(MIME_TYPES, "mime_type"), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False)
    derived_from_audio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audio.id"), nullable=True)


FALANTE_ROLES = ("PROFESSOR", "ALUNO", "UNASSIGNED")
LANGUAGES = ("pt-BR",)
MODEL_FORMATS = ("safetensors", "onnx", "ggml", "other")
INDICADOR_REASONS = ("insufficient_data",)
VALIDATION_STATUS = ("validated", "PENDING_SCIENTIFIC_VALIDATION", "engineering_decision",
                     "draft_pending_researcher_review")


class Transcricao(EntityMixin, Base):
    __tablename__ = "transcricao"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    audio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audio.id"), nullable=False)
    language: Mapped[str] = mapped_column(_enum(LANGUAGES, "transcricao_language"),
                                          default="pt-BR", nullable=False)
    asr_model_id: Mapped[str] = mapped_column(String, nullable=False)


class Falante(EntityMixin, Base):
    """Uma linha por voz enquanto role=UNASSIGNED; exatamente duas depois da
    escolha do professor (PROFESSOR e ALUNO). Nenhum agrupamento de voz por
    estudante sobrevive à escolha (§48)."""
    __tablename__ = "falante"
    transcricao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcricao.id"), index=True,
                                                      nullable=False)
    diarization_label: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(_enum(FALANTE_ROLES, "falante_role"),
                                      default="UNASSIGNED", nullable=False)


class Segmento(EntityMixin, Base):
    __tablename__ = "segmento"
    transcricao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcricao.id"), index=True,
                                                      nullable=False)
    falante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("falante.id"), nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    texto_original_asr: Mapped[str] = mapped_column(String(10000), nullable=False)
    texto_revisado: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    revisado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    asr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_pseudonymized: Mapped[str | None] = mapped_column(String(10000), nullable=True)


class ClassificacaoFIAS(EntityMixin, Base):
    __tablename__ = "classificacao_fias"
    segmento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("segmento.id"), index=True,
                                                   nullable=False)
    transcript_source: Mapped[str] = mapped_column(
        _enum(TRANSCRIPT_SOURCES, "classificacao_transcript_source"), nullable=False)
    pred_raw: Mapped[int] = mapped_column(Integer, nullable=False)
    pred_role_constrained: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_raw: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)


class IndicadorFIAS(EntityMixin, Base):
    __tablename__ = "indicador_fias"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    index_id: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(_enum(INDICADOR_REASONS, "indicador_reason"),
                                               nullable=True)
    numerator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    n_intervals: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        _enum(VALIDATION_STATUS, "indicador_validation_status"), nullable=False)
    mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class ModeloIA(EntityMixin, Base):
    __tablename__ = "modelo_ia"
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    task: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(_enum(MODEL_FORMATS, "modelo_format"), nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    license: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Processamento(EntityMixin, Base):
    """Criada em W1 para manter o modelo completo; primeira linha nasce no W2."""
    __tablename__ = "processamento"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    app_version: Mapped[str] = mapped_column(String, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)
    asr_model: Mapped[str] = mapped_column(String, nullable=False)
    asr_model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    diarization_model: Mapped[str] = mapped_column(String, nullable=False)
    fias_model: Mapped[str] = mapped_column(String, nullable=False)
    fias_model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hardware: Mapped[str] = mapped_column(String(200), nullable=False)
    device: Mapped[str] = mapped_column(String(200), nullable=False)
    audio_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript_source: Mapped[str] = mapped_column(_enum(TRANSCRIPT_SOURCES, "transcript_source"), nullable=False)
    stage_times_ms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(_enum(AULA_STATUS, "processamento_status"), nullable=False)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_divergence_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ---- Tabelas internas (fora do modelo lógico compartilhado; nunca exportadas) ----

class Sessao(Base):
    __tablename__ = "sessao"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    acting_as_professor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("professor.id"), nullable=True)
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AudioUpload(Base):
    """Áudio recebido e ainda não validado (dados do schema Audio só existem após o ffprobe)."""
    __tablename__ = "audio_upload"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_filename: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_created", "status", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(_enum(JOB_STATUS, "job_status"), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AcessoAdmin(Base):
    __tablename__ = "acesso_admin"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), nullable=False)
    professor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("professor.id"), index=True, nullable=True)
    resource: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    action: Mapped[str] = mapped_column(_enum(ADMIN_ACTIONS, "admin_action"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
