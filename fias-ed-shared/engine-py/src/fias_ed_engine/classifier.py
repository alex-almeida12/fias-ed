"""Pós-processamento das saídas do BERTimbau: confiança e restrição por papel do falante."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RolePrediction:
    pred_raw: int
    pred_role_constrained: int
    confidence_raw: float
    confidence: float
    uncertain: bool


def softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


def constrain_by_role(logits: list[float], role: str, rules: dict) -> RolePrediction:
    cfg = rules["classifier"]
    if len(logits) != 10:
        raise ValueError(f"Esperados 10 logits, recebidos {len(logits)}")
    if role not in cfg["role_categories"]:
        raise ValueError(f"Papel inválido: {role}")
    off = cfg["logit_index_offset"]
    probs = softmax(logits)
    raw_idx = max(range(10), key=lambda i: probs[i])
    allowed = [c - off for c in cfg["role_categories"][role]]
    con_idx = max(allowed, key=lambda i: probs[i])
    return RolePrediction(
        pred_raw=raw_idx + off,
        pred_role_constrained=con_idx + off,
        confidence_raw=probs[raw_idx],
        confidence=probs[con_idx],
        uncertain=probs[con_idx] < cfg["uncertain_below"],
    )


def divergence_rate(preds: list[RolePrediction]) -> float | None:
    if not preds:
        return None
    return sum(p.pred_raw != p.pred_role_constrained for p in preds) / len(preds)
