"""Task 12: GET /api/ciclos/{ciclo_id}/relatorio — a trajetória dos índices ao
longo das aulas do ciclo e as coletas do questionário respondido pelos
estudantes.

A regra que define esta tarefa: nenhum campo aqui compara começo e fim. O
classificador que produz os índices tem taxa de erro sobre aula brasileira
real ainda não medida (seção 4 de docs/ESTADO_DE_VALIDACAO.md) — subtrair dois
números carregados dessa incerteza e chamar o resultado de progresso
emprestaria ao sistema uma autoridade que ele não tem sobre a prática de uma
pessoa. `test_corpo_so_tem_os_campos_esperados` e
`test_corpo_bruto_sem_palavra_de_veredito` são quem prova isso — juntos,
porque cobrem coisas diferentes: um pega campo novo (qualquer nome), o outro
pega texto ruim dentro de um campo permitido.
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


def test_corpo_bruto_sem_palavra_de_veredito(cliente, ciclo_com_tres_aulas):
    """Nenhuma palavra de veredito no texto bruto da resposta. Cobre texto
    dentro de um campo permitido — o que `test_corpo_so_tem_os_campos_esperados`
    (abaixo) não cobre, porque olha só para nomes de chave, não para valores."""
    ciclo, _ = ciclo_com_tres_aulas
    resposta = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio")
    assert resposta.status_code == 200
    assert not re.search(r"melhor|pior|evolu|progress|regred", resposta.text.lower())


# Lista de permissão, não de proibição: uma lista negra de nomes proibidos
# ("variacao", "diferenca", "delta"...) é jogo de adivinhação — a revisão
# achou "resumo_numerico" em um minuto, e sempre existe um nome novo. Mesmo
# mecanismo de app/core/logging.py (ALLOWED_FIELDS): lá uma lista fechada de
# campos permitidos impede nome de pessoa ou texto de transcrição de vazar
# para o log; aqui a mesma ideia protege honestidade científica em vez de
# privacidade. É mais fácil enumerar o que PODE existir do que adivinhar tudo
# que não pode: qualquer campo novo, com qualquer nome, quebra este teste, e
# quem acrescentar um campo legítimo tem de atualizar a lista aqui
# conscientemente — o comentário acima é o que lê nesse momento.
CHAVES_TOPO = {"ciclo", "n_aulas_realizadas", "trajetoria", "coletas"}
CHAVES_CICLO = {"id", "turma", "disciplina", "n_aulas_previstas", "iniciado_em", "encerrado_em"}
CHAVES_TRAJETORIA = {"aula_id", "lesson_date", "status", "indices"}
CHAVES_COLETA = {"id", "coletado_em", "origem", "response_count", "displayable", "octantes"}


def test_corpo_so_tem_os_campos_esperados(cliente, ciclo_com_tres_aulas, coleta_em):
    """O classificador que produz os índices tem taxa de erro sobre aula
    brasileira real ainda não medida (seção 4 de docs/ESTADO_DE_VALIDACAO.md)
    — por isso o sistema mostra os números em ordem cronológica mas nunca os
    compara por conta própria (nenhuma diferença, tendência, "subiu"/"desceu").
    Este teste é quem garante que nenhum campo novo, disfarçado de nome
    inócuo, introduza essa comparação: o conjunto de chaves de cada nível do
    corpo tem de ser EXATAMENTE o esperado, não apenas "sem as palavras
    óbvias"."""
    ciclo, _ = ciclo_com_tres_aulas
    coleta_em(ciclo, "2026-03-05")  # sem isto corpo["coletas"] ficaria vazio e o loop abaixo não provaria nada
    corpo = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio").json()

    assert set(corpo) == CHAVES_TOPO
    assert set(corpo["ciclo"]) == CHAVES_CICLO

    assert corpo["trajetoria"]  # a fixture grava 3 aulas — loop vazio não provaria nada
    for item in corpo["trajetoria"]:
        assert set(item) == CHAVES_TRAJETORIA

    assert corpo["coletas"]
    for coleta in corpo["coletas"]:
        assert set(coleta) == CHAVES_COLETA


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


def test_coletas_em_ordem_de_coletado_em_com_valores_gravados(cliente, ciclo_com_tres_aulas, coleta_em):
    """Além da ordem, os valores de cada coleta têm de bater com o que foi
    gravado para AQUELA linha, não com qualquer coleta do ciclo — displayable
    varia entre as duas de propósito, para que um `SELECT` que cruzasse
    ColetaQTI/ResultadoQTI de linhas diferentes tivesse uma chance real de ser
    pego (antes deste teste, a única checagem era "octantes não vazio", que
    não provava nada sobre qual octante pertence a qual coleta)."""
    ciclo, _ = ciclo_com_tres_aulas
    c_tarde = coleta_em(ciclo, "2026-03-20", displayable=True)
    c_cedo = coleta_em(ciclo, "2026-03-05", displayable=False)

    corpo = cliente.get(f"/api/ciclos/{ciclo.id}/relatorio").json()
    datas = [c["coletado_em"] for c in corpo["coletas"]]
    assert datas == ["2026-03-05", "2026-03-20"]

    gravadas = {str(c_cedo.id): c_cedo, str(c_tarde.id): c_tarde}
    assert {c["id"] for c in corpo["coletas"]} == set(gravadas)
    for item in corpo["coletas"]:
        gravada = gravadas[item["id"]]
        assert item["origem"] == gravada.origem
        assert item["response_count"] == gravada.response_count
        assert item["displayable"] == gravada.displayable
        assert item["octantes"]


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
