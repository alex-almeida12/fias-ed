import datetime as dt

from app.models import Ciclo
from tests.helpers import login


def test_ciclo_nasce_aberto_e_com_o_numero_declarado(db, turma, disciplina, professor):
    c = Ciclo(turma_id=turma.id, disciplina_id=disciplina.id, professor_id=professor.id,
              n_aulas_previstas=8, iniciado_em=dt.date(2026, 3, 1))
    db.add(c); db.commit(); db.refresh(c)
    assert c.encerrado_em is None
    assert c.n_aulas_previstas == 8
    assert c.deleted_at is None


def test_criar_ciclo_devolve_201_e_o_numero_declarado(client, turma, disciplina):
    login(client, "professora-ciclo")
    r = client.post("/api/ciclos", json={"turma_id": str(turma.id), "disciplina_id": str(disciplina.id),
                                         "n_aulas_previstas": 8, "iniciado_em": "2026-03-01"})
    assert r.status_code == 201 and r.json()["n_aulas_previstas"] == 8


def test_criar_ciclo_sem_autenticacao_devolve_401(client, turma, disciplina):
    """Achado da revisão da Task 2: turma/disciplina não podem deixar o client logado
    escondido atrás de si — quem pede só essas fixtures continua anônimo."""
    r = client.post("/api/ciclos", json={"turma_id": str(turma.id), "disciplina_id": str(disciplina.id),
                                         "n_aulas_previstas": 8, "iniciado_em": "2026-03-01"})
    assert r.status_code == 401


def test_a_primeira_aula_gravada_do_ciclo_e_a_primeira(db, client, ciclo, aula_em, posicao):
    a1 = aula_em(ciclo, "2026-03-02")
    a2 = aula_em(ciclo, "2026-03-09")
    assert posicao(a1) == "primeira"
    assert posicao(a2) == "meio"


def test_ciclo_de_uma_aula_so_tem_a_mesma_aula_como_primeira_e_ultima(db, client, turma, disciplina, aula_em, posicao):
    """Review Focus 2: n_aulas_previstas = 1 não pode quebrar a regra das pontas."""
    login(client, "professora-ciclo")
    r = client.post("/api/ciclos", json={"turma_id": str(turma.id), "disciplina_id": str(disciplina.id),
                                         "n_aulas_previstas": 1, "iniciado_em": "2026-03-01"})
    ciclo_id = r.json()["id"]
    a = aula_em(ciclo_id, "2026-03-02")
    client.post(f"/api/ciclos/{ciclo_id}/encerrar")
    assert posicao(a) == "primeira_e_ultima"


def test_encerrar_define_a_ultima_pela_aula_realmente_gravada(db, client, ciclo, aula_em, posicao):
    """Review Focus: o professor declarou 8 e gravou 3."""
    login(client, "professora-ciclo")
    aula_em(ciclo, "2026-03-02"); aula_em(ciclo, "2026-03-09")
    ultima = aula_em(ciclo, "2026-03-16")
    client.post(f"/api/ciclos/{ciclo.id}/encerrar")
    assert posicao(ultima) == "ultima"


def test_aula_fora_de_ciclo_devolve_fora(db, aula_avulsa, posicao):
    assert posicao(aula_avulsa) == "fora"
