"""Baixa (uma vez) Ubuntu e Rokkitt do repositório google/fonts, registra hashes e gera WOFF2."""
import hashlib
import json
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont

BASE = "https://raw.githubusercontent.com/google/fonts/main/"
FILES = {
    "Ubuntu-Regular.ttf": "ufl/ubuntu/Ubuntu-Regular.ttf",
    "Ubuntu-Medium.ttf": "ufl/ubuntu/Ubuntu-Medium.ttf",
    "Ubuntu-Bold.ttf": "ufl/ubuntu/Ubuntu-Bold.ttf",
    "UFL.txt": "ufl/ubuntu/UFL.txt",
    "Rokkitt[wght].ttf": "ofl/rokkitt/Rokkitt%5Bwght%5D.ttf",
    "OFL-Rokkitt.txt": "ofl/rokkitt/OFL.txt",
}
OUT = Path(__file__).resolve().parents[1] / "design-tokens" / "fonts"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, rel in FILES.items():
        dest = OUT / name
        if not dest.exists():
            with urllib.request.urlopen(BASE + rel, timeout=60) as r:  # noqa: S310 (URL fixa, https)
                dest.write_bytes(r.read())
        manifest[name] = {"source": BASE + rel, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                          "size_bytes": dest.stat().st_size}
        if name.endswith(".ttf"):
            woff2 = dest.with_suffix(".woff2")
            font = TTFont(dest)
            font.flavor = "woff2"
            font.save(woff2)
            manifest[woff2.name] = {"derived_from": name, "sha256": hashlib.sha256(woff2.read_bytes()).hexdigest()}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(manifest)} arquivos registrados em {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
