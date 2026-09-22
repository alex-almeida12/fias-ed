import hashlib
import json
from pathlib import Path

import pytest

from app.ml.registry import ModeloInvalido, entrada, verificar_artefatos


def _escrever(caminho: Path, conteudo: bytes) -> str:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    return hashlib.sha256(conteudo).hexdigest()


@pytest.fixture()
def base_falsa(tmp_path, monkeypatch):
    """Monta um diretório que casa com uma entrada de registro inventada."""
    conteudo = b"pesos-de-mentira"
    sha = _escrever(tmp_path / "m" / "model.safetensors", conteudo)
    registro = {
        "registry_version": "1.0.0",
        "models": [{
            "model_id": "teste", "task": "fias_utterance_classification",
            "artifacts": [{"role": "weights", "relative_path": "m/model.safetensors",
                           "sha256": sha, "size_bytes": len(conteudo)}],
            "forbidden_files": ["optimizer.pt"],
            "label_map": "fias_category = argmax(logits) + 1",
        }],
    }
    caminho = tmp_path / "models.json"
    caminho.write_text(json.dumps(registro), encoding="utf-8")
    monkeypatch.setenv("FIAS_ED_MODELS_REGISTRY", str(caminho))
    return tmp_path


def test_artefatos_integros_passam(base_falsa):
    verificar_artefatos("teste", base_falsa)  # não levanta


def test_sha256_divergente_recusa(base_falsa):
    (base_falsa / "m" / "model.safetensors").write_bytes(b"outra-coisa")
    with pytest.raises(ModeloInvalido) as exc:
        verificar_artefatos("teste", base_falsa)
    assert exc.value.code == "MODELO_SHA256_DIVERGENTE"


def test_artefato_ausente_recusa(base_falsa):
    (base_falsa / "m" / "model.safetensors").unlink()
    with pytest.raises(ModeloInvalido) as exc:
        verificar_artefatos("teste", base_falsa)
    assert exc.value.code == "MODELO_ARTEFATO_AUSENTE"


def test_arquivo_proibido_recusa(base_falsa):
    # §67: restos de treino não podem ser distribuídos junto com os pesos.
    (base_falsa / "m" / "optimizer.pt").write_bytes(b"x")
    with pytest.raises(ModeloInvalido) as exc:
        verificar_artefatos("teste", base_falsa)
    assert exc.value.code == "MODELO_ARQUIVO_PROIBIDO"


def test_entrada_desconhecida_recusa(base_falsa):
    with pytest.raises(ModeloInvalido) as exc:
        entrada("nao-existe")
    assert exc.value.code == "MODELO_NAO_REGISTRADO"
