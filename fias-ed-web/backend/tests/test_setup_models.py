"""scripts/setup_models.py: uma falha não pode esconder o estado dos outros modelos.

O script rodou meses na ordem pyannote → BERTimbau → Whisper abortando no
primeiro erro. Enquanto os repositórios *gated* do pyannote devolveram 403, o
BERTimbau — que só copia do disco, sem rede e sem licença — nunca chegou a ser
copiado, e ninguém soube se ele estava bem. Estes testes fixam o conserto: cada
modelo tenta por si, os erros são coletados, e `MODELOS OK` continua exigindo os
três.

Nada aqui toca a rede nem o disco de verdade: os três passos são substituídos.
"""
import importlib.util
from pathlib import Path

import pytest

# O script não é módulo do pacote `app`: mora em scripts/, que o
# docker-compose.test.yml monta em /app/scripts, ao lado de tests/.
CAMINHO = Path(__file__).resolve().parents[1] / "scripts" / "setup_models.py"


@pytest.fixture(scope="module")
def setup_models():
    spec = importlib.util.spec_from_file_location("setup_models", CAMINHO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("FIAS_ED_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("FIAS_ED_EXPERIMENTS_DIR", str(tmp_path / "experimentos"))
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "token-de-mentira")
    monkeypatch.setenv("FIAS_ED_ASR_SIZE", "small")


@pytest.fixture
def passos(monkeypatch, setup_models):
    """Substitui os três passos e registra quem chegou a rodar."""
    rodaram: list[str] = []

    def registrar(nome, erro=None):
        def passo(*_args, **_kwargs):
            rodaram.append(nome)
            if erro is not None:
                raise erro
        return passo

    def configurar(**erros):
        for nome, atributo in (("pyannote", "passo_pyannote"),
                               ("BERTimbau", "passo_bertimbau"),
                               ("faster-whisper", "passo_whisper")):
            monkeypatch.setattr(setup_models, atributo, registrar(nome, erros.get(atributo)))
        return rodaram

    return configurar


def test_o_403_do_pyannote_nao_impede_os_outros(setup_models, ambiente, passos, capsys):
    gated = setup_models.FalhaDeModelo("acesso negado a pyannote/segmentation-3.0")
    rodaram = passos(passo_pyannote=gated)

    codigo = setup_models.main([])

    assert rodaram == ["pyannote", "BERTimbau", "faster-whisper"], \
        "o passo que falhou levou os outros junto"
    saida = capsys.readouterr()
    assert codigo == 1, "com um modelo faltando o setup não pode passar"
    assert "MODELOS OK" not in saida.out, "declarou OK com o pyannote faltando"
    assert "pyannote" in saida.err and "acesso negado" in saida.err, \
        "o relatório não diz qual modelo falhou nem por quê"
    assert "BERTimbau" not in saida.err and "faster-whisper" not in saida.err, \
        "acusou de falha quem passou"


def test_todos_passando_declara_modelos_ok(setup_models, ambiente, passos, capsys):
    rodaram = passos()

    codigo = setup_models.main([])

    assert rodaram == ["pyannote", "BERTimbau", "faster-whisper"]
    assert codigo == 0
    assert "MODELOS OK" in capsys.readouterr().out


def test_erro_inesperado_tambem_e_coletado(setup_models, ambiente, passos, capsys):
    """Não é só o 403: disco cheio ou rede caída também não podem parar os outros."""
    rodaram = passos(passo_bertimbau=OSError("No space left on device"))

    codigo = setup_models.main([])

    assert rodaram == ["pyannote", "BERTimbau", "faster-whisper"]
    assert codigo == 1
    assert "No space left on device" in capsys.readouterr().err


def test_sem_configuracao_o_script_para_antes_de_tentar(setup_models, ambiente, passos,
                                                        monkeypatch):
    """`SystemExit` continua abortando: sem token não há passo que faça sentido tentar."""
    monkeypatch.delenv("HUGGINGFACE_TOKEN")
    rodaram = passos()

    with pytest.raises(SystemExit):
        setup_models.main([])

    assert rodaram == [], "tentou baixar sem token"
