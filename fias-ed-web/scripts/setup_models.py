"""Popula o diretório de modelos e confere a integridade.

Roda uma vez, na instalação. Precisa de rede e do token do Hugging Face; o
produto em execução nunca faz isso — os serviços sobem com HF_HUB_OFFLINE=1 e
TRANSFORMERS_OFFLINE=1, e as três classes de modelo carregam com
`local_files_only`.

Cada repositório é baixado numa **revisão fixada** (o commit abaixo), não em
`main`. É o que torna a instalação reprodutível: sem isso, duas máquinas
instaladas em semanas diferentes rodariam pesos diferentes sem ninguém notar,
e o §44 ("a mesma aula reprocessada dá o mesmo texto") deixaria de valer entre
elas. O `huggingface_hub` confere o hash de cada arquivo contra o que o
repositório declara naquela revisão.

O BERTimbau não vem da rede: é copiado dos experimentos e conferido contra
`scientific-config/models.json`, que é onde os sha256 dele vivem.

Nada aqui imprime o token. Ele entra por variável de ambiente e viaja no
cabeçalho Authorization; as mensagens de erro do huggingface_hub carregam a
URL, que vai sem credencial.

Os repositórios do pyannote são *gated*: é preciso aceitar as condições de uso
na página de cada um, logado na conta dona do token, senão o download volta
403. O script diz isso em vez de estourar uma pilha.
"""
import os
import shutil
import sys
from pathlib import Path

# repo_id -> revisão fixada
REVISOES = {
    "Systran/faster-whisper-small": "536b0662742c02347bc0e980a01041f333bce120",
    "pyannote/speaker-diarization-3.1": "84fd25912480287da0247647c3d2b4853cb3ee5d",
    "pyannote/segmentation-3.0": "e66f3d3b9eb0873085418a7b813d3b369bf160bb",
    "pyannote/wespeaker-voxceleb-resnet34-LM": "837717ddb9ff5507820346191109dc79c958d614",
}

REPO_ASR = "Systran/faster-whisper-{tamanho}"
ARQUIVOS_ASR = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")

REPO_DIAR = "pyannote/speaker-diarization-3.1"
REPO_SEGMENTACAO = "pyannote/segmentation-3.0"
REPO_EMBEDDING = "pyannote/wespeaker-voxceleb-resnet34-LM"

MODEL_ID_ASR = "faster-whisper-{tamanho}"
MODEL_ID_DIAR = "pyannote-speaker-diarization-3.1"
MODEL_ID_CLF = "fias-bertimbau-ptbr-frente3"


def _baixar(repo_id: str, arquivo: str, destino: Path, token: str, cache: Path) -> Path:
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import GatedRepoError

    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        baixado = hf_hub_download(repo_id, arquivo, revision=REVISOES[repo_id],
                                  token=token, cache_dir=str(cache))
    except GatedRepoError:
        raise SystemExit(
            f"acesso negado a {repo_id}: é um repositório com condições de uso.\n"
            f"Abra https://huggingface.co/{repo_id} logado na conta dona do token,\n"
            "aceite as condições e rode este script de novo.") from None
    shutil.copyfile(baixado, destino)
    return destino


def baixar_whisper(base: Path, tamanho: str, token: str) -> Path:
    """Diretório simples, não o layout de cache do Hugging Face: o caminho dentro
    do cache carrega o commit do repositório e mudaria a cada revisão nova."""
    destino = base / f"faster-whisper-{tamanho}"
    for arquivo in ARQUIVOS_ASR:
        _baixar(REPO_ASR.format(tamanho=tamanho), arquivo, destino / arquivo, token, base / ".hf")
    return destino


