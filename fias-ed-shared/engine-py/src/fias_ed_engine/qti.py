"""Pontuação determinística do QTI-24 (manual VIL-24) e importação do dataset exportado."""
import csv
import io
import math


class IncompleteResponseError(ValueError):
    pass


class QtiImportError(ValueError):
    pass


def _validate(answers: dict[int, int], cfg: dict) -> None:
    lo, hi = cfg["instrument"]["likert"]["min"], cfg["instrument"]["likert"]["max"]
    n = len(cfg["items"])
    if set(answers) != set(range(1, n + 1)):
        raise IncompleteResponseError(f"Resposta incompleta: esperados {n} itens, recebidos {len(answers)}.")
    for order, v in answers.items():
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise IncompleteResponseError(f"Item {order} fora da escala {lo}–{hi}.")


def score_response(answers: dict[int, int], cfg: dict) -> dict:
    _validate(answers, cfg)
    b = cfg["instrument"]["weights"]["b"]
    octants: dict[str, float] = {}
    for o in cfg["octants"]:
        vals = [answers[i["order"]] for i in cfg["items"] if i["octant"] == o["code"]]
        octants[o["code"]] = (sum(vals) / len(vals) - 1) / 4
    agency = b * sum(o["agency_weight"] * octants[o["code"]] for o in cfg["octants"])
    communion = b * sum(o["communion_weight"] * octants[o["code"]] for o in cfg["octants"])
    return {"octants": octants, "agency": agency, "communion": communion}


def aggregate(responses: list[dict[int, int]], cfg: dict) -> dict:
    n = len(responses)
    if n == 0:
        return {"response_count": 0, "displayable": False, "octants": None, "agency": None, "communion": None}
    scores = [score_response(r, cfg) for r in responses]
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return {
        "response_count": n,
        "displayable": n >= cfg["instrument"]["min_responses"],
        "octants": {o["code"]: mean([s["octants"][o["code"]] for s in scores]) for o in cfg["octants"]},
        "agency": mean([s["agency"] for s in scores]),
        "communion": mean([s["communion"] for s in scores]),
    }


def parse_export_csv(text: str, cfg: dict) -> list[dict[int, int]]:
    reader = csv.DictReader(io.StringIO(text))
    n = len(cfg["items"])
    needed = [f"q{i}" for i in range(1, n + 1)]
    missing = [c for c in needed if c not in (reader.fieldnames or [])]
    if missing:
        raise QtiImportError(f"Colunas ausentes: {', '.join(missing)}")
    out: list[dict[int, int]] = []
    for line_no, row in enumerate(reader, start=2):
        try:
            ans = {i: int(row[f"q{i}"]) for i in range(1, n + 1)}
            s = score_response(ans, cfg)
        except (ValueError, IncompleteResponseError) as exc:
            raise QtiImportError(f"Linha {line_no}: {exc}") from exc
        checks = {**s["octants"], "agency": s["agency"], "communion": s["communion"]}
        for col, expected in checks.items():
            if row.get(col) not in (None, "") and not math.isclose(float(row[col]), expected, abs_tol=1e-9):
                raise QtiImportError(f"Linha {line_no}: coluna {col} diverge do recálculo")
        out.append(ans)
    return out
