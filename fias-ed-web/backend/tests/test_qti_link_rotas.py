import datetime as dt

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
