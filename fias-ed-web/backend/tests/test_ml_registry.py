import hashlib
import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.ml.registry import (
    STATUS_ADOTAVEIS,
    ModeloInvalido,
    _ler,
    entrada,
    entrada_adotavel,
    verificar_artefatos,
)


def _escrever(caminho: Path, conteudo: bytes) -> str:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    return hashlib.sha256(conteudo).hexdigest()


@pytest.fixture()
def base_falsa(tmp_path, monkeypatch):
    """Monta um diretório que casa com uma entrada de registro inventada."""
    # Limpar cache na entrada
    get_settings.cache_clear()
    _ler.cache_clear()

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
    # Criar o arquivo na estrutura correta: scientific-config/models.json
    caminho = tmp_path / "scientific-config" / "models.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(registro), encoding="utf-8")
    monkeypatch.setenv("SHARED_DIR", str(tmp_path))

    yield tmp_path

    # Limpar cache na saída
    get_settings.cache_clear()
    _ler.cache_clear()


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


def test_cache_por_caminho_com_registros_diferentes(tmp_path, monkeypatch):
    """Valida que cache funciona por caminho com registros diferentes."""
    # Limpar cache na entrada
    get_settings.cache_clear()
    _ler.cache_clear()

    # Primeiro registro com model_id "primeiro"
    tmp_path_1 = tmp_path / "dir1"
    conteudo_1 = b"pesos-primeiro"
    sha_1 = _escrever(tmp_path_1 / "m" / "model.safetensors", conteudo_1)
    registro_1 = {
        "registry_version": "1.0.0",
        "models": [{
            "model_id": "primeiro", "task": "fias_utterance_classification",
            "artifacts": [{"role": "weights", "relative_path": "m/model.safetensors",
                           "sha256": sha_1, "size_bytes": len(conteudo_1)}],
            "forbidden_files": [],
            "label_map": "fias_category = argmax(logits) + 1",
        }],
    }
    caminho_1 = tmp_path_1 / "scientific-config" / "models.json"
    caminho_1.parent.mkdir(parents=True, exist_ok=True)
    caminho_1.write_text(json.dumps(registro_1), encoding="utf-8")
    monkeypatch.setenv("SHARED_DIR", str(tmp_path_1))

    # Verificar que consegue carregar o primeiro
    e1 = entrada("primeiro")
    assert e1["model_id"] == "primeiro"

    # Segundo registro com model_id "segundo", em diretório diferente
    tmp_path_2 = tmp_path / "dir2"
    conteudo_2 = b"pesos-segundo"
    sha_2 = _escrever(tmp_path_2 / "m" / "model.safetensors", conteudo_2)
    registro_2 = {
        "registry_version": "1.0.0",
        "models": [{
            "model_id": "segundo", "task": "fias_utterance_classification",
            "artifacts": [{"role": "weights", "relative_path": "m/model.safetensors",
                           "sha256": sha_2, "size_bytes": len(conteudo_2)}],
            "forbidden_files": [],
            "label_map": "fias_category = argmax(logits) + 1",
        }],
    }
    caminho_2 = tmp_path_2 / "scientific-config" / "models.json"
    caminho_2.parent.mkdir(parents=True, exist_ok=True)
    caminho_2.write_text(json.dumps(registro_2), encoding="utf-8")
    monkeypatch.setenv("SHARED_DIR", str(tmp_path_2))

    # Limpar settings cache para forçar re-leitura da env var
    get_settings.cache_clear()

    # Verificar que consegue carregar o segundo e NOT o primeiro
    e2 = entrada("segundo")
    assert e2["model_id"] == "segundo"

    # Tentar buscar "primeiro" no segundo registro deve falhar
    with pytest.raises(ModeloInvalido) as exc:
        entrada("primeiro")
    assert exc.value.code == "MODELO_NAO_REGISTRADO"

    # Limpar cache na saída
    get_settings.cache_clear()
    _ler.cache_clear()


# --- Adoção: estar no registro deixou de bastar ---------------------------
#
# O registro guarda dois tipos de modelo desde que a medição do §21 recuperou a
# procedência que tinha perdido: o que o produto usa e o que só produziu números
# publicados. `faster-whisper-tiny` e `faster-whisper-base` estão lá porque o
# pino de versão deles é a única coisa que torna aquelas seis linhas de tabela
# recuperáveis — não porque alguém os adotou. A diferença entre as duas coisas é
# `validation_status`, e é `entrada_adotavel` quem a cobra.


def _registro_de(**status_por_modelo: str) -> dict:
    return {"registry_version": "1.0.0",
            "models": [{"model_id": mid, "artifacts": [], "validation_status": st}
                       for mid, st in status_por_modelo.items()]}


