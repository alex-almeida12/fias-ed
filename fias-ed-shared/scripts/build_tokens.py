"""Gera tokens.css (Web) e FiasTokens.kt (Compose) a partir de design-tokens/tokens.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "design-tokens"


def _lum(hex_color: str) -> float:
    c = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(fg: str, bg: str) -> float:
    a, b = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _pascal(name: str) -> str:
    return "".join(p.capitalize() for p in name.replace("_", "-").split("-"))


def build() -> None:
    t = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))
    colors = {**t["color"]["brand"], **t["color"]["semantic"]}
    out = ROOT / "build"
    out.mkdir(exist_ok=True)

    css = ["/* Gerado por scripts/build_tokens.py — não editar. */", ":root {"]
    css += [f"  --color-{k}: {v};" for k, v in colors.items()]
    css += [f"  --color-{k}: var(--color-{v});" for k, v in t["color"]["role"].items()]
    css += [f"  --color-fias-{k}: var(--color-{v});" for k, v in t["color"]["fias_groups"].items()]
    for key, f in t["font"].items():
        css.append(f"  --font-{key}: '{f['family']}', {f['fallback']};")
    for name, s in t["type_scale"].items():
        css.append(f"  --type-{name}-size: {s['size_px'] / 16:.4g}rem;")
        css.append(f"  --type-{name}-weight: {s['weight']};")
        css.append(f"  --type-{name}-line: {s['line']};")
        css.append(f"  --type-{name}-font: var(--font-{s['font']});")
    css += [f"  --space-{k}: {v}px;" for k, v in t["space_px"].items()]
    css += [f"  --radius-{k}: {v}px;" for k, v in t["radius_px"].items()]
    css += [f"  --border-{k}: {v}px;" for k, v in t["border_px"].items()]
    css.append("}")
    (out / "tokens.css").write_text("\n".join(css) + "\n", encoding="utf-8")

    kt = ["// Gerado por scripts/build_tokens.py — não editar.",
          "package br.ufersa.fiased.designsystem", "",
          "import androidx.compose.ui.graphics.Color", "import androidx.compose.ui.unit.dp", "",
          "object FiasTokens {"]
    kt += [f"    val {_pascal(k)} = Color(0xFF{v.lstrip('#').upper()})" for k, v in colors.items()]
    kt += [f"    val Space{k} = {v}.dp" for k, v in t["space_px"].items()]
    kt += [f"    val Radius{_pascal(k)} = {v}.dp" for k, v in t["radius_px"].items()]
    kt += [f"    val Border{_pascal(k)} = {v}.dp" for k, v in t["border_px"].items()]
    kt.append("}")
    (out / "FiasTokens.kt").write_text("\n".join(kt) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
    print("tokens.css e FiasTokens.kt gerados")
