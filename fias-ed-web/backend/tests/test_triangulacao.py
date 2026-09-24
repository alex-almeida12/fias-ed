"""Task 7: triangulação FIAS × QTI — pôr lado a lado o que o áudio mostrou e o
que os estudantes perceberam, sem classificar e sem dar veredito. Toda a
ciência (quais pares existem, o que cada um compara, a pergunta de reflexão)
vem de `fias_ed_engine.triangulation.triangulate`; aqui só se prova que:

1. a coleta escolhida é sempre a mais recente ANTERIOR ou igual à data da
   aula (`coleta_vigente`), com desempate determinístico quando duas coletas
   caem na mesma data;
2. sem coleta vigente, a triangulação ainda traz a pergunta de reflexão, só
   não traz os números do QTI;
3. com coleta vigente, os números que chegam em cada par são de fato os do
   `ResultadoQTI` gravado — não basta a ausência ser tratada;
4. o que `triangular` devolve é também o que fica gravado em `triangulacao` —
   "persiste o que o motor devolveu" (spec da task) não é só o retorno da
   função —, e recalcular substitui o que havia antes, nunca duplica.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import ResultadoQTI, Triangulacao
from app.triangulacao.service import coleta_vigente, triangular
from tests.helpers import classificar_para_triangulacao


def test_usa_a_coleta_mais_recente_anterior_a_aula(db, ciclo, aula_em, coleta_em):
    coleta_em(ciclo, "2026-03-01")
    marco = coleta_em(ciclo, "2026-04-01")
    coleta_em(ciclo, "2026-06-01")          # posterior à aula: não pode ser escolhida
    aula = aula_em(ciclo, "2026-05-10")
    assert coleta_vigente(db, aula).id == marco.id


def test_duas_coletas_na_mesma_data_escolhem_sempre_a_criada_por_ultimo(db, ciclo, aula_em, coleta_em):
    """Determinismo. Sem o desempate explícito, a escolha ficaria por conta da ordem
    de varredura do banco, que pode mudar entre execuções sem ninguém tocar no código."""
    coleta_em(ciclo, "2026-03-01")
    ultima = coleta_em(ciclo, "2026-03-01")
    aula = aula_em(ciclo, "2026-04-01")
    for _ in range(5):
        assert coleta_vigente(db, aula).id == ultima.id


def test_duas_coletas_com_created_at_empatado_escolhem_sempre_a_de_maior_id(db, ciclo, aula_em, coleta_em):
    """`created_at` é `default=utcnow` do lado do Python, não do banco: duas
    chamadas sequenciais de `coleta_em` nunca colidem nele de verdade, então o
    teste acima passa pelo `created_at` e o desempate por `id` em
    `coleta_vigente` fica sem cobertura. Aqui o `created_at` é forçado a ser
    exatamente o mesmo nas duas coletas — só o `id` pode decidir."""
    mesmo_instante = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    primeira = coleta_em(ciclo, "2026-03-01", created_at=mesmo_instante)
    segunda = coleta_em(ciclo, "2026-03-01", created_at=mesmo_instante)
    assert primeira.created_at == segunda.created_at
    maior_id = max(primeira, segunda, key=lambda c: c.id)
    aula = aula_em(ciclo, "2026-04-01")
    for _ in range(5):
        assert coleta_vigente(db, aula).id == maior_id.id


def test_sem_coleta_a_triangulacao_traz_a_pergunta_sem_os_valores(db, aula_classificada):
    """Sem QTI o professor ainda recebe a pergunta de reflexão; só não recebe o
    número ao lado. Uma triangulação vazia não teria por que existir."""
    pares = triangular(db, aula_classificada)
    assert len(pares) == 4
    assert all(p["qti_available"] is False for p in pares)
    assert all(p["reflection_question"] for p in pares)


def test_com_coleta_a_triangulacao_traz_os_valores_do_resultado_qti(db, ciclo, aula_em, coleta_em, monkeypatch):
    """Sem este teste, o anterior provaria só que a ausência de QTI é tratada —
    nada provaria que os valores chegam de fato ao resultado quando há coleta."""
    coleta = coleta_em(ciclo, "2026-03-01")
    resultado = db.scalar(select(ResultadoQTI).where(ResultadoQTI.coleta_id == coleta.id))
    aula = aula_em(ciclo, "2026-04-01")
    classificar_para_triangulacao(db, aula, monkeypatch)

    pares = triangular(db, aula)
    assert len(pares) == 4
    assert all(p["qti_available"] is True for p in pares)
    for p in pares:
        for item in p["qti"]:
            assert item["value"] == resultado.octantes[item["octant"]]


def test_coleta_com_poucas_respostas_nao_exibe_os_valores(db, ciclo, aula_em, coleta_em, aula_classificada):
    """Existe coleta, mas ela não é exibível: a régua do QTI diz que poucas
    respostas não viram número. A pergunta de reflexão continua; os valores, não.
    Sem este teste, um `displayable` fixo em True passaria despercebido e a tela
    mostraria justamente o que o QTI manda não mostrar."""
    coleta = coleta_em(ciclo, "2026-03-01", displayable=False)
    assert coleta_vigente(db, aula_classificada).id == coleta.id

    pares = triangular(db, aula_classificada)
    assert len(pares) == 4
    assert all(p["qti_available"] is False for p in pares)
    assert all(all(item["value"] is None for item in p["qti"]) for p in pares)
    assert all(p["reflection_question"] for p in pares)


def test_triangular_grava_os_pares_e_recalcular_substitui_sem_duplicar(db, aula_classificada):
    primeira_vez = triangular(db, aula_classificada)
    gravados = db.scalars(select(Triangulacao).where(Triangulacao.aula_id == aula_classificada.id)).all()
    assert len(gravados) == 4
    assert {g.pair_id for g in gravados} == {p["pair_id"] for p in primeira_vez}
    algum = next(g for g in gravados if g.pair_id == primeira_vez[0]["pair_id"])
    par = primeira_vez[0]
    assert algum.fias_kind == par["fias"]["kind"]
    assert algum.fias_ref == par["fias"]["ref"]
    assert algum.fias_value == par["fias"]["value"]
    assert algum.qti_available == par["qti_available"]
    assert algum.qti_values == par["qti"]
    assert algum.reflection_question == par["reflection_question"]
    assert algum.source_reference == par["source_reference"]
    assert algum.validation_status == par["validation_status"] == "PENDING_SCIENTIFIC_VALIDATION"

    triangular(db, aula_classificada)  # recalcular não pode duplicar
    ainda = db.scalars(select(Triangulacao).where(Triangulacao.aula_id == aula_classificada.id)).all()
    assert len(ainda) == 4
