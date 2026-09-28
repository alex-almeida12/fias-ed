"""scripts/setup_models.py: uma falha não pode esconder o estado dos outros modelos.

O script rodou meses na ordem pyannote → BERTimbau → Whisper abortando no
primeiro erro. Enquanto os repositórios *gated* do pyannote devolveram 403, o
BERTimbau — que só copia do disco, sem rede e sem licença — nunca chegou a ser
copiado, e ninguém soube se ele estava bem. Estes testes fixam o conserto: cada
modelo tenta por si, os erros são coletados, e `MODELOS OK` continua exigindo os
três.

A segunda metade trava a **fonte única do pino de versão**. A revisão fixada de
cada repositório do Hugging Face viveu em dois lugares: um dicionário no script
(quem de fato passava `revision=`) e o bloco `integrity` de
`scientific-config/models.json` (que ninguém lia). Duas fontes que não se
cruzam divergem em silêncio, e o registro passa a afirmar uma procedência que
não é a baixada. Agora o pino mora só no registro; estes testes provam que o
script lê de lá — mudando o pino no registro, muda o que ele baixa — e que não
sobrou cópia velha em lugar nenhum.

A terceira metade veio do estrago que a segunda fez sem querer. Tirar o
dicionário do script apagou do repositório inteiro os pinos de `tiny` e `base`,
que só existiam lá — e são os pesos das seis linhas de `tiny`/`base` da tabela
de medição do §21 do README. A medição deixou de ser reproduzível em silêncio,
porque nenhum teste exigia que um repositório baixável tivesse pino. Agora os
dois têm entrada no registro, pela procedência e não pela adoção, e os testes
abaixo travam as duas pontas: o que o script sabe baixar tem pino, e um tamanho
que está lá só pela procedência não vira o modelo do produto.

Nada aqui toca a rede nem o disco de verdade: os três passos são substituídos,
e onde o download é o próprio objeto do teste, quem sai é o `hf_hub_download`.
"""
import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

# O script não é módulo do pacote `app`: mora em scripts/, que o
# docker-compose.test.yml monta em /app/scripts, ao lado de tests/.
CAMINHO = Path(__file__).resolve().parents[1] / "scripts" / "setup_models.py"
# Quem sabe quais tamanhos de Whisper este projeto baixa é o script de medição:
# são os tamanhos que a tabela do §21 compara, e é por eles que
# `setup_models.py --somente-asr` é chamado.
CAMINHO_MEDIR = CAMINHO.parent / "medir_asr.py"


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


# Um valor que não é o pino de nenhum repositório de verdade: se ele chega ao
# `revision=`, é porque veio do registro que o teste instalou, e não de uma cópia.
REVISAO_FICTICIA = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def registro_real():
    """O registro científico que o serviço usa, lido pelo mesmo caminho do app."""
    from app.core.config import get_settings

    s = get_settings()
    return json.loads((s.shared_dir / s.models_registry_rel).read_text(encoding="utf-8"))


@pytest.fixture
def registro(tmp_path, monkeypatch):
    """Instala um registro próprio e faz o script ler dele.

    Escreve num SHARED_DIR de mentira: `fias-ed-shared` é a fonte de verdade
    científica e nenhum teste reescreve o arquivo de verdade.
    """
    from app.core.config import get_settings
    from app.ml import registry

    def instalar(dados: dict) -> None:
        destino = tmp_path / "shared" / "scientific-config"
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "models.json").write_text(json.dumps(dados), encoding="utf-8")
        monkeypatch.setenv("SHARED_DIR", str(tmp_path / "shared"))
        get_settings.cache_clear()

    yield instalar
    get_settings.cache_clear()
    registry._ler.cache_clear()


@pytest.fixture
def downloads(monkeypatch):
    """Substitui o `hf_hub_download` e guarda o (repo_id, revision) de cada chamada.

    É o ponto exato onde o pino deixa de ser assunto interno do script: o que
    for capturado aqui é o que iria ao Hugging Face.
    """
    import huggingface_hub

    # O config.yaml do pyannote é relido e reescrito por `baixar_pyannote`; os
    # outros arquivos só precisam existir.
    conteudo = {"config.yaml": "pipeline:\n  params:\n    segmentation: hub\n    embedding: hub\n"}
    chamadas: list[tuple[str, str]] = []

    def falso(repo_id, arquivo, *, revision, token, cache_dir):
        chamadas.append((repo_id, revision))
        caminho = Path(cache_dir) / repo_id.replace("/", "--") / revision / arquivo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo.get(arquivo, arquivo), encoding="utf-8")
        return str(caminho)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", falso)
    return chamadas


