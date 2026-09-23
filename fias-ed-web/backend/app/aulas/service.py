import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.audio.storage import work_rel
from app.audit import last_admin_change
from app.core.errors import AppError
from app.core.messages import error_message
from app.models import (Audio, AudioUpload, Aula, ClassificacaoFIAS, Disciplina, Falante,
                        IndicadorFIAS, Job, Processamento, Segmento, Transcricao, Turma, utcnow)


def get_owned_aula(db: Session, actor, aula_id: uuid.UUID) -> Aula:
    aula = db.scalar(select(Aula).where(Aula.id == aula_id, Aula.professor_id == actor.effective_professor_id,
                                        Aula.deleted_at.is_(None)))
    if aula is None:
        raise AppError(404, "AULA_NAO_ENCONTRADA", "Aula não encontrada.")
    return aula


def has_active_job(db: Session, aula_id: uuid.UUID) -> bool:
    return db.scalar(select(Job.id).where(Job.aula_id == aula_id, Job.status.in_(("queued", "running")))
                     .limit(1)) is not None


def current_audio(db: Session, aula_id: uuid.UUID) -> Audio | None:
    return db.scalar(select(Audio).where(Audio.aula_id == aula_id, Audio.is_original.is_(True),
                                         Audio.deleted_at.is_(None)))


def pending_upload(db: Session, aula_id: uuid.UUID) -> AudioUpload | None:
    return db.scalar(select(AudioUpload).where(AudioUpload.aula_id == aula_id))


def aula_summary(aula: Aula, turma: Turma, disciplina: Disciplina) -> dict:
    return {"id": str(aula.id), "lesson_date": aula.lesson_date.isoformat(), "status": aula.status,
            "turma": {"id": str(turma.id), "name": turma.name},
            "disciplina": {"id": str(disciplina.id), "name": disciplina.name}}


def aula_payload(db: Session, aula: Aula) -> dict:
    audio, upload = current_audio(db, aula.id), pending_upload(db, aula.id)
    changed = last_admin_change(db, aula.id)
    return {
        **aula_summary(aula, db.get(Turma, aula.turma_id), db.get(Disciplina, aula.disciplina_id)),
        "note": aula.note,
        "error_code": aula.error_code,
        "error_message": error_message(aula.error_code),
        "audio": None if audio is None else {
            "original_filename": audio.original_filename, "mime_type": audio.mime_type,
            "size_bytes": audio.size_bytes, "duration_ms": audio.duration_ms,
            "channels": audio.channels, "sample_rate": audio.sample_rate},
        "upload_pendente": None if upload is None else {
            "original_filename": upload.original_filename, "size_bytes": upload.size_bytes},
        "job_ativo": has_active_job(db, aula.id),
        "alterada_pelo_admin_em": changed.isoformat() if changed else None,
    }


def detach_audio(db: Session, aula: Aula, now: datetime | None = None) -> list[str]:
    """Desvincula o áudio atual da aula: apaga o upload pendente e marca os áudios como excluídos.

    Devolve os caminhos relativos a apagar do disco depois do commit. Reusado por
    soft_delete_aula (Task 7) e pela Task 8 (troca de áudio)."""
    now = now or utcnow()
    paths: list[str] = []
    upload = pending_upload(db, aula.id)
    if upload is not None:
        paths.append(upload.path)
        db.delete(upload)
    for audio in db.scalars(select(Audio).where(Audio.aula_id == aula.id, Audio.deleted_at.is_(None))):
        audio.deleted_at = now
        paths.append(audio.path)
    return paths


def apagar_transcricao(db: Session, aula_id: uuid.UUID) -> None:
    """Apaga fisicamente transcrição, segmentos, falantes e classificações da aula, na
    ordem das chaves estrangeiras (PRIVACY.md: exclusão real, não soft delete, para
    "áudio e transcrição" — Segmento carrega texto_original_asr, que traz fala e,
    até a pseudonimização, nomes; Falante e ClassificacaoFIAS dependem de Segmento/
    Transcricao por FK e são apagados junto).

    IndicadorFIAS não entra aqui, de propósito: não referencia Segmento nem
    Transcricao (só aula_id), não carrega texto nem nome — é o índice agregado que
    o PRIVACY.md descreve como "demais entidades", protegido por soft delete "para
    preservar o histórico necessário à reprodutibilidade científica", do mesmo jeito
    que Processamento já é tratado logo abaixo, em soft_delete_aula."""
    transcricao_ids = db.scalars(select(Transcricao.id).where(Transcricao.aula_id == aula_id)).all()
    if not transcricao_ids:
        return
    segmento_ids = db.scalars(
        select(Segmento.id).where(Segmento.transcricao_id.in_(transcricao_ids))).all()
    if segmento_ids:
        db.execute(delete(ClassificacaoFIAS).where(ClassificacaoFIAS.segmento_id.in_(segmento_ids)))
    db.execute(delete(Segmento).where(Segmento.transcricao_id.in_(transcricao_ids)))
    db.execute(delete(Falante).where(Falante.transcricao_id.in_(transcricao_ids)))
    db.execute(delete(Transcricao).where(Transcricao.id.in_(transcricao_ids)))


def soft_delete_aula(db: Session, aula: Aula) -> list[str]:
    now = utcnow()
    paths = detach_audio(db, aula, now)
    # A cópia de trabalho é áudio derivado do original — a mesma voz, a mesma
    # aula — e sai junto com ele. Sem esta linha ela sobrevivia à exclusão da
    # aula e da conta, porque detach_audio só conhece o que está na tabela Audio,
    # e a cópia de trabalho não tem linha em tabela nenhuma: ela é derivada do
    # UUID da aula. No caminho feliz o arquivo já foi apagado no fim da
    # diarização, e `delete_file` é silencioso quando não existe.
    paths.append(work_rel(aula.id))
    apagar_transcricao(db, aula.id)
    db.execute(update(Processamento).where(Processamento.aula_id == aula.id,
                                           Processamento.deleted_at.is_(None)).values(deleted_at=now))
    db.execute(update(IndicadorFIAS).where(IndicadorFIAS.aula_id == aula.id,
                                           IndicadorFIAS.deleted_at.is_(None)).values(deleted_at=now))
    aula.deleted_at = now
    return paths
