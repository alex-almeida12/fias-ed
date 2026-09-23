from pathlib import Path

import pytest

from app.ml import clf_bertimbau
from app.ml.clf_bertimbau import _parametros_tokenizacao, _tokenizar, categoria_de, montar_pares


def test_categoria_usa_o_offset_do_fias_rules():
    # logit_index_offset = 1 → índice 0 é a categoria 1
    logits = [9.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert categoria_de(logits, offset=1) == 1
    logits = [0.0] * 10
    logits[6] = 9.0
    assert categoria_de(logits, offset=1) == 7


def test_nenhum_codigo_le_id2label_do_checkpoint():
    """ANALISE_MODELOS_EXISTENTES §2.2: o config.json grava só LABEL_0..LABEL_9.
    Um mapa trocado não falha visivelmente — produz uma aula inteira
    classificada errado com aparência normal."""
    fonte = Path("app/ml/clf_bertimbau.py").read_text(encoding="utf-8")
    assert "id2label" not in fonte
    assert "label2id" not in fonte


def test_pares_usam_o_turno_anterior_como_contexto():
    # ANALISE_MODELOS_EXISTENTES §2.4: entrada = par (text_a, text_b)
    assert montar_pares(["um", "dois", "três"]) == [("", "um"), ("um", "dois"), ("dois", "três")]


def test_pares_de_lista_vazia():
    assert montar_pares([]) == []


def test_offset_invalido_recusa():
    with pytest.raises(ValueError):
        categoria_de([0.0] * 10, offset=0)


class _TokenizerFalso:
    """Simula um tokenizer HF real: marca o segmento B com 1, como o BERT faz
    por padrão — é exatamente o comportamento que precisa ser corrigido."""

    def __call__(self, a, b, **kwargs):
        n = len(a)
        return {
            "input_ids": [[101, 1, 2, 102, 3, 102] for _ in range(n)],
            "attention_mask": [[1, 1, 1, 1, 1, 1] for _ in range(n)],
            "token_type_ids": [[0, 0, 0, 0, 1, 1] for _ in range(n)],
        }


def test_tokenizacao_zera_token_type_ids():
    """fias_rules.classifier.token_type_ids = "zeros" (ANALISE_MODELOS_EXISTENTES
    §2.5): o treino nunca passou segmentos reais — todos os valores usados no
    treino são zero. Usar os segmentos que o tokenizer gera por padrão aqui
    reproduziria pior o que o modelo aprendeu (accuracy 0,7773 vs 0,7915 na
    reanálise), com o mesmo padrão de degradação silenciosa do mapa de
    categorias: nada quebra, o resultado só fica pior."""
    entradas = _tokenizar(_TokenizerFalso(), [("contexto", "alvo")], max_length=256, padding="max_length")
    assert entradas["token_type_ids"] == [[0, 0, 0, 0, 0, 0]]


def test_tokenizacao_preserva_input_ids_e_attention_mask():
    entradas = _tokenizar(_TokenizerFalso(), [("contexto", "alvo")], max_length=256, padding="max_length")
    assert entradas["input_ids"] == [[101, 1, 2, 102, 3, 102]]
    assert entradas["attention_mask"] == [[1, 1, 1, 1, 1, 1]]


def test_tokenizacao_passa_texto_a_e_texto_b_como_pares_separados():
    """O turno anterior (text_a) e o atual (text_b) vão para argumentos
    posicionais distintos, não concatenados — é o que produz [CLS] a [SEP] b
    [SEP] em vez de perder a fronteira entre os dois turnos."""
    capturado = {}

    class _TokenizerCaptura:
        def __call__(self, a, b, **kwargs):
            capturado["a"] = a
            capturado["b"] = b
            capturado["kwargs"] = kwargs
            return {"input_ids": [[0]] * len(a), "attention_mask": [[1]] * len(a)}

    _tokenizar(_TokenizerCaptura(), [("dois", "três"), ("", "um")], max_length=256, padding="max_length")
    assert capturado["a"] == ["dois", ""]
    assert capturado["b"] == ["três", "um"]


def test_tokenizacao_repassa_max_length_e_padding_ao_tokenizer():
    """max_length e padding não podem ser literais soltos no código: se
    fias_rules.classifier mudar esses valores (§2.6: padding não é neutro sob
    quantização, diferença de até 0,156 nos logits) e o classificador não
    acompanhar, a divergência não levanta exceção nem quebra teste."""
    capturado = {}

    class _TokenizerCaptura:
        def __call__(self, a, b, **kwargs):
            capturado.update(kwargs)
            return {"input_ids": [[0]] * len(a), "attention_mask": [[1]] * len(a)}

    _tokenizar(_TokenizerCaptura(), [("a", "b")], max_length=128, padding="longest")
    assert capturado["max_length"] == 128
    assert capturado["padding"] == "longest"


def test_parametros_tokenizacao_le_max_length_e_padding_das_regras_reais():
    """Lê fias_rules.json de verdade (sem mock): garante que o valor batido
    contra o registro é o mesmo que o treino usou (ANALISE_MODELOS_EXISTENTES
    §2.3, §2.6), não um literal reescrito à mão neste arquivo."""
    params = _parametros_tokenizacao()
    assert params == {"max_length": 256, "padding": "max_length"}


def test_parametros_tokenizacao_muda_com_as_regras(monkeypatch):
    """Prova que a leitura não é decorativa: mudar o valor em fias_rules muda
    o que o classificador usa, sem precisar tocar em clf_bertimbau.py."""
    def regras_falsas(nome):
        assert nome == "fias_rules"
        return {"classifier": {
            "max_length": 128,
            "padding": "longest",
            "input_format": "pair:previous_turn,current_turn",
        }}

    monkeypatch.setattr(clf_bertimbau, "load_rules", regras_falsas)
    assert _parametros_tokenizacao() == {"max_length": 128, "padding": "longest"}


def test_parametros_tokenizacao_recusa_formato_de_entrada_inesperado(monkeypatch):
    """ANALISE_MODELOS_EXISTENTES §2.4: o modelo foi treinado com par de
    turnos. Se fias_rules um dia declarar outro input_format, montar_pares()
    não vai passar a implementá-lo sozinho — é melhor recusar alto e claro do
    que classificar a aula inteira com um formato de entrada errado."""
    def regras_falsas(nome):
        return {"classifier": {
            "max_length": 256,
            "padding": "max_length",
            "input_format": "single_turn",
        }}

    monkeypatch.setattr(clf_bertimbau, "load_rules", regras_falsas)
    with pytest.raises(ValueError):
        _parametros_tokenizacao()
