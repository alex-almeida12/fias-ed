"""Interfaces finas dos três modelos.

Os jobs dependem destes protocolos, nunca de faster-whisper, pyannote ou
transformers diretamente. É o que permite a suíte rodar sem GPU e sem pesos.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SegmentoASR:
    inicio_ms: int
    fim_ms: int
    texto: str


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
