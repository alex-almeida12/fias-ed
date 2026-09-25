import datetime as dt

from app.models import Ciclo
from tests.helpers import login, make_user


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


def test_listar_ciclos_devolve_vazio_sem_ciclos(client, db):
    make_user(db, "professora-sem-ciclos")
    login(client, "professora-sem-ciclos")
    r = client.get("/api/ciclos")
    assert r.status_code == 200 and r.json() == []


def test_listar_ciclos_devolve_so_os_do_professor(client_factory, db, ciclo):
    """Task 14b: um professor não pode ver o ciclo de outro na listagem."""
    dono = client_factory()
    login(dono, "professora-ciclo")
    make_user(db, "outro-professor-lista")
    outro = client_factory()
    login(outro, "outro-professor-lista")
    assert [c["id"] for c in dono.get("/api/ciclos").json()] == [str(ciclo.id)]
    assert outro.get("/api/ciclos").json() == []


def test_listar_ciclos_ordena_do_mais_recente_para_o_mais_antigo(client, turma, disciplina):
    login(client, "professora-ciclo")
    antigo = client.post("/api/ciclos", json={"turma_id": str(turma.id), "disciplina_id": str(disciplina.id),
                                              "n_aulas_previstas": 4, "iniciado_em": "2026-01-01"}).json()
    recente = client.post("/api/ciclos", json={"turma_id": str(turma.id), "disciplina_id": str(disciplina.id),
                                               "n_aulas_previstas": 6, "iniciado_em": "2026-06-01"}).json()
    r = client.get("/api/ciclos")
    assert [c["id"] for c in r.json()] == [recente["id"], antigo["id"]]


def test_listar_ciclos_omite_ciclo_apagado(client, db, ciclo):
    login(client, "professora-ciclo")
    ciclo.deleted_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    assert client.get("/api/ciclos").json() == []


def test_listar_ciclos_traz_turma_e_disciplina(client, turma, disciplina, ciclo):
    login(client, "professora-ciclo")
    r = client.get("/api/ciclos")
    item = r.json()[0]
    assert item["turma"] == {"id": str(turma.id), "name": turma.name}
    assert item["disciplina"] == {"id": str(disciplina.id), "name": disciplina.name}
    assert item["n_aulas_previstas"] == ciclo.n_aulas_previstas


def test_encerrar_ciclo_de_outro_professor_da_404(client_factory, db, ciclo):
    """Lacuna pré-existente, achada de passagem na revisão da Task 12: as
    três rotas que dependem de posse de ciclo (encerrar, relatório do ciclo,
    importar QTI) compartilham `ciclo_do_professor`
    (app/ciclos/service.py), mas só as duas últimas tinham teste de 404 para
    ciclo alheio."""
    make_user(db, "outro-professor-encerrar")
    outro = client_factory()
    login(outro, "outro-professor-encerrar")
    r = outro.post(f"/api/ciclos/{ciclo.id}/encerrar")
    assert r.status_code == 404
