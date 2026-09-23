import subprocess  # nosec B404 - só para os tipos de exceção; nenhuma chamada aqui (prompt §57)
import uuid

from sqlalchemy.orm import Session

from app.audio.prepare import (audio_original, chunks_dir, cortar, limpar_chunks, normalizar,
                               planejar_chunks, work_path)
from app.audio.probe import ProbeError, probe
from app.audio.storage import abs_path, delete_file
from app.audio.validation import ValidationFailed, check
from app.aulas.service import pending_upload
from app.core.config import get_settings
from app.core.logging import log_event
from app.jobs.queue import enqueue, fail_job, finish_job
from app.ml.loader import obter_asr
from app.ml.protocols import SegmentoASR
from app.models import Audio, Aula, Job
from app.transcricao.service import criar_transcricao, falante_provisorio, gravar_segmentos


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


def handle_prepare_audio(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    audio = audio_original(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or audio is None:
        finish_job(db, job)
        db.commit()
        return
    # O professor precisa ver "Preparando sua aula…" durante a normalização, que
    # numa aula de 90 min é o estágio mais demorado. Sem isto, PREPROCESSING não
    # é usado por ninguém e a tela fica parada no status anterior.
    aula.status = "PREPROCESSING"
    db.commit()
    trabalho = work_path(aula.id)
    try:
        normalizar(abs_path(audio.path), trabalho)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        # fail_job é terminal: não há retry. Uma saída parcial do ffmpeg ficaria
        # órfã para sempre — mais de 170 MB numa aula de 90 min. handle_validate_audio
        # já faz a limpeza equivalente no seu caminho de erro.
        trabalho.unlink(missing_ok=True)
        fail_job(db, job, "AUDIO_PREPARO_FALHOU")
        db.commit()
        log_event("audio_prepare_failed", aula_id=aula.id, job_id=job.id)
        return
    aula.status, aula.error_code = "TRANSCRIBING", None
    enqueue(db, aula.id, "transcribe")
    finish_job(db, job)
    db.commit()
    log_event("audio_prepared", aula_id=aula.id, job_id=job.id)


def handle_transcribe(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    audio = audio_original(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or audio is None:
        finish_job(db, job)
        db.commit()
        return
    trabalho, dir_chunks = work_path(aula.id), chunks_dir(aula.id)
    plano = planejar_chunks(audio.duration_ms)
    chunks = cortar(trabalho, plano, dir_chunks)
    asr = obter_asr()
    segmentos: list[SegmentoASR] = []
    for chunk in chunks:
        # ASR devolve tempos locais ao chunk; a soma do deslocamento aqui é o que
        # torna o tempo gravado global — nenhuma camada acima sabe que houve corte.
        segmentos.extend(asr.transcrever(chunk.caminho, chunk.inicio_ms))
    limpar_chunks(dir_chunks)
    if not segmentos:
        # fail_job já marca a aula como ERROR/AUDIO_SEM_FALA; nenhuma atribuição
        # manual de status é necessária aqui.
        fail_job(db, job, "AUDIO_SEM_FALA")
        db.commit()
        log_event("transcricao_sem_fala", aula_id=aula.id, job_id=job.id)
        return
    transcricao = criar_transcricao(db, aula, audio, get_settings().asr_model_id)
    # Segmento.falante_id é NOT NULL: o schema do shared resolve "ainda não se sabe
    # quem falou" com role=UNASSIGNED, não com FK nula. A diarização (Task 7) troca
    # este falante provisório pelos falantes por voz.
    gravar_segmentos(db, transcricao, segmentos, falante_provisorio(db, transcricao))
    aula.status, aula.error_code = "DIARIZING", None
    enqueue(db, aula.id, "diarize")
    finish_job(db, job)
    db.commit()
    log_event("transcricao_pronta", aula_id=aula.id, job_id=job.id, n_segmentos=len(segmentos))


HANDLERS = {
    "validate_audio": handle_validate_audio,
    "prepare_audio": handle_prepare_audio,
    "transcribe": handle_transcribe,
}