@pytest.fixture()
def registro_de_estados(tmp_path, monkeypatch):
    """Instala um registro com um modelo por estado de validação."""
    get_settings.cache_clear()
    _ler.cache_clear()

    def instalar(**status_por_modelo: str) -> None:
        caminho = tmp_path / "scientific-config" / "models.json"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(_registro_de(**status_por_modelo)), encoding="utf-8")
        monkeypatch.setenv("SHARED_DIR", str(tmp_path))
        get_settings.cache_clear()
        _ler.cache_clear()

    yield instalar

    get_settings.cache_clear()
    _ler.cache_clear()


def test_modelo_de_procedencia_e_recusado_ao_carregar(registro_de_estados):
    """O estado novo recusa, e a mensagem diz por que ele existe."""
    registro_de_estados(medido="PENDING_SCIENTIFIC_VALIDATION")

    with pytest.raises(ModeloInvalido) as exc:
        entrada_adotavel("medido")

    assert exc.value.code == "MODELO_NAO_ADOTAVEL"
    mensagem = str(exc.value)
    assert "medido" in mensagem, "não disse qual modelo foi recusado"
    assert "PENDING_SCIENTIFIC_VALIDATION" in mensagem, "não disse em que estado ele está"
    assert "procedência" in mensagem and "não para autorizar o uso" in mensagem, \
        "recusou sem explicar que a entrada existe para a procedência de uma medição"
    # E continua legível como declaração: a procedência não some junto com a recusa.
    assert entrada("medido")["validation_status"] == "PENDING_SCIENTIFIC_VALIDATION"


def test_os_estados_adotados_continuam_carregando(registro_de_estados):
    registro_de_estados(**{st: st for st in STATUS_ADOTAVEIS})

    for status in STATUS_ADOTAVEIS:
        assert entrada_adotavel(status)["model_id"] == status


def test_estado_desconhecido_entra_recusado(registro_de_estados):
    """Lista de permitidos: o vocabulário de `validation_status` é do shared e
    pode crescer sem que este repositório saiba. Um estado que ninguém aqui
    examinou não pode virar adoção por omissão."""
    registro_de_estados(novo="draft_pending_researcher_review", sem_estado_nenhum="")

    for model_id in ("novo", "sem_estado_nenhum"):
        with pytest.raises(ModeloInvalido) as exc:
            entrada_adotavel(model_id)
        assert exc.value.code == "MODELO_NAO_ADOTAVEL"


def test_o_asr_recusa_carregar_um_tamanho_que_so_tem_procedencia(monkeypatch):
    """O caminho de produção de verdade, contra o registro de verdade.

    `WhisperASR.__init__` é o ponto onde um tamanho vira o modelo do produto.
    Com `tiny` — que está no registro pela medição do §21 — ele para antes de
    tocar em peso nenhum (não há peso em disco nesta suíte, e o teste passa
    justamente porque a recusa vem antes).
    """
    get_settings.cache_clear()
    _ler.cache_clear()
    monkeypatch.setenv("ASR_MODEL_ID", "faster-whisper-tiny")
    get_settings.cache_clear()
    try:
        from app.ml.asr_whisper import WhisperASR

        with pytest.raises(ModeloInvalido) as exc:
            WhisperASR()
    finally:
        get_settings.cache_clear()
        _ler.cache_clear()

    assert exc.value.code == "MODELO_NAO_ADOTAVEL"
    assert "faster-whisper-tiny" in str(exc.value)
    assert "procedência" in str(exc.value), "recusou sem dizer para que a entrada serve"


def test_tiny_e_base_tem_procedencia_no_registro_e_nao_sao_adotaveis():
    """As duas metades do conserto, contra o registro de verdade.

    A medição do §21 publica seis linhas feitas com `tiny` e `base`. Sem entrada
    no registro, o pino daqueles pesos não existia em lugar nenhum e a medição
    deixava de ser reproduzível; com entrada e sem estado que os recuse, o
    registro estaria declarando adotável um tamanho que ninguém validou.
    """
    get_settings.cache_clear()
    _ler.cache_clear()
    for model_id in ("faster-whisper-tiny", "faster-whisper-base"):
        m = entrada(model_id)
        repos = m["integrity"]["repos"]
        assert [r for r in repos if len(r.get("revision", "")) == 40], \
            f"{model_id} está no registro sem revisão fixada: a medição volta a não ser reproduzível"
        assert m["validation_status"] not in STATUS_ADOTAVEIS, \
            f"{model_id} virou adotável sem validação científica do tamanho"
        with pytest.raises(ModeloInvalido):
            entrada_adotavel(model_id)
