"""Implementações falsas, usadas só em teste. Nunca importadas em produção
fora do loader, que só as escolhe com usar_modelos_falsos = True.
"""
from dataclasses import replace
from pathlib import Path

from app.ml.protocols import SegmentoASR, TurnoDiar


class ASRFalso:
    def __init__(self, segmentos: list[SegmentoASR]) -> None:
        self._segmentos = segmentos

    def transcrever(self, caminho: Path, deslocamento_ms: int) -> list[SegmentoASR]:
        return [replace(s, inicio_ms=s.inicio_ms + deslocamento_ms, fim_ms=s.fim_ms + deslocamento_ms)
                for s in self._segmentos]


class DiarizadorFalso:
    def __init__(self, turnos: list[TurnoDiar]) -> None:
        self._turnos = turnos

    def turnos(self, caminho: Path) -> list[TurnoDiar]:
        return list(self._turnos)


class ClassificadorFalso:
    def __init__(self, categoria_fixa: int = 1) -> None:
        self._indice = categoria_fixa - 1  # logit_index_offset = 1

    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        vetor = [0.0] * 10
        vetor[self._indice] = 10.0
        return [list(vetor) for _ in pares]