def baixar_pyannote(base: Path, token: str) -> Path:
    """Baixa os três repositórios e reescreve o config.yaml para caminhos locais.

    O config.yaml publicado aponta `segmentation` e `embedding` para ids do Hub.
    Carregado como vem, o pipeline sai para a rede atrás dos outros dois
    repositórios — e em execução não há rede.
    """
    import yaml

    destino = base / "pyannote"
    segmentacao = _baixar(REPO_SEGMENTACAO, "pytorch_model.bin",
                          destino / "segmentation-3.0" / "pytorch_model.bin", token, base / ".hf")
    embedding = _baixar(REPO_EMBEDDING, "pytorch_model.bin",
                        destino / "wespeaker-voxceleb-resnet34-LM" / "pytorch_model.bin",
                        token, base / ".hf")
    bruto = _baixar(REPO_DIAR, "config.yaml", destino / "config.upstream.yaml", token, base / ".hf")

    config = yaml.safe_load(bruto.read_text(encoding="utf-8"))
    params = config["pipeline"]["params"]
    params["segmentation"] = str(segmentacao)
    params["embedding"] = str(embedding)
    (destino / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return destino


def copiar_bertimbau(base: Path, experimentos: Path) -> None:
    """Copia só os artefatos registrados — nada de `training_args.bin` e companhia,
    que o registro lista em forbidden_files justamente por serem pickle.

    O diretório de origem é somente leitura para este script: ele lê e nunca
    escreve lá.
    """
    from app.ml.registry import entrada

    for art in entrada(MODEL_ID_CLF)["artifacts"]:
        origem = experimentos / art["relative_path"]
        if not origem.is_file():
            raise SystemExit(
                f"artefato do BERTimbau ausente em {experimentos}: {art['relative_path']}."
                " Confira FIAS_ED_EXPERIMENTS_DIR no .env.")
        alvo = base / art["relative_path"]
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, alvo)


def conferir(base: Path, model_ids: tuple[str, ...]) -> None:
    """BERTimbau: sha256 artefato por artefato, contra o registro.

    Whisper e pyannote: o registro do shared é enraizado no diretório de
    experimentos e recusa artefato `.bin`, então os pesos baixados do Hugging
    Face não têm sha256 lá (fias-ed-shared/engine-py/tests/test_models_registry.py).
    A conferência deles é a da revisão fixada, feita pelo huggingface_hub no
    download; aqui só se exige que o modelo esteja declarado no registro e que
    o arquivo tenha ficado no lugar.
    """
    from app.ml.registry import entrada, verificar_artefatos

    verificar_artefatos(MODEL_ID_CLF, base)
    for model_id in model_ids:
        entrada(model_id)


def _exigir(caminhos: tuple[Path, ...]) -> None:
    faltando = [str(c) for c in caminhos if not c.is_file()]
    if faltando:
        raise SystemExit("arquivos que o setup deveria ter deixado e não deixou: " + ", ".join(faltando))


def _exigir_ambiente(nome: str, dica: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise SystemExit(f"{nome} não está definido. {dica}")
    return valor


def main() -> int:
    base = Path(_exigir_ambiente("FIAS_ED_MODELS_DIR", "É o diretório onde os pesos ficam."))
    tamanho = os.environ.get("FIAS_ED_ASR_SIZE", "small")
    token = _exigir_ambiente(
        "HUGGINGFACE_TOKEN",
        "Crie um token de leitura em https://huggingface.co/settings/tokens e ponha no .env.")
    experimentos = Path(_exigir_ambiente(
        "FIAS_ED_EXPERIMENTS_DIR",
        "É o diretório 'artigos selecionados/experimentos'; ponha o caminho no .env."))
    if REPO_ASR.format(tamanho=tamanho) not in REVISOES:
        raise SystemExit(
            f"FIAS_ED_ASR_SIZE={tamanho} não tem revisão fixada neste script. Acrescente o"
            f" commit de https://huggingface.co/{REPO_ASR.format(tamanho=tamanho)} em REVISOES"
            " e a entrada correspondente em scientific-config/models.json.")
    base.mkdir(parents=True, exist_ok=True)

    print("baixando o pyannote…", flush=True)
    pyannote = baixar_pyannote(base, token)
    print("copiando o BERTimbau dos experimentos…", flush=True)
    copiar_bertimbau(base, experimentos)
    print(f"baixando o faster-whisper ({tamanho})…", flush=True)
    whisper = baixar_whisper(base, tamanho, token)

    _exigir((pyannote / "config.yaml",
             pyannote / "segmentation-3.0" / "pytorch_model.bin",
             pyannote / "wespeaker-voxceleb-resnet34-LM" / "pytorch_model.bin",
             *(whisper / a for a in ARQUIVOS_ASR)))
    conferir(base, (MODEL_ID_DIAR, MODEL_ID_ASR.format(tamanho=tamanho)))
    # O cache do download não fica: só ocupa espaço (uma segunda cópia de tudo)
    # e confunde a conferência de arquivos proibidos.
    shutil.rmtree(base / ".hf", ignore_errors=True)
    print("MODELOS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
