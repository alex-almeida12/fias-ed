"""Agregação turno → intervalos de codificação e matriz de transições FIAS."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CodedSegment:
    start_ms: int
    end_ms: int
    category: int


def _check(seg: CodedSegment) -> None:
    if seg.end_ms <= seg.start_ms or seg.start_ms < 0:
        raise ValueError(f"Segmento com tempo inválido: {seg}")
    if not 1 <= seg.category <= 10:
        raise ValueError(f"Categoria FIAS inválida: {seg.category}")


def segments_to_intervals(segments: list[CodedSegment], total_ms: int, rules: dict) -> list[int]:
    step = int(rules["coding"]["interval_seconds"] * 1000)
    gap = rules["aggregation"]["gap_category"]
    for s in segments:
        _check(s)
    ordered = sorted(segments, key=lambda s: s.start_ms)
    out: list[int] = []
    for k in range(math.ceil(total_ms / step)):
        lo, hi = k * step, min((k + 1) * step, total_ms)
        best, best_cov = gap, 0
        for s in ordered:  # ordem de início garante desempate pelo mais antigo
            cov = min(hi, s.end_ms) - max(lo, s.start_ms)
            if cov > best_cov:
                best, best_cov = s.category, cov
        out.append(best)
    return out


def transition_matrix(intervals: list[int], rules: dict) -> list[list[int]]:
    pad = rules["matrix"]["pad_category"]
    seq = [pad, *intervals, pad]
    m = [[0] * 10 for _ in range(10)]
    for a, b in zip(seq, seq[1:]):
        m[a - 1][b - 1] += 1
    return m
