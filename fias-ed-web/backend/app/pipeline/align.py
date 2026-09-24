"""Cruza os segmentos do ASR com os turnos do diarizador.

Função pura: não toca banco nem modelo. É aqui que mora a decisão de o que
fazer quando um segmento cruza a fronteira de dois turnos, que é o caso comum
de alguém interromper o professor no meio da frase.
"""
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from fias_ed_engine.intervals import SpeechSpan

from app.ml.protocols import SegmentoASR, TurnoDiar
from app.models import Falante, Segmento, Transcricao, TrechoDeFala

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


def criar_falantes_provisorios(db: Session, transcricao: Transcricao, linhas: list[Segmento],
                               rotulos: list[str | None]) -> None:
    """Cria um Falante (role=UNASSIGNED) por voz detectada, repontando cada
    segmento para o falante da sua voz, e apaga o falante provisório
    "pendente" que a Task 5 criou — mas só quando ele ficar sem segmentos.
    Um segmento sem rótulo (sem sobreposição com turno algum) permanece no
    provisório de propósito, então ele nem sempre pode ser apagado aqui.

    Recebe as linhas do banco (de segmentos_ordenados), não refaz a consulta:
    casar duas consultas independentes por posição — ambas ORDER BY start_ms,
    sem chave de desempate — deixa dois trechos com start_ms idêntico
    trocarem de voz em silêncio. `linhas` é a mesma lista que alimentou
    alinhar() (via para_protocolo), então a correspondência com `rotulos` é
    por identidade de objeto, não por uma segunda leitura do banco."""
    if len(linhas) != len(rotulos):
        raise ValueError("linhas e rótulos precisam ter o mesmo tamanho, na mesma ordem")
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


def _fala_por_numero_de_vozes(turnos: list[TurnoDiar]) -> list[tuple[int, int, int]]:
    """A linha do tempo de fala com quantas vozes ao mesmo tempo — sem quais.

    O rótulo do diarizador entra aqui e não sai: serve só para contar vozes
    DISTINTAS no mesmo instante, e some com o fim da função (§48, e o aviso que
    o próprio `TurnoDiar.rotulo` carrega). Trechos vizinhos com a mesma
    contagem são fundidos, o que apaga de quebra a troca de turno entre duas
    vozes: A falando e B falando viram um trecho só de uma voz.

    Trecho sem voz nenhuma não vira linha: ausência de linha É a não-fala, e
    gravar os dois lados duplicaria a mesma informação em duas versões que
    poderiam discordar."""
    pontos = sorted({t.inicio_ms for t in turnos} | {t.fim_ms for t in turnos})
    trechos: list[list[int]] = []
    for a, b in zip(pontos, pontos[1:]):
        vozes = len({t.rotulo for t in turnos if t.inicio_ms <= a < t.fim_ms})
        if vozes == 0:
            continue
        if trechos and trechos[-1][1] == a and trechos[-1][2] == vozes:
            trechos[-1][1] = b
        else:
            trechos.append([a, b, vozes])
    return [(a, b, n) for a, b, n in trechos]


def gravar_fala_detectada(db: Session, transcricao: Transcricao, turnos: list[TurnoDiar]) -> None:
    """Guarda a linha do tempo de fala que o separador de vozes encontrou.

    É a única cópia da evidência de fala/não-fala: logo depois desta função a
    cópia de trabalho do áudio é apagada, e a classificação FIAS só roda depois
    da revisão de vozes. Sem isto o motor mediria silêncio pelas lacunas entre
    segmentos do ASR, que o vad_filter do Whisper fecha — na aula medida, 21,5 s
    de lacuna de ASR contra 78,2 s de não-fala segundo o diarizador.

    Apaga o que houver antes de gravar: um retry do job de diarização reprocessa
    o estágio do início, e evidência duplicada viraria fala onde não houve."""
    db.execute(delete(TrechoDeFala).where(TrechoDeFala.transcricao_id == transcricao.id))
    db.add_all([TrechoDeFala(transcricao_id=transcricao.id, inicio_ms=a, fim_ms=b, n_vozes=n)
                for a, b, n in _fala_por_numero_de_vozes(turnos)])


def fala_detectada(db: Session, transcricao_id) -> list[SpeechSpan] | None:
    """Os trechos em que o separador de vozes ouviu fala, para o motor.

    `None`, e não lista vazia, quando não há trecho gravado: o motor precisa
    distinguir "o diarizador diz que não houve fala nenhuma" de "não se sabe
    onde houve fala" — no segundo caso ele cai nos próprios segmentos, que é
    pior, mas honesto. Aula diarizada antes da versão que passou a gravar a
    linha do tempo de fala cai nesse caso.

    `n_vozes` não viaja: nenhuma regra implementada hoje o usa. Ele fica
    gravado para a confusão (fias_rules.confusion), que vai precisar saber se
    havia mais de uma voz ao mesmo tempo — e que não se reconstrói depois, com
    o áudio já apagado."""
    linhas = db.scalars(select(TrechoDeFala)
                        .where(TrechoDeFala.transcricao_id == transcricao_id)
                        .order_by(TrechoDeFala.inicio_ms)).all()
    return [SpeechSpan(start_ms=t.inicio_ms, end_ms=t.fim_ms) for t in linhas] or None
