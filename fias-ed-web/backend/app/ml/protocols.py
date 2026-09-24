"""Interfaces finas dos três modelos.

Os jobs dependem destes protocolos, nunca de faster-whisper, pyannote ou
transformers diretamente. É o que permite a suíte rodar sem GPU e sem pesos.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SegmentoASR:
    """Um trecho transcrito, com a qualidade da decodificação que o produziu.

    `confianca` é exp(avg_logprob) do faster-whisper — a média geométrica da
    probabilidade por token, que é o que cabe no intervalo 0–1 de
    `Segmento.asr_confidence` (schemas/entities/segmento.schema.json). Ela NÃO
    tem resolução de segmento: medida na aula real de 24 min, os três sinais de
    qualidade (avg_logprob, no_speech_prob, compression_ratio) são constantes
    dentro de cada janela de decodificação de 30 s — 213 segmentos vieram de 51
    janelas, 4,18 segmentos por janela, mediana de 28 s de aula por janela. O
    valor gravado em cada segmento é, portanto, o da janela que o produziu, e
    quem for usá-lo para decidir alguma coisa sobre um trecho de menos de 30 s
    está lendo uma resolução que o sinal não tem (fias_rules.confusion).

    `None` quando o ASR não informa qualidade (modelos falsos da suíte, e
    segmentos gravados antes desta versão)."""
    inicio_ms: int
    fim_ms: int
    texto: str
    confianca: float | None = None


@dataclass(frozen=True)
class TurnoDiar:
    inicio_ms: int
    fim_ms: int
    rotulo: str  # rótulo do diarizador; vive só em memória, nunca vai para o banco (§48)


class ASR(Protocol):
    def transcrever(self, caminho: Path, deslocamento_ms: int) -> list[SegmentoASR]:
        """Transcreve um chunk. Os tempos devolvidos já são globais."""


class Diarizador(Protocol):
    def turnos(self, caminho: Path) -> list[TurnoDiar]:
        """Turnos de fala do arquivo inteiro, agrupados por voz."""


class Classificador(Protocol):
    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        """Um vetor de 10 logits por par de turnos (text_a, text_b)."""
