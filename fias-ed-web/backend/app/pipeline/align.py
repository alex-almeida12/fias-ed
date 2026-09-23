"""Cruza os segmentos do ASR com os turnos do diarizador.

Função pura: não toca banco nem modelo. É aqui que mora a decisão de o que
fazer quando um segmento cruza a fronteira de dois turnos, que é o caso comum
de alguém interromper o professor no meio da frase.
"""
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.protocols import SegmentoASR, TurnoDiar
from app.models import Falante, Segmento, Transcricao

MAX_AMOSTRAS = 3


@dataclass(frozen=True)
class GrupoDeVoz:
    rotulo: str
    tempo_total_ms: int
    n_segmentos: int
    amostras: list[tuple[int, int]]


def _sobreposicao(a_ini: int, a_fim: int, b_ini: int, b_fim: int) -> int:
    return max(0, min(a_fim, b_fim) - max(a_ini, b_ini))


def alinhar(segmentos: list[SegmentoASR], turnos: list[TurnoDiar]) -> list[str | None]:
    rotulos: list[str | None] = []
    for seg in segmentos:
        melhor: str | None = None
        melhor_ms = 0
        melhor_inicio: int | None = None
        for turno in turnos:
            ms = _sobreposicao(seg.inicio_ms, seg.fim_ms, turno.inicio_ms, turno.fim_ms)
            if ms <= 0:
                continue
            # desempate: maior sobreposição; empatado, quem começou antes vence
            # — decidido pelo inicio_ms do turno, não pela ordem em que chegou
            # na lista, para o resultado ser o mesmo qualquer que seja a ordem.
            if melhor is None or ms > melhor_ms or (ms == melhor_ms and turno.inicio_ms < melhor_inicio):
                melhor, melhor_ms, melhor_inicio = turno.rotulo, ms, turno.inicio_ms
        rotulos.append(melhor)
    return rotulos


def resumo_por_voz(segmentos: list[SegmentoASR], rotulos: list[str | None]) -> list[GrupoDeVoz]:
    acumulado: dict[str, dict] = {}
    for seg, rotulo in zip(segmentos, rotulos):
        if rotulo is None:
            continue
        item = acumulado.setdefault(rotulo, {"ms": 0, "n": 0, "amostras": []})
        item["ms"] += seg.fim_ms - seg.inicio_ms
        item["n"] += 1
        if len(item["amostras"]) < MAX_AMOSTRAS:
            item["amostras"].append((seg.inicio_ms, seg.fim_ms))
    grupos = [GrupoDeVoz(r, v["ms"], v["n"], v["amostras"]) for r, v in acumulado.items()]
    return sorted(grupos, key=lambda g: g.tempo_total_ms, reverse=True)


def criar_falantes_provisorios(db: Session, transcricao: Transcricao, segmentos: list[SegmentoASR],
                               rotulos: list[str | None]) -> None:
    """Cria um Falante (role=UNASSIGNED) por voz detectada, repontando cada
    segmento para o falante da sua voz, e apaga o falante provisório
    "pendente" que a Task 5 criou — mas só quando ele ficar sem segmentos.
    Um segmento sem rótulo (sem sobreposição com turno algum) permanece no
    provisório de propósito, então ele nem sempre pode ser apagado aqui."""
    linhas = db.scalars(select(Segmento).where(Segmento.transcricao_id == transcricao.id)
                        .order_by(Segmento.start_ms)).all()
    if len(linhas) != len(segmentos) or len(segmentos) != len(rotulos):
        raise ValueError("segmentos e rótulos precisam estar alinhados 1:1 com os segmentos já gravados")
    provisorio = db.scalar(select(Falante).where(Falante.transcricao_id == transcricao.id,
                                                 Falante.diarization_label == "pendente"))
    falantes_por_rotulo: dict[str, Falante] = {}
    for linha, rotulo in zip(linhas, rotulos):
        if rotulo is None:
            continue  # fica no provisório, de propósito
        falante = falantes_por_rotulo.get(rotulo)
        if falante is None:
            falante = Falante(transcricao_id=transcricao.id, diarization_label=rotulo, role="UNASSIGNED")
            db.add(falante)
            db.flush()
            falantes_por_rotulo[rotulo] = falante
        linha.falante_id = falante.id
    db.flush()
    if provisorio is not None:
        restantes = db.scalar(select(func.count()).select_from(Segmento)
                              .where(Segmento.falante_id == provisorio.id))
        if restantes == 0:
            db.delete(provisorio)
            db.flush()
