"""BERTimbau atrás do protocolo Classificador.

O mapa índice→categoria NÃO sai do checkpoint: o config.json grava só
LABEL_0..LABEL_9 (ANALISE_MODELOS_EXISTENTES §2.2). A categoria vem do
logit_index_offset declarado em fias_rules.json — nunca de um mapa lido
do checkpoint.

O formato de entrada (par de turnos, sem lowercasing, sem prefixo de
falante, token_type_ids sempre zero) também vem da pesquisa, não é
escolha de implementação: ANALISE_MODELOS_EXISTENTES §2.3-§2.5. Mudar
esse formato em relação ao treino degrada a qualidade em silêncio, do
mesmo jeito que um mapa de categorias trocado.

max_length e padding são lidos de fias_rules.classifier, nunca literais
soltos aqui: o §2.6 mede que padding não é neutro sob quantização
(diferença de até 0,156 nos logits) — uma segunda fonte de verdade que
divergisse da usada no treino teria o mesmo efeito silencioso.
"""
from pathlib import Path

from fias_ed_engine.rules import load_rules

from app.core.config import get_settings
from app.ml.registry import entrada, verificar_artefatos

FORMATO_ENTRADA_ESPERADO = "pair:previous_turn,current_turn"


def categoria_de(logits: list[float], offset: int) -> int:
    if offset < 1:
        raise ValueError("logit_index_offset precisa ser >= 1")
    return max(range(len(logits)), key=logits.__getitem__) + offset


def montar_pares(textos: list[str]) -> list[tuple[str, str]]:
    """Par de turnos: o anterior como contexto, o atual como alvo."""
    return [("" if i == 0 else textos[i - 1], t) for i, t in enumerate(textos)]


def _parametros_tokenizacao() -> dict:
    """Lê max_length, padding e input_format de fias_rules.classifier — nunca
    literais aqui. Recusa alto e claro se input_format deixar de ser o par de
    turnos que montar_pares() implementa (ANALISE_MODELOS_EXISTENTES §2.4):
    classificar a aula inteira num formato de entrada que o código não
    implementa de fato é pior do que uma exceção na hora.
    """
    classificador = load_rules("fias_rules")["classifier"]
    if classificador["input_format"] != FORMATO_ENTRADA_ESPERADO:
        raise ValueError(f"formato de entrada não suportado: {classificador['input_format']!r}")
    return {"max_length": classificador["max_length"], "padding": classificador["padding"]}


def _tokenizar(tok, pares: list[tuple[str, str]], max_length: int, padding: str) -> dict:
    """Constrói as entradas do modelo a partir do par (turno anterior, turno
    atual), em Python puro (sem tensores) para ser testável sem torch.

    Zera token_type_ids: o treino nunca passou segmentos reais — todos os
    valores usados no treino são zero (ANALISE_MODELOS_EXISTENTES §2.5).
    Usar os segmentos que o tokenizer gera por padrão (0 no turno anterior,
    1 no atual) reproduz pior o que o modelo aprendeu: accuracy 0,7773
    (segmentos do tokenizer) contra 0,7915 (zeros) na reanálise registrada
    em fias_rules.classifier.token_type_ids.
    """
    a = [p[0] for p in pares]
    b = [p[1] for p in pares]
    entradas = tok(a, b, padding=padding, truncation="longest_first", max_length=max_length)
    if "token_type_ids" in entradas:
        entradas["token_type_ids"] = [[0] * len(seq) for seq in entradas["token_type_ids"]]
    return entradas


class BertimbauClassificador:
    def __init__(self) -> None:
        s = get_settings()
        base = Path(s.models_dir)
        verificar_artefatos(s.clf_model_id, base)
        art = {a["role"]: a["relative_path"] for a in entrada(s.clf_model_id)["artifacts"]}
        diretorio = (base / art["weights"]).parent
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self._tok = AutoTokenizer.from_pretrained(diretorio, local_files_only=True)
        self._modelo = AutoModelForSequenceClassification.from_pretrained(diretorio, local_files_only=True)
        self._modelo.eval()

    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        if not pares:
            return []
        import torch
        params = _parametros_tokenizacao()
        entradas = _tokenizar(self._tok, pares, max_length=params["max_length"], padding=params["padding"])
        tensores = {k: torch.tensor(v) for k, v in entradas.items()}
        with torch.no_grad():
            saida = self._modelo(**tensores).logits
        return saida.tolist()
