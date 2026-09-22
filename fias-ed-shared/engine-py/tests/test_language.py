from fias_ed_engine.language import find_forbidden
from fias_ed_engine.rules import load_rules


def test_detects_forbidden():
    assert sorted(find_forbidden("Seu desempenho foi ruim")) == ["desempenho", "ruim"]
    assert find_forbidden("Você fez errado") == ["errado"]
    assert find_forbidden("A aula está não conforme") == ["conforme", "não conforme"]
    assert find_forbidden("Os resultados foram ruins") == ["ruim"]


def test_word_boundaries():
    assert find_forbidden("Vale anotar os momentos de pergunta") == []
    assert find_forbidden("conformidade das rotinas") == []


def test_rules_texts_are_clean():
    texts = [r["interpretation"] for r in load_rules("mtss_rules")["rules"] if r["enabled"]]
    ped = load_rules("pedagogical_rules")
    texts += [r["text"] for r in ped["recommendations"]]
    texts += [p["reflection_question"] for p in ped["triangulation_pairs"]]
    offenders = {t: find_forbidden(t) for t in texts if find_forbidden(t)}
    assert offenders == {}
