from pathlib import Path
from types import SimpleNamespace

import pytest

from fias_ed_engine.rules import load_rules

from app.ml import clf_bertimbau
from app.ml.clf_bertimbau import (FORMATO_ENTRADA_ESPERADO, Turno, _parametros_tokenizacao,
                                  _tokenizar, categoria_de, montar_pares)


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


def test_contexto_vem_do_turno_anterior_quando_o_falante_muda():
    """A convenção do conjunto de treino: `text_a` é o turno anterior DO OUTRO
    FALANTE. Quando o falante muda, o contexto é preenchido com o texto do
    turno anterior inteiro — é o que dá ao modelo a informação que separa a
    categoria 3 das outras categorias de professor."""
    turnos = [Turno("pergunta do professor", "PROFESSOR"),
              Turno("resposta do aluno", "ALUNO"),
              Turno("o professor repete a resposta", "PROFESSOR")]
    assert montar_pares(turnos) == [
        ("", "pergunta do professor"),
        ("pergunta do professor", "resposta do aluno"),
        ("resposta do aluno", "o professor repete a resposta"),
    ]


def test_mesmo_falante_em_sequencia_nao_recebe_contexto():
    """Professor depois de professor → `text_a` vazio. É o ramo do notebook do
    TalkMoves em que o par sai com `empty_student`, e era exatamente o que a
    produção fazia errado: 213 de 213 segmentos recebiam o segmento anterior
    como contexto porque ninguém olhava quem falava."""
    turnos = [Turno("primeira frase", "PROFESSOR"),
              Turno("segunda frase", "PROFESSOR"),
              Turno("terceira frase", "PROFESSOR")]
    assert montar_pares(turnos) == [("", "primeira frase"), ("", "segunda frase"), ("", "terceira frase")]


def test_o_contexto_da_categoria_3_nao_e_apagado():
    """**Este é o teste que trava o conserto errado.** "Esvaziar `text_a`
    sempre" passaria em `test_mesmo_falante_em_sequencia_nao_recebe_contexto` e
    destruiria a categoria 3 ("aceita ou utiliza ideias dos alunos"), que só
    existe porque o professor está reagindo à fala de um aluno — metade do
    numerador do ID_RATIO, que é como o FIAS mede influência indireta.

    O exemplo é o padrão canônico do conjunto de treino (rótulo 3: `text_a`
    "Sete quatorze", `text_b` "Sete e quatorze."): o contexto tem de ser o
    texto do aluno, palavra por palavra, e não uma string vazia nem uma marca
    de falante."""
    turnos = [Turno("o aluno disse: sete quatorze", "ALUNO"),
              Turno("sete e quatorze", "PROFESSOR")]
    contexto, alvo = montar_pares(turnos)[1]
    assert contexto == "o aluno disse: sete quatorze"
    assert alvo == "sete e quatorze"


def test_alternancia_longa_preenche_e_esvazia_no_lugar_certo():
    """Fecha os dois erros de uma vez numa sequência que mistura os casos:
    contar quantos `text_a` estão vazios não prova nada, então o teste fixa
    QUAL contexto cada turno recebeu."""
    turnos = [Turno("p1", "PROFESSOR"), Turno("p2", "PROFESSOR"), Turno("a1", "ALUNO"),
              Turno("a2", "ALUNO"), Turno("p3", "PROFESSOR"), Turno("a3", "ALUNO")]
    assert montar_pares(turnos) == [
        ("", "p1"),      # primeiro turno da aula: não existe anterior
        ("", "p2"),      # professor depois de professor
        ("p2", "a1"),    # trocou: contexto é a ÚLTIMA fala do professor, não a primeira
        ("", "a2"),      # aluno depois de aluno
        ("a2", "p3"),    # trocou
        ("p3", "a3"),    # trocou
    ]


