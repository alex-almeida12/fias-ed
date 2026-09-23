"""Lê o registro de modelos do fias-ed-shared e confere integridade (§66, §67).

A lista de hashes é do shared, não daqui: manter uma cópia local criaria duas
fontes de verdade que divergem em silêncio.

Estar no registro deixou de ser o mesmo que poder rodar. O registro também
guarda modelo que existe só pela **procedência de uma medição publicada** — os
pesos `tiny` e `base` do §21 do README, cujo pino de versão é a única coisa que
torna aquelas linhas de tabela recuperáveis. Eles precisam de entrada (senão a
revisão fixada não mora em lugar nenhum), e não podem ser carregados: ninguém
validou o tamanho. Quem carrega peso em produção chama `entrada_adotavel`, que
lê `validation_status` e recusa o que não foi adotado; quem só lê procedência
para bookkeeping continua em `entrada`.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


class ModeloInvalido(Exception):
    def __init__(self, code: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.code = code


def _caminho_registro() -> Path:
    return get_settings().shared_dir / get_settings().models_registry_rel


@lru_cache(maxsize=None)
def _ler(caminho: Path) -> dict:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModeloInvalido("MODELO_REGISTRO_ILEGIVEL", f"registro ilegível: {caminho}") from exc


def carregar_registro() -> dict:
    caminho = _caminho_registro()
    return _ler(caminho)


def entrada(model_id: str) -> dict:
    for m in carregar_registro().get("models", []):
        if m.get("model_id") == model_id:
            return m
    raise ModeloInvalido("MODELO_NAO_REGISTRADO", f"modelo fora do registro: {model_id}")


#: Os estados de validação que autorizam um modelo a rodar em produção.
#: Lista de permitidos, e não de recusados, de propósito: o vocabulário de
#: `validation_status` é do shared (engine-py/src/fias_ed_engine/traceability.py)
#: e pode ganhar estados novos sem que este repositório saiba. Um estado que
#: ninguém aqui examinou entra recusado, não adotado por omissão.
STATUS_ADOTAVEIS = ("validated", "engineering_decision")


def entrada_adotavel(model_id: str) -> dict:
    """A entrada do registro, exigindo que o modelo seja adotável em produção.

    É o que separa "declarado" de "aprovado". `faster-whisper-tiny` e
    `faster-whisper-base` estão no registro porque a medição do §21 foi feita
    com eles e o pino de versão é fato científico que não pode se perder — não
    porque alguém decidiu usá-los. Sem esta checagem, acrescentar a procedência
    de uma medição passaria a autorizar o uso do peso medido, que é exatamente
    o contrário do que a entrada quer dizer.
    """
    m = entrada(model_id)
    status = m.get("validation_status")
    if status not in STATUS_ADOTAVEIS:
        raise ModeloInvalido(
            "MODELO_NAO_ADOTAVEL",
            f"modelo não adotável em produção: {model_id} (validation_status={status!r})."
            " A entrada dele no registro científico existe para a procedência de uma medição"
            " publicada — dizer qual peso produziu aqueles números —, não para autorizar o uso."
            " Adotá-lo exige validação científica registrada"
            f" (validation_status em {', '.join(STATUS_ADOTAVEIS)}).")
    return m


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def verificar_artefatos(model_id: str, base: Path) -> None:
    m = entrada(model_id)
    for proibido in m.get("forbidden_files", []):
        if any(base.rglob(proibido)):
            raise ModeloInvalido("MODELO_ARQUIVO_PROIBIDO", f"arquivo proibido presente: {proibido}")
    for art in m.get("artifacts", []):
        caminho = base / art["relative_path"]
        if not caminho.is_file():
            raise ModeloInvalido("MODELO_ARTEFATO_AUSENTE", f"artefato ausente: {art['relative_path']}")
        if _sha256(caminho) != art["sha256"]:
            raise ModeloInvalido("MODELO_SHA256_DIVERGENTE", f"sha256 divergente: {art['relative_path']}")
