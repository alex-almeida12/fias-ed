import subprocess  # nosec B404 - só para os tipos de exceção; nenhuma chamada aqui (prompt §57)
import uuid

from sqlalchemy.orm import Session

from app.audio.prepare import (audio_original, chunks_dir, cortar, descartar_trabalho, limpar_chunks,
                               normalizar, planejar_chunks, work_path)
from app.audio.probe import ProbeError, probe
from app.audio.storage import abs_path, delete_file
from app.audio.validation import ValidationFailed, check
from app.aulas.service import pending_upload
from app.core.config import get_settings
from app.core.logging import log_event
from app.fias.service import classificar_aula
from app.jobs.queue import enqueue, fail_job, finish_job
from app.ml.loader import obter_asr, obter_diarizador
from app.ml.protocols import SegmentoASR
from app.models import Audio, Aula, Job
from app.pipeline.align import alinhar, criar_falantes_provisorios, gravar_fala_detectada
from app.transcricao.service import (criar_transcricao, falante_provisorio, gravar_segmentos,
                                     para_protocolo, segmentos_ordenados, transcricao_da_aula)


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
        # AUDIO_VALIDATED não é parada para o professor: o spec manda seguir
        # direto para prepare_audio. O enqueue vai na MESMA transação que grava
        # o status (mesma lição da Task 12) — status commitado sem job na fila
        # deixaria a aula parada para sempre sem ninguém perceber.
        enqueue(db, aula.id, "prepare_audio")
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
    # Quem marca o estágio é o handler que faz o trabalho, no momento em que
    # começa: é a regra dos três handlers deste arquivo.
    aula.status, aula.error_code = "PREPROCESSING", None
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
    # A aula fica em PREPROCESSING com o job de transcrição na fila. Marcar
    # TRANSCRIBING aqui diria ao professor "transformando áudio em texto…" com o
    # job ainda parado atrás de quantas outras aulas houver, e um worker só.
    # O enqueue vai na mesma transação que fecha o job (lição da Task 12).
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
    # TRANSCRIBING é marcado aqui, no começo do trabalho, e não por quem
    # enfileirou este job: entre o enqueue e esta linha a aula pode passar horas
    # na fila, e dizer "transformando áudio em texto…" nesse tempo é falso.
    # Commitado antes do ASR porque o estágio dura o áudio inteiro — a tela do
    # professor precisa dele agora, não no fim. Repetir a marcação num retry é
    # inofensivo: o handler reprocessa o estágio do início e nenhum caminho aqui
    # depende do status anterior.
    aula.status, aula.error_code = "TRANSCRIBING", None
    db.commit()
    trabalho, dir_chunks = work_path(aula.id), chunks_dir(aula.id)
    # A cópia de trabalho NÃO é apagada aqui, embora os chunks sejam: a
    # diarização ainda vai lê-la inteira (handle_diarize), e é lá que ela morre.
    # Os chunks são diferentes — existem só para este estágio.
    # try/finally: se cortar() ou transcrever() levantar, a exceção sobe até o
    # worker, que faz rollback e retry — mas os pedaços já cortados ficariam no
    # disco para sempre. Numa aula de 90 min são centenas de MB por falha, e o
    # retry pode repetir isso mais de uma vez.
    try:
        plano = planejar_chunks(audio.duration_ms)
        chunks = cortar(trabalho, plano, dir_chunks)
        asr = obter_asr()
        segmentos: list[SegmentoASR] = []
        for chunk in chunks:
            # ASR devolve tempos locais ao chunk; a soma do deslocamento aqui é o
            # que torna o tempo gravado global — nenhuma camada acima sabe que
            # houve corte.
            segmentos.extend(asr.transcrever(chunk.caminho, chunk.inicio_ms))
    finally:
        limpar_chunks(dir_chunks)
    if not segmentos:
        # fail_job já marca a aula como ERROR/AUDIO_SEM_FALA; nenhuma atribuição
        # manual de status é necessária aqui.
        fail_job(db, job, "AUDIO_SEM_FALA")
        db.commit()
        # Terminal, como o caminho de erro da diarização: sem transcrição a
        # diarização nunca é enfileirada, então ninguém mais vai ler a cópia de
        # trabalho desta aula.
        descartar_trabalho(aula.id)
        log_event("transcricao_sem_fala", aula_id=aula.id, job_id=job.id)
        return
    transcricao = criar_transcricao(db, aula, audio, get_settings().asr_model_id)
    # Segmento.falante_id é NOT NULL: o schema do shared resolve "ainda não se sabe
    # quem falou" com role=UNASSIGNED, não com FK nula. A diarização (Task 7) troca
    # este falante provisório pelos falantes por voz.
    gravar_segmentos(db, transcricao, segmentos, falante_provisorio(db, transcricao))
    # TRANSCRIBED é o estado de repouso entre "a transcrição terminou" e "a
    # diarização começou" — o spec nomeia os dois (transcribe → TRANSCRIBING →
    # TRANSCRIBED). Quem marca DIARIZING é handle_diarize, ao começar.
    aula.status, aula.error_code = "TRANSCRIBED", None
    enqueue(db, aula.id, "diarize")
    finish_job(db, job)
    db.commit()
    log_event("transcricao_pronta", aula_id=aula.id, job_id=job.id, n_segmentos=len(segmentos))


