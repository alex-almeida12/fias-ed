"""Gera rules/qti_config.json a partir do sistema avalie-seu-professor (fonte congelada).

Uso: python extract_qti.py [--check]   (--check: falha se o JSON atual divergir do extraído)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.paths import RULES_DIR, qti_system_dir  # noqa: E402

QTI_DIR = Path("src") / "domain" / "qti"
FILES = ["qtiItems.ts", "QtiOctant.ts", "qtiWeights.ts", "likertScale.ts"]
SRC = "avalie-seu-professor/src/domain/qti/"


def _read(name: str) -> str:
    return (qti_system_dir() / QTI_DIR / name).read_text(encoding="utf-8")


def _sha(name: str) -> str:
    return hashlib.sha256((qti_system_dir() / QTI_DIR / name).read_bytes()).hexdigest()


def build() -> dict:
    items_ts, oct_ts, w_ts, lik_ts = (_read(f) for f in FILES)
    a = float(re.search(r"WEIGHT_A\s*=\s*([0-9.]+)", w_ts).group(1))
    b = float(re.search(r"WEIGHT_B\s*=\s*([0-9.]+)", w_ts).group(1))
    sign = {"WEIGHT_A": a, "-WEIGHT_A": -a, "WEIGHT_B": b, "-WEIGHT_B": -b}
    weights = {m[0]: (sign[m[1]], sign[m[2]]) for m in re.findall(
        r"(oc[1-8]):\s*\{\s*agency:\s*(-?WEIGHT_[AB]),\s*communion:\s*(-?WEIGHT_[AB])\s*\}", w_ts)}
    octants = [{
        "code": code, "label_pt_br": pt, "label_en": en,
        "agency_weight": weights[code][0], "communion_weight": weights[code][1],
        "source_reference": SRC + "QtiOctant.ts; qtiWeights.ts (manual VIL-24, jan. 2013)",
        "validation_status": "validated",
    } for code, pt, en in re.findall(
        r'code:\s*"(oc[1-8])",\s*labelPtBr:\s*"([^"]+)",\s*labelEn:\s*"([^"]+)"', oct_ts)]
    items = [{
        "order": int(order), "id": f"qti24-item-{int(order):02d}", "text_pt_br": text, "octant": octant,
        "source_reference": SRC + "qtiItems.ts (textos congelados)",
        "validation_status": "PENDING_SCIENTIFIC_VALIDATION",
    } for order, octant, text in re.findall(r'item\((\d+),\s*"(oc[1-8])",\s*"([^"]+)"\)', items_ts)]
    stem = re.search(r'ITEM_STEM_PT_BR\s*=\s*"([^"]+)"', items_ts).group(1)
    min_label = re.search(r'LIKERT_MIN_LABEL_PT_BR\s*=\s*"([^"]+)"', lik_ts).group(1)
    max_label = re.search(r'LIKERT_MAX_LABEL_PT_BR\s*=\s*"([^"]+)"', lik_ts).group(1)
    if len(items) != 24 or len(octants) != 8 or len(weights) != 8:
        raise SystemExit(f"Extração incompleta: itens={len(items)} octantes={len(octants)}")
    return {
        "rules_version": "1.0.0",
        "instrument": {
            "name": "QTI-24 (Questionnaire on Teacher Interaction) — versão preliminar PT-BR",
            "version": "VIL-24 jan. 2013",
            "stem": stem,
            "likert": {"min": 1, "max": 5, "min_label": min_label, "max_label": max_label},
            "weights": {"a": a, "b": b},
            "min_responses": 10,
            "min_responses_note": "engineering_decision herdada de avalie-seu-professor (MIN_RESPONSES_FOR_PUBLIC_RESULT)",
            "license_note": "Instrumento de Wubbels e colegas (Universidade de Utrecht); uso não comercial; autorização formal pendente.",
            "sources": [{"path": SRC + f, "sha256": _sha(f)} for f in FILES],
            "source_reference": SRC + "* ; README.md §Cálculo do QTI-24 (fiel ao manual VIL-24, jan. 2013)",
            "validation_status": "PENDING_SCIENTIFIC_VALIDATION",
        },
        "octants": octants,
        "items": sorted(items, key=lambda i: i["order"]),
    }


def main() -> int:
    out = RULES_DIR / "qti_config.json"
    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        same = out.exists() and out.read_text(encoding="utf-8") == text
        print("OK — qti_config.json idêntico à fonte" if same else "DIVERGENTE — rode extract_qti.py")
        return 0 if same else 1
    out.write_text(text, encoding="utf-8")
    print(f"Gerado {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
