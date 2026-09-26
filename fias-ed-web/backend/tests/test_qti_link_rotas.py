import datetime as dt
import json
import uuid

import pytest
from sqlalchemy import select

from app.models import Ciclo, ColetaQTI, Disciplina, Escola, LinkQTI, Turma
from app.qti.links import criar_link, link_valido
from tests.helpers import login, make_user


def _ciclo_do_outro_professor(db, username: str) -> Ciclo:
    outro = make_user(db, username)
    escola = Escola(name="Outra Escola", name_key=f"outra escola {username}")
    db.add(escola)
    db.flush()
    turma = Turma(escola_id=escola.id, professor_id=outro.id, name="7º Ano A")
    disciplina = Disciplina(professor_id=outro.id, name="História")
    db.add_all([turma, disciplina])
    db.flush()
    ciclo_do_outro = Ciclo(turma_id=turma.id, disciplina_id=disciplina.id, professor_id=outro.id,
                          n_aulas_previstas=8, iniciado_em=dt.date(2026, 3, 1))
    db.add(ciclo_do_outro)
    db.commit()
    db.refresh(ciclo_do_outro)
    return ciclo_do_outro


@pytest.fixture
def ciclo_de_outro(db):
    return _ciclo_do_outro_professor(db, "outro-professor-link")


@pytest.fixture
def link_de_outro(db):
    ciclo_do_outro = _ciclo_do_outro_professor(db, "outro-professor-link-revogar")
    coleta = ColetaQTI(ciclo_id=ciclo_do_outro.id, coletado_em=dt.date(2026, 3, 1),
                       origem="COLETA_NATIVA", response_count=0, displayable=False,
                       qti_config_version="1.0.0", cabecalho_recebido=None)
    db.add(coleta)
    db.flush()
    link, _token = criar_link(db, coleta, n_estudantes=30, dias=7)
    return link


def test_gerar_link_devolve_a_url_uma_unica_vez(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 201
    url = r.json()["url"]
    assert "/responder/" in url
    assert r.json()["limite_respostas"] == 33
    token = url.rsplit("/", 1)[-1]
    assert db.scalar(select(LinkQTI)).token_hash != token


def test_gerar_link_cria_a_coleta_nativa_se_nao_houver(db, client, ciclo):
    login(client, "professora-ciclo")
    client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    coleta = db.query(ColetaQTI).one()
    assert coleta.origem == "COLETA_NATIVA" and coleta.response_count == 0


def test_gerar_dois_links_na_mesma_data_reusa_a_coleta(db, client, ciclo):
    """Duas coletas vivas na mesma data fariam a triangulação escolher
    arbitrariamente qual vale — o mesmo defeito que a reimportação evita do
    outro lado (test_reimportar_na_mesma_data_substitui_em_vez_de_duplicar)."""
    login(client, "professora-ciclo")
    for _ in range(2):
        client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert db.query(ColetaQTI).count() == 1
    assert db.query(LinkQTI).count() == 2


def test_gerar_link_com_turma_de_50_usa_aritmetica_inteira(db, client, ciclo):
    """30 esconde o erro de arredondamento: 30 * 1.10 e 30 * 11 / 10 coincidem.
    50 é onde os dois divergem (50 * 1.10 == 55.00000000000001 em ponto
    flutuante, e math.ceil disso dá 56; a aritmética inteira dá 55)."""
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 50, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 201
    assert r.json()["limite_respostas"] == 55


def test_gerar_link_reusa_coleta_nativa_ja_existente_na_data(db, client, ciclo):
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=dt.date(2026, 9, 1), origem="COLETA_NATIVA",
                       response_count=0, displayable=False, qti_config_version="1.0.0",
                       cabecalho_recebido=None)
    db.add(coleta)
    db.commit()
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 201
    assert db.query(ColetaQTI).count() == 1
    assert db.query(ColetaQTI).one().id == coleta.id


def test_gerar_link_recusa_quando_ja_existe_coleta_importada_na_data(db, client, ciclo):
    """`coleta_nativa_do_dia` não filtra por origem na consulta: se o que
    encontra na data é uma coleta importada (que tem respostas de verdade),
    recusa em vez de substituir — ao contrário da reimportação, gerar um
    link não traz dado nenhum que justifique apagar trabalho existente."""
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=dt.date(2026, 9, 1), origem="IMPORTACAO_EXTERNA",
                       response_count=12, displayable=True, qti_config_version="1.0.0",
                       cabecalho_recebido="response_id,q1")
    db.add(coleta)
    db.commit()
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 409
    assert r.json()["error_code"] == "COLETA_JA_EXISTE"
    assert db.query(ColetaQTI).count() == 1
    assert db.query(LinkQTI).count() == 0


