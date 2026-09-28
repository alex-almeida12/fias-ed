"""Troca nomes próprios por [NOME] (PRIVACY.md, §48).

União de dois detectores: um NER local de português (CPU, dezenas de MB) e uma
heurística de maiúscula. Qualquer um dos dois que aponte, pseudonimiza — NER em
fala transcrita perde casos que a heurística pega, e vice-versa. O viés é
deliberadamente conservador: um falso positivo troca uma palavra comum por
[NOME] na versão exportada; um falso negativo vaza o nome de um estudante.

O NER (spaCy, modelo pt_core_news_sm — MIT/CC BY-SA, instalado como dependência
comum do pyproject.toml) é carregado uma vez, em CPU, a partir do pacote já
instalado na imagem; nada aqui faz uma chamada de rede em tempo de execução. Se
o modelo não estiver disponível no ambiente (ausente, corrompido, biblioteca
não instalada), a heurística continua protegendo sozinha — é o que
test_sem_modelo_de_ner_a_heuristica_ainda_protege existe para garantir: um
modelo ausente não pode virar vazamento silencioso.
"""
import re
from functools import lru_cache

MARCADOR = "[NOME]"

# Palavras que começam com maiúscula por razão gramatical, não por serem nome.
NAO_SAO_NOMES = {
    "A", "As", "O", "Os", "Um", "Uma", "Ele", "Ela", "Eles", "Elas", "Eu", "Nós", "Você", "Vocês",
    "Vamos", "Vem", "Vai", "Então", "Mas", "Quando", "Quem", "Que", "Qual", "Como", "Onde", "Por",
    "Bom", "Boa", "Olha", "Agora", "Hoje", "Ontem", "Amanhã", "Sim", "Não", "Certo", "Pronto",
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
    "Outubro", "Novembro", "Dezembro",
}

_PALAVRA = re.compile(r"\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+)\b")


@lru_cache(maxsize=1)
def _modelo():
    """Carrega o pipeline de NER uma única vez. None se o modelo não está disponível."""
    try:
        import spacy
        return spacy.load("pt_core_news_sm", disable=["parser", "lemmatizer", "attribute_ruler"])
    except Exception:  # modelo ausente/corrompido/spaCy não instalado: sem chamada de rede, sem crash
        return None


def nomes_por_ner(texto: str) -> set[str]:
    """Spans marcados como pessoa pelo modelo. Carregado uma vez, em CPU."""
    nlp = _modelo()
    if nlp is None:  # modelo ausente: a heurística sozinha ainda protege
        return set()
    return {ent.text for ent in nlp(texto).ents if ent.label_ in ("PER", "PERSON")}


def nomes_por_heuristica(texto: str) -> set[str]:
    """A regra de maiúscula, mantida como rede: nomes que o NER pode perder.

    Não marca a primeira palavra da frase (maiúscula por regra de escrita, não
    indício de nome) nem palavras do NAO_SAO_NOMES — casos assim ficam por
    conta do NER, de propósito (ver test_ner_pega_nome_que_a_heuristica_perde)."""
    nomes = set()
    for m in _PALAVRA.finditer(texto):
        palavra = m.group(1)
        if palavra in NAO_SAO_NOMES:
            continue
        anterior = texto[: m.start()].rstrip()
        if not anterior or anterior.endswith((".", "!", "?")):
            continue
        nomes.add(palavra)
    return nomes


def pseudonimizar(texto: str) -> str:
    """União de NER e heurística: qualquer um dos dois que aponte um nome, troca."""
    if not texto:
        return texto
    nomes = nomes_por_ner(texto) | nomes_por_heuristica(texto)
    if not nomes:
        return texto
    padrao = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in sorted(nomes, key=len, reverse=True)) + r")\b")
    return padrao.sub(MARCADOR, texto)
