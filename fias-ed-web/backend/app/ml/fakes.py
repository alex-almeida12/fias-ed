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
    def __init__(self, categoria_fixa: int | None = 1) -> None:
        # None → vetor uniforme (nenhuma categoria domina): usado para testar o
        # limiar de incerteza do shared (fias_rules.classifier.uncertain_below),
        # sem inventar um segundo cálculo de confiança aqui.
        self._indice = None if categoria_fixa is None else categoria_fixa - 1  # logit_index_offset = 1
        # Guarda o que recebeu para que um teste possa checar a ENTRADA do
        # modelo, e não só a saída: o par (text_a, text_b) é decidido no Web a
        # partir do papel do falante, e um par montado errado não quebra nada
        # visivelmente — só muda a categoria de dois terços da aula.
        self.pares_recebidos: list[tuple[str, str]] = []

    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        self.pares_recebidos.extend(pares)
        vetor = [0.0] * 10
        if self._indice is not None:
            vetor[self._indice] = 10.0
        return [list(vetor) for _ in pares]
