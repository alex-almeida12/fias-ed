import hashlib
import os
import uuid
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.audio.prepare import extrair_trecho
from app.audio.storage import abs_path, delete_file, ensure_dirs, store_root
from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import aula_payload, current_audio, detach_audio, get_owned_aula, has_active_job
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.core.messages import error_message
from app.models import AudioUpload

router = APIRouter()

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "aac", "flac"}
UPLOAD_STATUSES = {"DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "ERROR"}


def sanitize_filename(raw: str) -> str:
    name = unquote(raw).replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip().strip(".")
    return name[:255] or "audio"


def extension_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _too_large() -> AppError:
    return AppError(413, "AUDIO_TOO_LARGE", error_message("AUDIO_TOO_LARGE"))


# upload_audio é async porque o streaming do corpo (request.stream()) exige um handler async,
# mas a escrita do arquivo e as chamadas ao banco abaixo são bloqueantes: isso travaria o event
# loop sob concorrência. Aceito aqui porque o sistema é single-user, uso local (ruling P16).
@router.put("/aulas/{aula_id}/audio", status_code=201)
async def upload_audio(aula_id: uuid.UUID, request: Request, actor: Actor = Depends(current_actor),
                       db: Session = Depends(get_db)):
    s = get_settings()
    aula = get_owned_aula(db, actor, aula_id)
    if aula.status not in UPLOAD_STATUSES:
        raise AppError(409, "AUDIO_LOCKED", error_message("AUDIO_LOCKED"))
    if has_active_job(db, aula.id):
        raise AppError(409, "AULA_BUSY", "Aguarde o processamento atual terminar.")
    original = sanitize_filename(request.headers.get("X-Filename", ""))
    ext = extension_of(original)
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(415, "AUDIO_UNSUPPORTED_FORMAT", error_message("AUDIO_UNSUPPORTED_FORMAT"))
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > s.max_upload_bytes:
        raise _too_large()

    ensure_dirs()
    internal = f"{uuid.uuid4()}.{ext}"
    tmp, final_rel = store_root() / "tmp" / internal, f"original/{internal}"
    digest, size = hashlib.sha256(), 0
    try:
        with tmp.open("wb") as fh:
            async for chunk in request.stream():
                size += len(chunk)
                if size > s.max_upload_bytes:
                    raise _too_large()
                digest.update(chunk)
                fh.write(chunk)
        if size == 0:
            raise AppError(422, "AUDIO_EMPTY", "O arquivo enviado está vazio.")
        os.replace(tmp, abs_path(final_rel))
        os.chmod(abs_path(final_rel), 0o440)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    old_paths = detach_audio(db, aula)
    db.add(AudioUpload(aula_id=aula.id, original_filename=original, internal_filename=internal,
                       path=final_rel, size_bytes=size, sha256=digest.hexdigest()))
    aula.status, aula.error_code = "AUDIO_IMPORTED", None
    audit(db, actor, "aula", aula.id, "upload")
    db.commit()
    for rel in old_paths:
        delete_file(rel)
    log_event("audio_uploaded", aula_id=aula.id)
    return aula_payload(db, aula)


@router.get("/aulas/{aula_id}/audio")
def play_audio(aula_id: uuid.UUID, inicio_ms: int | None = None, fim_ms: int | None = None,
               actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    audio = current_audio(db, aula.id)
    if audio is None:
        raise AppError(404, "AUDIO_NAO_ENCONTRADO", "Esta aula ainda não tem áudio conferido.")
    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    if inicio_ms is None and fim_ms is None:
        return FileResponse(abs_path(audio.path), media_type=audio.mime_type, content_disposition_type="inline")
    # Trecho avulso para audição (Task 8: ouvir a amostra de uma voz antes de
    # escolher qual é a do professor). É um corte de verdade via ffmpeg, não um
    # Range de bytes — o navegador não converte milissegundos em offset de byte
    # de um WAV/MP3/M4A/AAC/FLAC.
    if inicio_ms is None or fim_ms is None or inicio_ms < 0 or fim_ms <= inicio_ms:
        raise AppError(422, "TRECHO_INVALIDO", "Informe o início e o fim do trecho corretamente.")
    trecho = store_root() / "tmp" / f"trecho-{uuid.uuid4()}.wav"
    try:
        extrair_trecho(abs_path(audio.path), inicio_ms, fim_ms, trecho)
    except BaseException:
        # Mesmo padrão de upload_audio: se o ffmpeg levantar depois de já ter escrito
        # saída parcial (timeout, disco cheio, áudio corrompido no meio), nenhum
        # FileResponse chega a existir e o BackgroundTask abaixo nunca é criado — sem
        # isto o arquivo parcial ficaria em tmp/ para sempre.
        trecho.unlink(missing_ok=True)
        raise
    return FileResponse(trecho, media_type="audio/wav", content_disposition_type="inline",
                        background=BackgroundTask(trecho.unlink))