def test_gerar_link_em_ciclo_de_outro_professor_da_404(db, client, ciclo, ciclo_de_outro):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo_de_outro.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 404


def test_revogar_derruba_o_link(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    token = r.json()["url"].rsplit("/", 1)[-1]
    link = db.scalar(select(LinkQTI))
    assert client.post(f"/api/qti/links/{link.id}/revogar").status_code == 204
    assert link_valido(db, token) is None


def test_revogar_link_de_outro_professor_da_404(db, client, ciclo, link_de_outro):
    login(client, "professora-ciclo")
    assert client.post(f"/api/qti/links/{link_de_outro.id}/revogar").status_code == 404


# ---------------------------------------------------------------------------
# Task 6 (w3b): sem o `id` do link na resposta de gerar_link, e sem `links_qti`
# em GET /ciclos, a rota de revogar existe mas nenhuma tela tem como chamá-la.
# ---------------------------------------------------------------------------


def test_gerar_link_devolve_id_de_um_link_que_existe_no_banco(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    link_id = r.json()["id"]
    assert db.get(LinkQTI, uuid.UUID(link_id)) is not None


def test_get_ciclos_traz_links_qti_vivo_e_fica_vazio_depois_de_revogar(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    link_id = r.json()["id"]

    item = next(c for c in client.get("/api/ciclos").json() if c["id"] == str(ciclo.id))
    assert item["links_qti"] == [{"id": link_id, "expira_em": r.json()["expira_em"],
                                  "limite_respostas": 33, "coletado_em": "2026-09-01"}]

    assert client.post(f"/api/qti/links/{link_id}/revogar").status_code == 204

    # É este que prova que "vivo" significa vivo: o mesmo ciclo, revogado, some da lista.
    item_depois = next(c for c in client.get("/api/ciclos").json() if c["id"] == str(ciclo.id))
    assert item_depois["links_qti"] == []


def test_get_ciclos_omite_link_com_expira_em_no_passado(db, client, ciclo):
    """Mesma simetria de test_..._fica_vazio_depois_de_revogar, para o filtro de expiração:
    sem ele, um link vencido continuaria oferecendo 'Revogar' na tela — o professor acharia
    que o questionário está aberto quando os estudantes já recebem LINK_INVALIDO."""
    login(client, "professora-ciclo")
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=dt.date(2026, 9, 1), origem="COLETA_NATIVA",
                       response_count=0, displayable=False, qti_config_version="1.0.0",
                       cabecalho_recebido=None)
    db.add(coleta)
    db.flush()
    link, _token = criar_link(db, coleta, n_estudantes=30, dias=7)
    link.expira_em = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    db.commit()

    item = next(c for c in client.get("/api/ciclos").json() if c["id"] == str(ciclo.id))
    assert item["links_qti"] == []


def test_get_ciclos_omite_link_com_deleted_at_preenchido(db, client, ciclo):
    login(client, "professora-ciclo")
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=dt.date(2026, 9, 1), origem="COLETA_NATIVA",
                       response_count=0, displayable=False, qti_config_version="1.0.0",
                       cabecalho_recebido=None)
    db.add(coleta)
    db.flush()
    link, _token = criar_link(db, coleta, n_estudantes=30, dias=7)
    link.deleted_at = dt.datetime.now(dt.timezone.utc)
    db.commit()

    item = next(c for c in client.get("/api/ciclos").json() if c["id"] == str(ciclo.id))
    assert item["links_qti"] == []


def test_get_ciclos_omite_link_vivo_de_coleta_apagada(db, client, ciclo):
    login(client, "professora-ciclo")
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=dt.date(2026, 9, 1), origem="COLETA_NATIVA",
                       response_count=0, displayable=False, qti_config_version="1.0.0",
                       cabecalho_recebido=None)
    db.add(coleta)
    db.flush()
    link, _token = criar_link(db, coleta, n_estudantes=30, dias=7)
    coleta.deleted_at = dt.datetime.now(dt.timezone.utc)
    db.commit()

    item = next(c for c in client.get("/api/ciclos").json() if c["id"] == str(ciclo.id))
    assert item["links_qti"] == []


def test_get_ciclos_nunca_expoe_token_nem_token_hash(client, ciclo):
    login(client, "professora-ciclo")
    client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    r = client.get("/api/ciclos")
    # Varre o JSON serializado inteiro, não só as chaves do primeiro nível: "token" é
    # substring tanto de "token" quanto de "token_hash".
    assert "token" not in json.dumps(r.json()).lower()


def test_relatorio_do_ciclo_nao_ganha_links_qti(client, ciclo):
    login(client, "professora-ciclo")
    client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    r = client.get(f"/api/ciclos/{ciclo.id}/relatorio")
    assert "links_qti" not in r.json()["ciclo"]
