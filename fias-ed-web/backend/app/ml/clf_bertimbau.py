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
from app.ml.registry import entrada_adotavel, verificar_artefatos

FORMATO_ENTRADA_ESPERADO = "pair:previous_turn,current_turn"

# Quantos pares vão ao modelo por passagem. Decisão de engenharia local, não
# científica: fias_rules.classifier declara o que muda resultado (input_format,
# max_length, padding, token_type_ids, logit_index_offset, uncertain_below) e
# não declara lote — porque lote não muda a entrada do modelo nem a categoria de
# nenhuma fala (veja logits()). Uma entrada nova no shared para isto seria uma
# segunda fonte de verdade para algo que a pesquisa não fixou.
#
# O número sai de medição, não de gosto. Sem lote, a aula inteira ia numa
# passagem só: numa aula de 46 min (381 segmentos) o processo do worker saltava
# de 2,73 GB para 4,75 GB durante os ~46 s da classificação, e o acréscimo cresce
# linearmente com a quantidade de segmentos — com a duração da aula e com o
# quanto a fala é picada. `scripts/medir_classificacao.py` mede, no BERTimbau
# real: 381 segmentos numa passagem só custam 4,23 GB de pico e 762 custam
# 7,65 GB (o dobro de aula, o dobro de memória, sem teto nenhum à vista); com
# lote de 16, os dois custam 1,07 GB — dos quais 0,46 GB são o modelo carregado.
# O pico deixou de ser função do tamanho da aula, que era o ponto. O tempo não
# piora: 47,8 s contra 52,9 s em 381 segmentos, e 106,9 s contra 106,9 s em 762.
# Lotes muito menores só trocariam 0,6 GB por mais tempo de relógio.
TAMANHO_DO_LOTE = 16


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
        art = {a["role"]: a["relative_path"] for a in entrada_adotavel(s.clf_model_id)["artifacts"]}
        diretorio = (base / art["weights"]).parent
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self._tok = AutoTokenizer.from_pretrained(diretorio, local_files_only=True)
        self._modelo = AutoModelForSequenceClassification.from_pretrained(diretorio, local_files_only=True)
        self._modelo.eval()

    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        """Logits de todos os pares, em lotes de TAMANHO_DO_LOTE.

        **A entrada do modelo é idêntica à da passagem única, linha por linha.**
        Com padding="max_length" (fias_rules.classifier) cada par é preenchido
        até os 256 tokens sozinho, sem olhar para os vizinhos, então o lote não
        altera um único id, uma única máscara. Quem sustenta essa premissa é
        `test_parametros_tokenizacao_le_max_length_e_padding_das_regras_reais`:
        se o shared um dia declarar padding="longest", o comprimento passa a
        depender de quem está no mesmo lote e esta frase deixa de valer.

        **A saída não é bit a bit a mesma, e não tinha como ser.** O produto de
        matrizes em float32 escolhe blocagem e ordem de redução conforme a
        dimensão do lote, então o mesmo par em lote de 16 e em lote de 381 dá
        números que diferem na última casa da representação: medido no BERTimbau
        real, com 381 segmentos, **1,9e-6 no pior caso**, contra uma margem
        mínima de 0,231 entre o maior e o segundo maior logit no mesmo material
        — 121 mil vezes de folga, e nenhuma das 381 categorias muda
        (`scripts/medir_classificacao.py`, e
        `test_bertimbau_em_lote_nao_muda_nenhuma_categoria`). Nenhum tamanho de
        lote reproduziria os valores de outro tamanho; a pergunta certa não é
        essa.

        A pergunta certa é a do §44, e a resposta é sim: o tamanho do lote é
        fixo, então a mesma aula reprocessada passa exatamente pelas mesmas
        contas e devolve exatamente os mesmos números — verificado, os dois
        lados bit a bit iguais.
        """
        if not pares:
            return []
        import torch
        params = _parametros_tokenizacao()
        saida: list[list[float]] = []
        for inicio in range(0, len(pares), TAMANHO_DO_LOTE):
            lote = pares[inicio:inicio + TAMANHO_DO_LOTE]
            entradas = _tokenizar(self._tok, lote, max_length=params["max_length"],
                                  padding=params["padding"])
            tensores = {k: torch.tensor(v) for k, v in entradas.items()}
            with torch.no_grad():
                saida.extend(self._modelo(**tensores).logits.tolist())
        return saida
