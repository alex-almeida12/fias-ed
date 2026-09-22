import pytest

from app.pipeline.pseudonymize import pseudonimizar


@pytest.mark.parametrize("entrada,esperado", [
    ("Maria, responde pra gente", "[NOME], responde pra gente"),
    ("o João e a Ana conversaram", "o [NOME] e a [NOME] conversaram"),
    ("boa tarde, turma", "boa tarde, turma"),
])
def test_casos_diretos(entrada, esperado):
    assert pseudonimizar(entrada) == esperado


def test_primeira_palavra_da_frase_nao_e_nome_so_por_ser_maiuscula():
    # "Vamos" abre a frase; maiúscula ali não indica nome próprio.
    assert pseudonimizar("Vamos começar a aula") == "Vamos começar a aula"


@pytest.mark.parametrize("entrada", [
    "a Vitória veio ao quadro",
    "chama a Bela aqui",
    "fala, Paz",
])
def test_homonimo_de_substantivo_comum_e_pseudonimizado(entrada):
    """Review Focus 4: na dúvida, pseudonimiza. Um falso positivo troca uma
    palavra comum por [NOME] na versão exportada; um falso negativo vaza o nome
    de um estudante, que é o dano que o §48 existe para impedir."""
    assert "[NOME]" in pseudonimizar(entrada)


def test_nome_no_meio_de_frase_com_pontuacao():
    assert pseudonimizar("então, Pedro, o que você acha?") == "então, [NOME], o que você acha?"


def test_sigla_em_caixa_alta_nao_vira_nome():
    assert pseudonimizar("a prova do ENEM") == "a prova do ENEM"


def test_ner_pega_nome_que_a_heuristica_perde(monkeypatch):
    # Nome no começo da frase: a heurística se cala de propósito, o NER não.
    monkeypatch.setattr("app.pipeline.pseudonymize.nomes_por_ner", lambda t: {"Rafael"})
    assert pseudonimizar("Rafael, vem ao quadro") == "[NOME], vem ao quadro"


def test_sem_modelo_de_ner_a_heuristica_ainda_protege(monkeypatch):
    """O modelo pode faltar no diretório; isso não pode virar vazamento silencioso."""
    monkeypatch.setattr("app.pipeline.pseudonymize.nomes_por_ner", lambda t: set())
    assert "[NOME]" in pseudonimizar("chamei a Ana no quadro")


def test_texto_vazio():
    assert pseudonimizar("") == ""
