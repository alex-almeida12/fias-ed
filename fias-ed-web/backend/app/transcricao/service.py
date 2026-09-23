"""Grava a transcrição no banco: a linha de Transcricao, o falante provisório e
os segmentos.

Os tempos que chegam aqui em `segmentos` já são globais — a soma do
deslocamento de cada chunk acontece antes, no job (handle_transcribe), nunca
aqui. `Segmento` usa start_ms/end_ms (schema do fias-ed-shared); o protocolo
do ASR usa inicio_ms/fim_ms — a tradução entre os dois nomes é o único papel
deste módulo além de gravar.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.protocols import SegmentoASR
from app.models import Audio, Aula, Falante, Segmento, Transcricao
from app.pipeline.pseudonymize import pseudonimizar


def criar_transcricao(db: Session, aula: Aula, audio: Audio, asr_model_id: str) -> Transcricao:
    transcricao = Transcricao(aula_id=aula.id, audio_id=audio.id, asr_model_id=asr_model_id)
    db.add(transcricao)
    db.flush()
    return transcricao


def falante_provisorio(db: Session, transcricao: Transcricao) -> Falante:
    """A única linha à qual todo segmento aponta até a diarização (Task 7) trocá-la
    pelos falantes por voz. Segmento.falante_id é NOT NULL — role=UNASSIGNED é como
    o schema do shared resolve "ainda não se sabe quem falou", não uma FK nula."""
    falante = Falante(transcricao_id=transcricao.id, diarization_label="pendente", role="UNASSIGNED")
    db.add(falante)
    db.flush()
    return falante


def gravar_segmentos(db: Session, transcricao: Transcricao, segmentos: list[SegmentoASR],
                     falante: Falante) -> None:
    """text_pseudonymized é NOT NULL e é preenchido já nesta primeira gravação —
    escrever o texto cru "por enquanto" seria um vazamento silencioso se algo
    acima escorregasse (§48)."""
    for seg in segmentos:
        db.add(Segmento(transcricao_id=transcricao.id, falante_id=falante.id,
                        start_ms=seg.inicio_ms, end_ms=seg.fim_ms, texto_original_asr=seg.texto,
                        text_pseudonymized=pseudonimizar(seg.texto)))


def transcricao_da_aula(db: Session, aula_id: uuid.UUID) -> Transcricao | None:
    return db.scalar(select(Transcricao).where(Transcricao.aula_id == aula_id,
                                                Transcricao.deleted_at.is_(None)))


def segmentos_ordenados(db: Session, transcricao: Transcricao) -> list[Segmento]:
    """As linhas de Segmento da transcrição, na ordem em que ocorrem na aula —
    consulta única. Quem precisa tanto do protocolo do ASR (para alinhar())
    quanto de repontar falante_id depois (criar_falantes_provisorios) usa esta
    função uma vez só e converte com para_protocolo; duas consultas
    independentes, ambas ORDER BY start_ms sem chave de desempate, podem
    devolver ordens diferentes entre si quando dois segmentos têm o mesmo
    start_ms — e aí o repontamento por posição troca a voz de um trecho pela
    do outro em silêncio."""
    return list(db.scalars(select(Segmento).where(Segmento.transcricao_id == transcricao.id)
                           .order_by(Segmento.start_ms)).all())


def para_protocolo(linha: Segmento) -> SegmentoASR:
    """Traduz uma linha gravada (start_ms/end_ms) para o protocolo do ASR
    (inicio_ms/fim_ms) — a mesma tradução que segmentos_asr fazia inline."""
    return SegmentoASR(inicio_ms=linha.start_ms, fim_ms=linha.end_ms, texto=linha.texto_original_asr)


def segmentos_asr(db: Session, transcricao: Transcricao) -> list[SegmentoASR]:
    """Relê os segmentos gravados no formato do protocolo do ASR (inicio_ms/fim_ms),
    na ordem em que ocorrem na aula. Devolve o texto bruto do ASR — quem precisa do
    texto revisado quando houver usa texto_efetivo por segmento."""
    return [para_protocolo(linha) for linha in segmentos_ordenados(db, transcricao)]


def texto_efetivo(segmento: Segmento) -> str:
    """texto_revisado quando o professor já revisou o segmento, senão o texto
    bruto do ASR."""
    return segmento.texto_revisado if segmento.texto_revisado is not None else segmento.texto_original_asr
