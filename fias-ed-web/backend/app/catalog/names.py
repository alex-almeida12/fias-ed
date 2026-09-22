import unicodedata


def name_key(text: str) -> str:
    """Chave de comparação: minúsculas, sem acentos, espaços colapsados."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.lower().split())
