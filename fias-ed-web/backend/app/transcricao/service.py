"""Grava a transcrição no banco: a linha de Transcricao, o falante provisório e
os segmentos.

Os tempos que chegam aqui em `segmentos` já são globais — a soma do
deslocamento de cada chunk acontece antes, no job (handle_transcribe), nunca
aqui. `Segmento` usa start_ms/end_ms (schema do fias-ed-shared); o protocolo
do ASR usa inicio_ms/fim_ms — a tradução entre os dois nomes é o único papel
deste módulo além de gravar.
"""
import math
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.ml.protocols import SegmentoASR
from app.models import AULA_STATUS, Audio, Aula, Falante, Segmento, Transcricao
from app.pipeline.align import MAX_AMOSTRAS, GrupoDeVoz
from app.pipeline.pseudonymize import pseudonimizar

BLOCO_MS = 300_000


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
    acima escorregasse (§48).

    `asr_confidence` existia no schema desde a W2 e nunca era escrito. Ele
    recebe a confiança do PRÓPRIO segmento (SegmentoASR.confianca), não a média
    da aula nem a do vizinho: é o valor da janela de decodificação que produziu
    aquele trecho, e é por ele que se saberá depois, sem reprocessar o áudio,
    quão bem o Whisper ouviu ali. Continua anulável: modelo falso e aula
    transcrita por uma versão anterior não têm o que gravar."""
    for seg in segmentos:
        db.add(Segmento(transcricao_id=transcricao.id, falante_id=falante.id,
                        start_ms=seg.inicio_ms, end_ms=seg.fim_ms, texto_original_asr=seg.texto,
                        asr_confidence=seg.confianca,
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
    return SegmentoASR(inicio_ms=linha.start_ms, fim_ms=linha.end_ms, texto=linha.texto_original_asr,
                       confianca=linha.asr_confidence)


def segmentos_asr(db: Session, transcricao: Transcricao) -> list[SegmentoASR]:
    """Relê os segmentos gravados no formato do protocolo do ASR (inicio_ms/fim_ms),
    na ordem em que ocorrem na aula. Devolve o texto bruto do ASR — quem precisa do
    texto revisado quando houver usa texto_efetivo por segmento."""
    return [para_protocolo(linha) for linha in segmentos_ordenados(db, transcricao)]


def texto_efetivo(segmento: Segmento) -> str:
    """texto_revisado quando o professor já revisou o segmento, senão o texto
    bruto do ASR."""
    return segmento.texto_revisado if segmento.texto_revisado is not None else segmento.texto_original_asr


def total_blocos(duracao_ms: int) -> int:
    """Quantos blocos de cinco minutos cabem no áudio da aula — o mesmo tamanho
    de página que segmentos_do_bloco usa para filtrar. Uma aula sem duração
    conhecida (áudio desvinculado) não tem blocos."""
    return math.ceil(duracao_ms / BLOCO_MS) if duracao_ms > 0 else 0


def segmentos_do_bloco(db: Session, transcricao: Transcricao, bloco: int) -> list[tuple[Segmento, str]]:
    """Os segmentos de um bloco de cinco minutos (0-based), cada um já com o
    papel (role) do falante resolvido numa única consulta — uma aula de 50
    minutos tem centenas de trechos; a tela busca um bloco por vez, não a
    transcrição inteira."""
    inicio, fim = bloco * BLOCO_MS, (bloco + 1) * BLOCO_MS
    linhas = db.execute(
        select(Segmento, Falante.role)
        .join(Falante, Falante.id == Segmento.falante_id)
        .where(Segmento.transcricao_id == transcricao.id, Segmento.start_ms >= inicio,
               Segmento.start_ms < fim)
        .order_by(Segmento.start_ms)
    ).all()
    return [(seg, papel) for seg, papel in linhas]


def segmento_payload(seg: Segmento, papel: str) -> dict:
    return {"id": str(seg.id), "start_ms": seg.start_ms, "end_ms": seg.end_ms,
            "texto": texto_efetivo(seg), "papel": papel, "version": seg.version,
            "revisado": seg.revisado}


def get_owned_segmento(db: Session, actor, segmento_id: uuid.UUID) -> tuple[Segmento, Aula]:
    """Trecho de uma aula do professor autenticado (ou de quem o admin está agindo
    como) — 404 para trecho de aula de outro professor, nunca 403; mesmo padrão de
    get_owned_aula (app.aulas.service). Devolve também a própria Aula (não só o id):
    quem chama precisa do `status` para decidir se a edição reabre a classificação
    (precisa_reclassificar) — o segmento em si nunca é logado, só `aula_id`."""
    linha = db.execute(
        select(Segmento, Aula)
        .join(Transcricao, Transcricao.id == Segmento.transcricao_id)
        .join(Aula, Aula.id == Transcricao.aula_id)
        .where(Segmento.id == segmento_id, Aula.professor_id == actor.effective_professor_id,
               Aula.deleted_at.is_(None))
    ).first()
    if linha is None:
        raise AppError(404, "SEGMENTO_NAO_ENCONTRADO", "Trecho não encontrado.")
    return linha[0], linha[1]


_INICIO_POS_CLASSIFICACAO = AULA_STATUS.index("FIAS_COMPLETED")
_FIM_POS_CLASSIFICACAO = AULA_STATUS.index("REPORT_READY")
# Toda posição do pipeline entre a primeira classificação e o relatório final,
# calculada a partir de AULA_STATUS (não um valor fixo) — hoje só FIAS_COMPLETED é
# alcançável nesta fatia, mas WAITING_QTI/QTI_COMPLETED/TRIANGULATED/
# MTSS_INTERPRETED já existem no enum para as tasks seguintes (QTI, triangulação,
# relatório) e passam a valer aqui sem tocar este arquivo de novo, contanto que
# continuem sendo inseridas em AULA_STATUS na ordem do pipeline, como já são.
# ERROR fica de fora de propósito: é um estado terminal alcançável de qualquer
# estágio (inclusive antes da classificação), não uma posição no pipeline — incluí-lo
# faria uma aula travada por erro de áudio, por exemplo, "reabrir" uma classificação
# que nunca aconteceu.
POS_CLASSIFICACAO = frozenset(AULA_STATUS[_INICIO_POS_CLASSIFICACAO:_FIM_POS_CLASSIFICACAO + 1])


def precisa_reclassificar(status_atual: str) -> bool:
    """spec §3: "se ele reabrir a revisão depois de FIAS_COMPLETED, a aula volta
    para READY_FOR_FIAS e reclassifica — evidência e resultado nunca ficam fora de
    sincronia". Vale para qualquer estágio depois da classificação, não só
    FIAS_COMPLETED (ver POS_CLASSIFICACAO)."""
    return status_atual in POS_CLASSIFICACAO


def falante_do_papel(db: Session, seg: Segmento, papel: str) -> Falante:
    """A linha de Falante (PROFESSOR ou ALUNO) da mesma transcrição do segmento.
    Trocar o falante de um trecho é apontar para a outra linha, não criar uma
    nova — Falante tem exatamente duas linhas depois da escolha da voz (Task 8)."""
    falante = db.scalar(select(Falante).where(Falante.transcricao_id == seg.transcricao_id,
                                              Falante.role == papel))
    if falante is None:
        raise AppError(409, "FALANTE_NAO_ENCONTRADO", "Esta aula ainda não tem os dois falantes definidos.")
    return falante


def revisar_segmento(db: Session, seg: Segmento, *, texto: str | None, papel: str | None,
                     version_esperada: int) -> bool:
    """Aplica a edição do professor num UPDATE só: compara `version` e incrementa
    na mesma instrução (WHERE id=... AND version=...), para que duas abas editando
    o mesmo trecho ao mesmo tempo nunca as duas ganhem em silêncio (Review Focus
    5) — a checagem e a escrita são atômicas no banco, não um "lê, compara em
    Python, escreve" que duas transações concorrentes poderiam passar as duas.

    Editar o texto regrava text_pseudonymized: se a correção reintroduz um nome
    de estudante, a versão pseudonimizada tem que acompanhar, senão a correção
    vira um vazamento (PRIVACY.md §48).

    Marca `revisado=True` sempre que a versão bate, mesmo numa chamada sem
    `texto`/`papel` (só a versão): `revisado` (exigido pelo schema do shared) é
    "o professor já passou por este trecho", distinto de `texto_revisado` (só
    grava quando o texto muda) — confirmar um trecho como correto sem editar
    nada também é revisão.

    Devolve False quando a versão não bateu (o trecho foi alterado por outra
    aba desde que quem chamou o leu, nada é escrito); True quando a edição foi
    aplicada."""
    valores: dict = {"version": Segmento.version + 1, "revisado": True}
    if texto is not None:
        valores["texto_revisado"] = texto
        valores["text_pseudonymized"] = pseudonimizar(texto)
    if papel is not None:
        valores["falante_id"] = falante_do_papel(db, seg, papel).id
    resultado = db.execute(update(Segmento).where(Segmento.id == seg.id, Segmento.version == version_esperada)
                           .values(**valores))
    return resultado.rowcount > 0


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
