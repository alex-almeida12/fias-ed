import json
import logging

from app.jobs.worker import run_once
from tests.audio_fixtures import make_audio, upload
from tests.helpers import PASSWORD, login, make_user


def test_full_flow_logs_no_sensitive_data(client, db, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="fias_ed")
    make_user(db, "professora.segredo")
    login(client, "professora.segredo")
    escola = client.post("/api/escolas", json={"name": "Escola Confidencial"}).json()
    turma = client.post("/api/turmas", json={"name": "Turma Sigilosa", "escola_id": escola["id"]}).json()
    disciplina = client.post("/api/disciplinas", json={"name": "Disciplina Reservada"}).json()
    aula = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                           "lesson_date": "2026-09-22", "note": "Observação privada"}).json()
    upload(client, aula["id"], make_audio(tmp_path / "gravacao-intima.wav"))
    client.post(f"/api/aulas/{aula['id']}/processar")
    run_once(db)
    client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "outra-senha-longa-9"})

    everything = caplog.text + json.dumps([getattr(r, "fields", {}) for r in caplog.records], ensure_ascii=False)
    for secret in (PASSWORD, "outra-senha-longa-9", "professora.segredo", "Professora.Segredo",
                   "Escola Confidencial", "Turma Sigilosa", "Disciplina Reservada", "Observação privada",
                   "gravacao-intima", client.cookies.get("fias_session"), client.cookies.get("fias_csrf")):
        assert secret not in everything, secret
    assert any(getattr(r, "fields", {}).get("event") == "audio_validated" for r in caplog.records)