def test_primeiro_turno_da_aula_nao_tem_contexto():
    """Continua vazio, mas agora pela mesma regra dos demais (não existe turno
    anterior de outro falante), e não por um caso especial em i == 0."""
    assert montar_pares([Turno("única fala", "ALUNO")]) == [("", "única fala")]


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


def test_o_input_format_das_regras_reais_e_o_que_o_codigo_implementa():
    """Sem mock: o valor que está em fias_rules.json tem de ser exatamente o
    que `montar_pares` faz. Se um dos dois andar sozinho, a aula inteira sai
    num formato de entrada que as regras não declaram."""
    assert load_rules("fias_rules")["classifier"]["input_format"] == FORMATO_ENTRADA_ESPERADO
    assert FORMATO_ENTRADA_ESPERADO == "pair:previous_turn_if_speaker_changed,current_turn"


def test_parametros_tokenizacao_muda_com_as_regras(monkeypatch):
    """Prova que a leitura não é decorativa: mudar o valor em fias_rules muda
    o que o classificador usa, sem precisar tocar em clf_bertimbau.py."""
    def regras_falsas(nome):
        assert nome == "fias_rules"
        return {"classifier": {
            "max_length": 128,
            "padding": "longest",
            "input_format": FORMATO_ENTRADA_ESPERADO,
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


def test_recusa_o_formato_antigo_de_turno_anterior_sempre(monkeypatch):
    """A recusa vale nos dois sentidos. "pair:previous_turn,current_turn" foi o
    formato declarado até 2026-09-23 e descrevia o turno anterior SEMPRE, sem
    olhar quem falava — o defeito. `montar_pares` não implementa mais isso,
    então o valor antigo tem de ser recusado como qualquer outro formato
    desconhecido, e não silenciosamente aceito por parecer familiar."""
    def regras_falsas(nome):
        return {"classifier": {
            "max_length": 256,
            "padding": "max_length",
            "input_format": "pair:previous_turn,current_turn",
        }}

    monkeypatch.setattr(clf_bertimbau, "load_rules", regras_falsas)
    with pytest.raises(ValueError, match="pair:previous_turn,current_turn"):
        _parametros_tokenizacao()


# ---- lote: o pico de memória deixa de crescer com a aula --------------------------


class _TokenizerPorLinha:
    """Tokenizer falso em que cada par gera uma linha diferente das outras.

    Um tokenizer que devolvesse a mesma linha para todo par (como o
    `_TokenizerFalso` acima) tornaria a comparação entre lote e passagem única
    verdadeira por acidente: qualquer embaralhamento ou repetição de linhas
    passaria despercebido. Aqui os ids saem do texto, então trocar duas linhas
    de lugar muda os valores."""

    def __call__(self, a, b, padding, truncation, max_length):
        linhas = []
        for texto_a, texto_b in zip(a, b):
            ids = [101] + [ord(c) for c in texto_a] + [102] + [ord(c) for c in texto_b] + [102]
            ids = ids[:max_length]
            linhas.append(ids + [0] * (max_length - len(ids)))
        return {
            "input_ids": linhas,
            "attention_mask": [[1 if i else 0 for i in linha] for linha in linhas],
            "token_type_ids": [[0] * len(linha) for linha in linhas],
        }


class _ModeloPorLinha:
    """Modelo falso cujos logits dependem só da própria linha — como um BERT em
    eval(), onde uma linha não influencia a outra. Anota o tamanho de cada lote
    recebido, que é como o teste distingue "dividiu em lotes" de "mandou tudo de
    uma vez e o resultado por acaso bateu"."""

    def __init__(self):
        self.lotes_recebidos: list[int] = []

    def __call__(self, **tensores):
        import torch

        ids = tensores["input_ids"]
        self.lotes_recebidos.append(int(ids.shape[0]))
        soma = ids.sum(dim=1).to(torch.float64)
        colunas = torch.arange(1, 11, dtype=torch.float64)
        return SimpleNamespace(logits=soma.unsqueeze(1) / (colunas * 7))


def _classificador_falso() -> tuple[clf_bertimbau.BertimbauClassificador, _ModeloPorLinha]:
    """Instância sem __init__: carregar o BERTimbau de verdade aqui exigiria o
    peso em disco, e o que está em teste é a divisão em lotes, não o load."""
    clf = object.__new__(clf_bertimbau.BertimbauClassificador)
    modelo = _ModeloPorLinha()
    clf._tok, clf._modelo = _TokenizerPorLinha(), modelo
    return clf, modelo


def _pares_de_teste(n: int) -> list[tuple[str, str]]:
    """Alterna os papéis a cada turno: assim metade dos pares leva contexto e a
    outra metade não, que é o material realista para os testes de lote."""
    return montar_pares([Turno(f"fala numero {i} da aula", "PROFESSOR" if i % 2 else "ALUNO")
                         for i in range(n)])


def test_logits_em_lote_sao_identicos_a_passagem_unica(monkeypatch):
    """O ponto do conserto inteiro (§44). Contar linhas não prova nada: um lote
    quebrado — deslocado, repetido, fora de ordem — devolve a quantidade certa
    de linhas com os valores errados. O que prova é a igualdade valor a valor
    contra a passagem única, com mais segmentos do que cabe num lote."""
    pares = _pares_de_teste(37)

    clf, modelo = _classificador_falso()
    monkeypatch.setattr(clf_bertimbau, "TAMANHO_DO_LOTE", len(pares) * 10)
    passagem_unica = clf.logits(pares)
    assert modelo.lotes_recebidos == [37], "a referência precisa ser mesmo uma passagem só"

    clf_lote, modelo_lote = _classificador_falso()
    monkeypatch.setattr(clf_bertimbau, "TAMANHO_DO_LOTE", 8)
    em_lote = clf_lote.logits(pares)

    assert modelo_lote.lotes_recebidos == [8, 8, 8, 8, 5], "não houve divisão em lotes"
    assert em_lote == passagem_unica


def test_logits_de_lista_vazia_nao_chama_o_modelo():
    clf, modelo = _classificador_falso()
    assert clf.logits([]) == []
    assert modelo.lotes_recebidos == []


def test_logits_com_menos_segmentos_que_um_lote(monkeypatch):
    """Aula curta: três segmentos, lote de 16. Uma passagem só, com as três
    linhas — e nada de um lote vazio no fim."""
    pares = _pares_de_teste(3)
    clf, modelo = _classificador_falso()
    monkeypatch.setattr(clf_bertimbau, "TAMANHO_DO_LOTE", 16)
    saida = clf.logits(pares)
    assert modelo.lotes_recebidos == [3]
    assert len(saida) == 3


def test_logits_com_numero_exato_de_lotes_nao_faz_passagem_vazia(monkeypatch):
    """Múltiplo exato do lote: 16 segmentos em lotes de 8 são duas passagens, não
    três — uma terceira, vazia, faria o modelo receber um tensor de zero linhas."""
    pares = _pares_de_teste(16)
    clf, modelo = _classificador_falso()
    monkeypatch.setattr(clf_bertimbau, "TAMANHO_DO_LOTE", 8)
    assert len(clf.logits(pares)) == 16
    assert modelo.lotes_recebidos == [8, 8]


def test_tamanho_do_lote_e_decisao_local_e_nao_sai_do_shared():
    """fias_rules.classifier não declara lote, e não deve: lote não muda
    resultado (a igualdade acima), só memória. Se um dia declarar, este teste
    cai e a decisão volta a ser do shared, como manda "o motor decide"."""
    classificador = load_rules("fias_rules")["classifier"]
    assert not [chave for chave in classificador if "batch" in chave or "lote" in chave]
    assert isinstance(clf_bertimbau.TAMANHO_DO_LOTE, int) and clf_bertimbau.TAMANHO_DO_LOTE > 0
