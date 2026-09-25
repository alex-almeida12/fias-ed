"""Task 12: GET /api/ciclos/{ciclo_id}/relatorio — a trajetória dos índices ao
longo das aulas do ciclo e as coletas do questionário respondido pelos
estudantes.

A regra que define esta tarefa: nenhum campo aqui compara começo e fim. O
classificador que produz os índices tem taxa de erro sobre aula brasileira
real ainda não medida (seção 4 de docs/ESTADO_DE_VALIDACAO.md) — subtrair dois
números carregados dessa incerteza e chamar o resultado de progresso
emprestaria ao sistema uma autoridade que ele não tem sobre a prática de uma
pessoa. `test_corpo_bruto_sem_veredito` é quem prova isso.
"""
import re

import pytest

from tests.helpers import login, make_user


@pytest.fixture
def cliente(client_factory, professor):
    c = client_factory()
    login(c, professor.username)
    return c


def test_trajetoria_em_ordem_de_data(cliente, ciclo_com_tres_aulas):
    ciclo, aulas = ciclo_com_tres_aulas
    corpo = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio").json()
    datas = [item["lesson_date"] for item in corpo["trajetoria"]]
    assert datas == sorted(datas)
    assert datas == [a.lesson_date.isoformat() for a in aulas]


def test_declara_previstas_e_realizadas(cliente, ciclo_com_tres_aulas):
    ciclo, aulas = ciclo_com_tres_aulas
    corpo = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio").json()
    assert corpo["ciclo"]["n_aulas_previstas"] == 8
    assert corpo["n_aulas_realizadas"] == len(aulas) == 3


def _chaves(obj) -> set[str]:
    """Todas as chaves usadas em qualquer nível do JSON (corpo ou sub-objetos/listas)."""
    chaves: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            chaves.add(k)
            chaves |= _chaves(v)
    elif isinstance(obj, list):
        for item in obj:
            chaves |= _chaves(item)
    return chaves


def test_corpo_bruto_sem_veredito(cliente, ciclo_com_tres_aulas):
    """Nenhuma palavra de veredito no corpo bruto da resposta — mas uma
    checagem só de vocabulário não basta: um campo `"variacao": ultimo -
    primeiro` passaria batido por ela sem usar nenhuma dessas palavras (a
    mutação 2 do brief da task provou isso). Por isso o teste também nega
    explicitamente o NOME de qualquer campo derivado de comparação, e não só
    as palavras no texto."""
    ciclo, _ = ciclo_com_tres_aulas
    resposta = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio")
    assert resposta.status_code == 200
    assert not re.search(r"melhor|pior|evolu|progress|regred", resposta.text.lower())

    chaves = {c.lower() for c in _chaves(resposta.json())}
    for proibida in ("variacao", "diferenca", "delta", "tendencia", "trend", "comparacao"):
        assert proibida not in chaves, proibida


def test_aula_sem_indices_aparece_na_trajetoria_com_lista_vazia(cliente, ciclo_com_tres_aulas):
    ciclo, aulas = ciclo_com_tres_aulas
    corpo = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio").json()
    por_aula = {item["aula_id"]: item["indices"] for item in corpo["trajetoria"]}

    sem_indices = [a for a in aulas if a.status != "FIAS_COMPLETED"]
    assert len(sem_indices) == 2  # a1 e a3 do fixture, ainda em DRAFT
    for a in sem_indices:
        assert por_aula[str(a.id)] == []

    com_indices = [a for a in aulas if a.status == "FIAS_COMPLETED"]
    assert len(com_indices) == 1  # a2, a única classificada
    for a in com_indices:
        assert por_aula[str(a.id)]


def test_coletas_em_ordem_de_coletado_em_com_octantes(cliente, ciclo_com_tres_aulas, coleta_em):
    ciclo, _ = ciclo_com_tres_aulas
    coleta_em(ciclo, "2026-03-20")
    coleta_em(ciclo, "2026-03-05")

    corpo = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio").json()
    datas = [c["coletado_em"] for c in corpo["coletas"]]
    assert datas == ["2026-03-05", "2026-03-20"]
    assert all(c["octantes"] for c in corpo["coletas"])


def test_ciclo_de_outro_professor_da_404(client_factory, db, ciclo_com_tres_aulas):
    ciclo, _ = ciclo_com_tres_aulas
    make_user(db, "outro-professor-relatorio-ciclo")
    outro = client_factory()
    login(outro, "outro-professor-relatorio-ciclo")
    r = outro.get(f"/api/ciclos/{ciclo.id}/relatorio")
    assert r.status_code == 404


def test_ciclo_sem_aula_nenhuma_devolve_200_com_trajetoria_vazia(cliente, ciclo):
    corpo = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio").json()
    assert corpo["trajetoria"] == []
    assert corpo["n_aulas_realizadas"] == 0
