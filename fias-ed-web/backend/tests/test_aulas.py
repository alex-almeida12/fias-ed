import uuid

from app.audio.storage import abs_path, ensure_dirs, store_root
from app.aulas.service import detach_audio
from app.models import Aula, Audio, AudioUpload, Job
from tests.helpers import login, make_aula, make_user


def _catalog(client, escola_name="Escola A"):
    escola = client.post("/api/escolas", json={"name": escola_name}).json()
    turma = client.post("/api/turmas", json={"name": "9º B", "escola_id": escola["id"]}).json()
    disciplina = client.post("/api/disciplinas", json={"name": "Ciências"}).json()
    return turma, disciplina


def test_create_list_and_get_aula(client, db):
    make_user(db, "ana")
    login(client, "ana")
    turma, disciplina = _catalog(client)
    r = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                        "lesson_date": "2026-09-22", "note": "Aula de revisão"})
    assert r.status_code == 201
    aula = r.json()
    assert aula["status"] == "DRAFT" and aula["turma"]["name"] == "9º B" and aula["note"] == "Aula de revisão"
    assert aula["audio"] is None and aula["upload_pendente"] is None and aula["job_ativo"] is False
    assert aula["alterada_pelo_admin_em"] is None and aula["error_message"] is None
    assert [a["id"] for a in client.get("/api/aulas").json()] == [aula["id"]]
    assert client.get(f"/api/aulas/{aula['id']}").json()["id"] == aula["id"]


def test_cannot_use_other_professor_turma(client_factory, db):
    make_user(db, "ana")
    make_user(db, "bia")
    a, b = client_factory(), client_factory()
    login(a, "ana")
    login(b, "bia")
    turma, disciplina = _catalog(a)
    # escola_name diferente: o catálogo de escolas é global (dedup entre professores, Task 6),
    # então reusar "Escola A" aqui bateria em ESCOLA_DUPLICADA em vez de testar TURMA_INVALIDA.
    _, disc_b = _catalog(b, "Escola B")
    r = b.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disc_b["id"], "lesson_date": "2026-09-22"})
    assert r.status_code == 422 and r.json()["error_code"] == "TURMA_INVALIDA"


def test_other_professor_aula_is_404(client, db):
    make_user(db, "ana")
    bia = make_user(db, "bia")
    aula = make_aula(db, bia)
    login(client, "ana")
    r = client.get(f"/api/aulas/{aula.id}")
    assert r.status_code == 404 and r.json()["error_code"] == "AULA_NAO_ENCONTRADA"
    assert client.delete(f"/api/aulas/{aula.id}").status_code == 404
    assert client.get("/api/aulas").json() == []


def test_note_limit(client, db):
    make_user(db, "ana")
    login(client, "ana")
    turma, disciplina = _catalog(client)
    r = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                        "lesson_date": "2026-09-22", "note": "x" * 2001})
    assert r.status_code == 422


def test_error_message_in_payload(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="ERROR")
    aula.error_code = "AUDIO_TOO_SHORT"
    db.commit()
    login(client, "ana")
    body = client.get(f"/api/aulas/{aula.id}").json()
    assert body["error_message"].startswith("O áudio tem menos de 1 minuto")


def test_delete_removes_files_and_hides_aula(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_VALIDATED")
    login(client, "ana")
    ensure_dirs()
    for rel in ("original/a.wav", "original/b.wav"):
        abs_path(rel).write_bytes(b"RIFF")
    db.add(Audio(aula_id=aula.id, original_filename="a.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/a.wav", mime_type="audio/wav", size_bytes=4, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.add(AudioUpload(aula_id=aula.id, original_filename="b.wav", internal_filename=f"{uuid.uuid4()}.wav",
                       path="original/b.wav", size_bytes=4, sha256="0" * 64))
    db.commit()
    assert client.delete(f"/api/aulas/{aula.id}").status_code == 204
    assert not (store_root() / "original" / "a.wav").exists()
    assert not (store_root() / "original" / "b.wav").exists()
    db.expire_all()
    assert db.get(Aula, aula.id).deleted_at is not None
    assert db.query(AudioUpload).count() == 0
    assert client.get(f"/api/aulas/{aula.id}").status_code == 404


def test_delete_blocked_while_job_active(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    db.add(Job(type="validate_audio", aula_id=aula.id, status="queued"))
    db.commit()
    login(client, "ana")
    r = client.delete(f"/api/aulas/{aula.id}")
    assert r.status_code == 409 and r.json()["error_code"] == "AULA_BUSY"


def test_storage_rejects_paths_outside_root():
    import pytest
    with pytest.raises(ValueError):
        abs_path("../../etc/passwd")


def test_detach_audio_returns_paths_without_soft_deleting_aula(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_VALIDATED")
    ensure_dirs()
    db.add(Audio(aula_id=aula.id, original_filename="c.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/c.wav", mime_type="audio/wav", size_bytes=4, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.add(AudioUpload(aula_id=aula.id, original_filename="d.wav", internal_filename=f"{uuid.uuid4()}.wav",
                       path="original/d.wav", size_bytes=4, sha256="0" * 64))
    db.commit()

    paths = detach_audio(db, aula)
    db.commit()

    assert sorted(paths) == ["original/c.wav", "original/d.wav"]
    db.expire_all()
    assert db.query(AudioUpload).count() == 0
    audio = db.query(Audio).filter(Audio.aula_id == aula.id).one()
    assert audio.deleted_at is not None
    assert db.get(Aula, aula.id).deleted_at is None
