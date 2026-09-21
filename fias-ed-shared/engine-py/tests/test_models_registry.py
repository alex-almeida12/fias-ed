import hashlib
import json
import sys
from pathlib import Path

import pytest

from fias_ed_engine.paths import SCIENTIFIC_CONFIG_DIR, SHARED_ROOT, experiments_dir
from fias_ed_engine.traceability import find_untraced

sys.path.insert(0, str(SHARED_ROOT / "scripts"))
import verify_models  # noqa: E402

MODELS = SCIENTIFIC_CONFIG_DIR / "models.json"


def test_registry_traced():
    data = json.loads(MODELS.read_text(encoding="utf-8"))
    assert find_untraced(data["models"]) == []
    targets = json.loads((SCIENTIFIC_CONFIG_DIR / "metric_targets.json").read_text(encoding="utf-8"))
    assert find_untraced(targets["targets"]) == []


def test_no_pickle_artifacts_registered():
    data = json.loads(MODELS.read_text(encoding="utf-8"))
    for m in data["models"]:
        for a in m["artifacts"]:
            assert not a["relative_path"].endswith((".bin", ".pt", ".pth", ".pkl", ".joblib"))


def test_verify_detects_mismatch(tmp_path, monkeypatch):
    f = tmp_path / "x" / "w.onnx"
    f.parent.mkdir()
    f.write_bytes(b"abc")
    reg = {"models": [{"model_id": "t", "artifacts": [
        {"role": "weights", "relative_path": "x/w.onnx", "size_bytes": 3,
         "sha256": hashlib.sha256(b"abd").hexdigest()}]}]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setenv("FIAS_ED_EXPERIMENTS_DIR", str(tmp_path))
    errors = verify_models.verify(p)
    assert len(errors) == 1 and "sha256" in errors[0]


@pytest.mark.skipif(not experiments_dir().exists(), reason="experimentos indisponíveis")
def test_real_models_match_registry():
    assert verify_models.verify(MODELS) == []
