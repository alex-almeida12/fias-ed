"""Grava a transcrição no banco: a linha de Transcricao, o falante provisório e
os segmentos.

Os tempos que chegam aqui em `segmentos` já são globais — a soma do
deslocamento de cada chunk acontece antes, no job (handle_transcribe), nunca
aqui. `Segmento` usa start_ms/end_ms (schema do fias-ed-shared); o protocolo
do ASR usa inicio_ms/fim_ms — a tradução entre os dois nomes é o único papel
deste módulo além de gravar.
"""
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.ml.protocols import SegmentoASR
from app.models import Audio, Aula, Falante, Segmento, Transcricao
from app.pipeline.align import MAX_AMOSTRAS, GrupoDeVoz
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


class VozDesconhecida(Exception):
    """`rotulo` não corresponde a nenhuma das vozes provisórias da aula."""


def _vozes_provisorias(db: Session, transcricao_id: uuid.UUID) -> list[tuple[Falante, GrupoDeVoz]]:
    """Os falantes de voz que a diarização deixou (role=UNASSIGNED), cada um
    pareado com o resumo da própria fala, ordenados do que mais falou para o
    que menos falou — a mesma ordem em que a tela numera Voz 1, Voz 2… Esta
    ordem tem que ser idêntica entre `vozes_da_aula` (o que a tela lista) e
    `atribuir_papeis` (o que "voz-N" resolve): se divergissem, "Voz 1" na tela
    apontaria para um falante diferente do que a escolha grava.

    Um falante sem nenhum segmento (o "pendente" da Task 5, se ainda existir
    vazio) não é uma voz — fica fora da lista."""
    falantes = db.scalars(select(Falante).where(Falante.transcricao_id == transcricao_id,
                                                 Falante.role == "UNASSIGNED")).all()
    pares: list[tuple[Falante, GrupoDeVoz]] = []
    for f in falantes:
        segmentos = db.scalars(select(Segmento).where(Segmento.falante_id == f.id)
                               .order_by(Segmento.start_ms)).all()
        if not segmentos:
            continue
        tempo_total_ms = sum(s.end_ms - s.start_ms for s in segmentos)
        amostras = [(s.start_ms, s.end_ms) for s in segmentos[:MAX_AMOSTRAS]]
        pares.append((f, GrupoDeVoz(f.diarization_label, tempo_total_ms, len(segmentos), amostras)))
    pares.sort(key=lambda par: (-par[1].tempo_total_ms, par[1].rotulo))
    return pares


def vozes_da_aula(db: Session, aula: Aula) -> list[GrupoDeVoz]:
    """As vozes que a diarização separou nesta aula, para a tela "qual destas
    vozes é você?" (Task 8). O rótulo interno do diarizador (`GrupoDeVoz.rotulo`,
    ex.: "SPEAKER_00") não vaza para a API — quem numera como "voz-1", "voz-2"
    é a rota, na mesma ordem em que esta função devolve."""
    transcricao = transcricao_da_aula(db, aula.id)
    if transcricao is None:
        return []
    return [grupo for _, grupo in _vozes_provisorias(db, transcricao.id)]


def _indice_da_voz(rotulo: str, total: int) -> int | None:
    prefixo = "voz-"
    resto = rotulo[len(prefixo):] if rotulo.startswith(prefixo) else ""
    if not resto.isdigit():
        return None
    indice = int(resto) - 1
    return indice if 0 <= indice < total else None


def atribuir_papeis(db: Session, aula: Aula, rotulo: str) -> None:
    """Colapsa os falantes provisórios da diarização em exatamente dois:
    PROFESSOR (a voz escolhida) e ALUNO (tudo o mais, `diarization_label`
    "merged"). §48: nenhum agrupamento de voz por estudante sobrevive à
    escolha — os rótulos do diarizador são apagados depois de repontar os
    segmentos, não só esvaziados.

    Levanta `VozDesconhecida` se `rotulo` não corresponder a nenhuma voz
    (aula sem diarização ainda, ou índice fora do intervalo)."""
    transcricao = transcricao_da_aula(db, aula.id)
    pares = _vozes_provisorias(db, transcricao.id) if transcricao is not None else []
    indice = _indice_da_voz(rotulo, len(pares))
    if indice is None:
        raise VozDesconhecida()
    escolhido, _ = pares[indice]

    professor = Falante(transcricao_id=transcricao.id, diarization_label=escolhido.diarization_label,
                        role="PROFESSOR")
    aluno = Falante(transcricao_id=transcricao.id, diarization_label="merged", role="ALUNO")
    db.add_all([professor, aluno])
    db.flush()
    for falante, _ in pares:
        alvo_id = professor.id if falante.id == escolhido.id else aluno.id
        db.execute(update(Segmento).where(Segmento.falante_id == falante.id).values(falante_id=alvo_id))
    db.execute(delete(Falante).where(Falante.transcricao_id == transcricao.id, Falante.role == "UNASSIGNED"))
    db.flush()