def handle_diarize(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    transcricao = transcricao_da_aula(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or transcricao is None:
        finish_job(db, job)
        db.commit()
        return
    # Mesmo motivo do TRANSCRIBING: a aula chega aqui em TRANSCRIBED e só vira
    # DIARIZING quando o separador de vozes realmente começa. Reprocessar o
    # estágio depois de um retry regrava o mesmo status, sem efeito colateral.
    aula.status, aula.error_code = "DIARIZING", None
    db.commit()
    try:
        turnos = obter_diarizador().turnos(work_path(aula.id))
    except Exception:  # noqa: BLE001 - qualquer falha do separador de vozes vira erro de produto
        # fail_job já marca a aula como ERROR/DIARIZACAO_FALHOU; nenhuma atribuição
        # manual de status é necessária aqui (mesma lição da Task 5).
        fail_job(db, job, "DIARIZACAO_FALHOU")
        db.commit()
        # fail_job é terminal: não há retry, e uma aula em ERROR não volta ao
        # pipeline sem um áudio novo (que refaz a normalização). A cópia de
        # trabalho não tem mais leitor nenhum — depois do commit, para o arquivo
        # não sumir de um estado que o banco ainda não registrou.
        descartar_trabalho(aula.id)
        log_event("diarizacao_falhou", aula_id=aula.id, job_id=job.id)
        return
    # Uma consulta só: as mesmas linhas alimentam o alinhamento (via
    # para_protocolo) e o repontamento, para dois segmentos de start_ms igual
    # não trocarem de voz por causa de duas consultas independentes
    # desempatando a ordem de jeitos diferentes.
    linhas = segmentos_ordenados(db, transcricao)
    rotulos = alinhar([para_protocolo(linha) for linha in linhas], turnos)
    criar_falantes_provisorios(db, transcricao, linhas, rotulos)
    # A linha do tempo de fala fica gravada — quando houve voz e quantas ao
    # mesmo tempo, nunca quais (§48) —, porque daqui a três linhas a cópia de
    # trabalho do áudio some. A classificação FIAS, que roda depois da revisão
    # de vozes, precisa dela para aplicar a regra 4 de Flanders (silêncio de
    # 3 s ou mais = categoria 10) contra a fala de verdade, e não contra as
    # lacunas do ASR.
    gravar_fala_detectada(db, transcricao, turnos)
    aula.status, aula.error_code = "READY_FOR_SPEAKER_REVIEW", None
    finish_job(db, job)
    db.commit()
    # Fim da linha da cópia de trabalho: a diarização é o último estágio que a lê
    # (a revisão de vozes ouve trechos do áudio ORIGINAL, e a classificação só vê
    # texto). Sem isto ela ficava em disco para sempre — ~173 MB numa aula de 90
    # min, por aula, sobrevivendo à exclusão da aula e da conta.
    #
    # Depois do commit, e não antes, por causa do retry: enquanto o job não está
    # fechado, `recover_stale` pode devolvê-lo à fila e o handler reprocessa o
    # estágio do início, lendo este arquivo de novo. Se o processo morrer entre o
    # commit e esta linha, o arquivo fica — e aí quem fecha é
    # `limpar_trabalho_orfao`, no laço do worker.
    descartar_trabalho(aula.id)
    log_event("diarizacao_pronta", aula_id=aula.id, job_id=job.id, n_vozes=len(set(filter(None, rotulos))))


def handle_classify_fias(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    transcricao = transcricao_da_aula(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or transcricao is None:
        finish_job(db, job)
        db.commit()
        return
    classificar_aula(db, aula)
    aula.status, aula.error_code = "FIAS_COMPLETED", None
    finish_job(db, job)
    db.commit()
    log_event("fias_pronto", aula_id=aula.id, job_id=job.id)


HANDLERS = {
    "validate_audio": handle_validate_audio,
    "prepare_audio": handle_prepare_audio,
    "transcribe": handle_transcribe,
    "diarize": handle_diarize,
    "classify_fias": handle_classify_fias,
}
