"""Verificação da linguagem formativa (nada de julgamento ou rótulo de desempenho)."""
import re

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    ("errado", r"\berrad[oa]s?\b"),
    ("ruim", r"\bru(im|ins)\b"),
    ("inadequado", r"\binadequad[oa]s?\b"),
    ("nota", r"\bnotas?\b"),
    ("desempenho", r"\bdesempenhos?\b"),
    ("fracasso", r"\bfracass(o|os|ou)\b"),
    ("deveria ter", r"\bdeveria ter\b"),
    ("conforme", r"\bconforme\b"),
    ("não conforme", r"\bn[ãa]o conforme\b"),
    ("reprovado", r"\breprovad[oa]s?\b"),
    ("avaliação docente", r"\bavalia[çc][ãa]o docente\b"),
]


def find_forbidden(text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in FORBIDDEN_PATTERNS:
        if label not in hits and re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(label)
    return hits