def _baixar_tudo(setup_models, base: Path) -> None:
    """Os mesmos downloads que os passos do script disparam, pelas mesmas funções."""
    setup_models._sem_banco()
    setup_models.baixar_whisper(base, "small", "token-de-mentira")
    setup_models.baixar_pyannote(base, "token-de-mentira")


def test_a_revisao_baixada_e_a_que_o_registro_declara(setup_models, downloads, registro_real,
                                                      tmp_path):
    """Trava a concordância entre as duas fontes, contra o registro de verdade.

    Não compara o registro consigo mesmo: o lado esquerdo é o `revision=` que o
    script entregaria ao Hugging Face.
    """
    declarado = {r["repo_id"]: r["revision"]
                 for m in registro_real["models"]
                 for r in m.get("integrity", {}).get("repos", [])}

    _baixar_tudo(setup_models, tmp_path / "models")

    assert downloads, "nenhum download foi tentado: o teste não exercitou o script"
    for repo_id, revision in downloads:
        assert repo_id in declarado, f"{repo_id} é baixado sem entrada no registro científico"
        assert revision == declarado[repo_id], (
            f"{repo_id}: o script baixa {revision} e o registro declara {declarado[repo_id]}")


def test_mudar_o_pino_no_registro_muda_o_que_o_script_baixa(setup_models, downloads,
                                                            registro_real, registro, tmp_path):
    """A prova de que a fonte é uma só: com o registro trocado, o script segue o registro."""
    for modelo in registro_real["models"]:
        for repo in modelo.get("integrity", {}).get("repos", []):
            repo["revision"] = REVISAO_FICTICIA
    registro(registro_real)

    _baixar_tudo(setup_models, tmp_path / "models")

    assert downloads, "nenhum download foi tentado"
    assert {revisao for _, revisao in downloads} == {REVISAO_FICTICIA}, \
        "o script ignorou o pino do registro: ainda existe uma cópia da revisão nele"


def test_sem_pino_no_registro_o_script_recusa_baixar(setup_models, downloads, registro_real,
                                                     registro, tmp_path):
    """Pino ausente é erro de configuração científica: nada de valor padrão."""
    for modelo in registro_real["models"]:
        modelo.pop("integrity", None)
    registro(registro_real)

    with pytest.raises(setup_models.FalhaDeModelo) as erro:
        setup_models._sem_banco()
        setup_models.baixar_whisper(tmp_path / "models", "small", "token-de-mentira")

    assert "Systran/faster-whisper-small" in str(erro.value), "não disse qual repositório"
    assert "models.json" in str(erro.value), "não disse onde o pino tem de ser declarado"
    assert downloads == [], "baixou assim mesmo, sem pino declarado"


def test_tamanho_de_asr_sem_pino_para_antes_de_tentar(setup_models, ambiente, passos, monkeypatch):
    """Um tamanho que o registro não declara não baixa, e o script diz onde declarar.

    `medium` não está no registro — nem como modelo do produto, nem como
    procedência de medição nenhuma. Sem pino não há instalação reprodutível, e
    baixar `main` produziria pesos que ninguém consegue recuperar depois.
    """
    monkeypatch.setenv("FIAS_ED_ASR_SIZE", "medium")
    rodaram = passos()

    with pytest.raises(SystemExit) as erro:
        setup_models.main([])

    assert "medium" in str(erro.value) and "models.json" in str(erro.value), \
        "não explicou que o que falta é o pino no registro"
    assert rodaram == [], "tentou baixar um tamanho sem revisão declarada"


def test_tamanho_so_de_procedencia_nao_vira_o_modelo_do_produto(setup_models, ambiente, passos,
                                                                monkeypatch):
    """`tiny` tem pino, e ainda assim o setup completo recusa instalá-lo.

    É a diferença entre baixável e adotável. A entrada de `tiny` no registro
    existe para dizer qual peso produziu a medição do §21; `app/ml/asr_whisper.py`
    recusaria carregá-lo na primeira transcrição, então o script para antes de
    tocar a rede, com o motivo e a saída (`--somente-asr`).
    """
    monkeypatch.setenv("FIAS_ED_ASR_SIZE", "tiny")
    rodaram = passos()

    with pytest.raises(SystemExit) as erro:
        setup_models.main([])

    mensagem = str(erro.value)
    assert "tiny" in mensagem, "não disse qual tamanho foi recusado"
    assert "procedência" in mensagem, \
        "recusou sem dizer que a entrada existe para a procedência de uma medição"
    assert "asr_whisper" in mensagem, "não disse quem recusaria o modelo depois"
    assert "--somente-asr" in mensagem, "recusou sem dizer por onde repetir a medição"
    assert rodaram == [], "começou a instalar um tamanho que o produto não pode carregar"


