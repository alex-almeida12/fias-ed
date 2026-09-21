"""Confere SHA-256 e tamanho dos modelos registrados. Somente leitura.

Uso: python verify_models.py [caminho/models.json]
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.paths import SCIENTIFIC_CONFIG_DIR, experiments_dir  # noqa: E402


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(models_path: Path) -> list[str]:
    registry = json.loads(Path(models_path).read_text(encoding="utf-8"))
    base = experiments_dir()
    errors: list[str] = []
    for model in registry["models"]:
        for art in model["artifacts"]:
            p = base / art["relative_path"]
            if not p.is_file():
                errors.append(f"{model['model_id']}: ausente {art['relative_path']}")
                continue
            if p.stat().st_size != art["size_bytes"]:
                errors.append(f"{model['model_id']}: tamanho divergente {art['relative_path']}")
            if sha256_of(p) != art["sha256"]:
                errors.append(f"{model['model_id']}: sha256 divergente {art['relative_path']}")
    return errors


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else SCIENTIFIC_CONFIG_DIR / "models.json"
    errs = verify(target)
    for e in errs:
        print("ERRO:", e)
    print("OK — todos os modelos conferem" if not errs else f"{len(errs)} erro(s)")
    sys.exit(1 if errs else 0)
