from app.jobs.worker import run_once
from app.models import AcessoAdmin, Aula
from tests.audio_fixtures import make_audio, upload
from tests.helpers import login, make_user


def test_admin_creates_and_processes_aula_for_professor(client_factory, db, tmp_path):
    admin_user = make_user(db, "admin", role="ADMIN_LOCAL")
    prof = make_user(db, "ana")
    admin, ana = client_factory(), client_factory()
    login(admin, "admin")
    login(ana, "ana")
    admin.post("/api/admin/agir-como", json={"professor_id": str(prof.id)})
    escola = admin.post("/api/escolas", json={"name": "Escola X"}).json()
    turma = admin.post("/api/turmas", json={"name": "6º A", "escola_id": escola["id"]}).json()
    disciplina = admin.post("/api/disciplinas", json={"name": "História"}).json()
    aula = admin.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                          "lesson_date": "2026-09-22"}).json()
    assert upload(admin, aula["id"], make_audio(tmp_path / "a.wav")).status_code == 201
    assert admin.post(f"/api/aulas/{aula['id']}/processar").status_code == 202
    run_once(db)

    assert db.query(Aula).one().professor_id == prof.id
    seen_by_prof = ana.get(f"/api/aulas/{aula['id']}").json()
    assert seen_by_prof["status"] == "AUDIO_VALIDATED"
    assert seen_by_prof["alterada_pelo_admin_em"] is not None
    actions = {r.action for r in db.query(AcessoAdmin).filter_by(admin_id=admin_user.id, resource="aula")}
    assert {"create", "upload", "process"} <= actions


def test_professor_own_actions_are_not_flagged(client, db, tmp_path):
    make_user(db, "ana")
    login(client, "ana")
    escola = client.post("/api/escolas", json={"name": "Escola Y"}).json()
    turma = client.post("/api/turmas", json={"name": "6º B", "escola_id": escola["id"]}).json()
    disciplina = client.post("/api/disciplinas", json={"name": "Artes"}).json()
    aula = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                           "lesson_date": "2026-09-22"}).json()
    assert client.get(f"/api/aulas/{aula['id']}").json()["alterada_pelo_admin_em"] is None
    assert db.query(AcessoAdmin).count() == 0