def test_somente_asr_baixa_o_tamanho_de_procedencia_avisando(setup_models, ambiente, downloads,
                                                             registro_real, monkeypatch, capsys):
    """Medir é justamente o que se faz com um peso que ninguém adotou.

    `--somente-asr` continua baixando `tiny` — foi assim que a tabela do §21
    nasceu, e sem isso ela não é repetível —, mas quem baixa ouve o que está
    levando. O pino que vai ao Hugging Face é o do registro.
    """
    monkeypatch.setenv("FIAS_ED_ASR_SIZE", "tiny")
    declarado = {r["repo_id"]: r["revision"]
                 for m in registro_real["models"]
                 for r in m.get("integrity", {}).get("repos", [])}

    codigo = setup_models.main(["--somente-asr"])

    saida = capsys.readouterr().out
    assert codigo == 0, "recusou baixar um tamanho que o registro declara"
    assert downloads == [("Systran/faster-whisper-tiny",
                          declarado["Systran/faster-whisper-tiny"])] * len(setup_models.ARQUIVOS_ASR)
    assert "aviso" in saida and "procedência" in saida, \
        "baixou sem avisar que o tamanho não é adotável em produção"


def _tamanhos_da_medicao() -> list[str]:
    """Os tamanhos de Whisper que `scripts/medir_asr.py` mede, lidos do fonte dele.

    Lido, e não copiado: uma lista própria aqui seria a mesma duplicação que
    começou esta história. É o default de `--tamanhos`, que é o que roda quando
    a medição do §21 é repetida.
    """
    arvore = ast.parse(CAMINHO_MEDIR.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and getattr(no.func, "attr", "") == "add_argument"
                and no.args and getattr(no.args[0], "value", None) == "--tamanhos"):
            for kw in no.keywords:
                if kw.arg == "default":
                    return [ast.literal_eval(e) for e in kw.value.elts]
    raise AssertionError("scripts/medir_asr.py não declara mais o default de --tamanhos:"
                         " este teste perdeu a lista do que o script sabe baixar")


def test_todo_repositorio_que_o_script_sabe_baixar_tem_pino_no_registro(setup_models, ambiente):
    """A ausência que causou o defeito não pode voltar a passar despercebida.

    `tiny` e `base` eram baixáveis e não tinham entrada no registro: quando a
    cópia do pino saiu do script, a procedência das seis linhas de tabela do §21
    sumiu do repositório inteiro. O que o script sabe baixar — os três tamanhos
    da medição e os três repositórios do pyannote — tem de ter pino declarado.
    """
    setup_models._sem_banco()
    repos = [setup_models.REPO_ASR.format(tamanho=t) for t in _tamanhos_da_medicao()]
    repos += [setup_models.REPO_DIAR, setup_models.REPO_SEGMENTACAO, setup_models.REPO_EMBEDDING]

    sem_pino = []
    for repo_id in repos:
        try:
            assert len(setup_models.revisao_fixada(repo_id)) == 40
        except setup_models.FalhaDeModelo:
            sem_pino.append(repo_id)

    assert sem_pino == [], \
        f"o script baixa estes repositórios e o registro não declara a revisão: {sem_pino}"


def test_o_script_nao_guarda_commit_fixado(setup_models):
    """Qualquer sha de commit de volta ao script é a segunda fonte renascendo."""
    fonte = CAMINHO.read_text(encoding="utf-8")

    assert not re.findall(r"\b[0-9a-f]{40}\b", fonte), \
        "voltou a existir revisão fixada no script; o pino tem uma fonte só, o registro"


def test_nenhuma_copia_do_pino_fora_do_registro(registro_real):
    """E o mesmo para o backend: o pino não pode estar colado em canto nenhum."""
    pinos = {r["revision"] for m in registro_real["models"]
             for r in m.get("integrity", {}).get("repos", [])}
    raizes = (CAMINHO.parent, Path(__file__).resolve().parents[1] / "app")

    copias = sorted(f"{arquivo}: {pino}"
                    for raiz in raizes for arquivo in raiz.rglob("*.py")
                    for pino in pinos if pino in arquivo.read_text(encoding="utf-8"))

    assert copias == [], f"revisão do registro copiada no código: {copias}"
