import uuid

from app.audio.storage import store_root
from app.models import AcessoAdmin, Audio, Aula, Professor, Sessao
from tests.helpers import PASSWORD, login, make_aula, make_user


def _admin(client_factory, db):
    make_user(db, "admin", role="ADMIN_LOCAL")
    c = client_factory()
    login(c, "admin")
    return c


def test_create_account_with_provisional_password(client_factory, db):
    admin = _admin(client_factory, db)
    r = admin.post("/api/admin/contas", json={"username": "Ana", "display_name": "Ana Souza"})
    assert r.status_code == 201
    conta, senha = r.json()["conta"], r.json()["senha_provisoria"]
    assert conta["username"] == "ana" and conta["role"] == "PROFESSOR" and conta["must_change_password"]
    ana = client_factory()
    login(ana, "ana", senha)
    assert ana.get("/api/aulas").json()["error_code"] == "PASSWORD_CHANGE_REQUIRED"
    ana.post("/api/auth/password", json={"current_password": senha, "new_password": "minha-senha-nova-1"})
    ana.headers["X-CSRF-Token"] = ana.cookies["fias_csrf"]
    assert ana.get("/api/aulas").status_code == 200


def test_list_accounts(client_factory, db):
    admin = _admin(client_factory, db)
    make_user(db, "ana")
    names = [c["username"] for c in admin.get("/api/admin/contas").json()]
    assert set(names) == {"admin", "ana"}


def test_deactivate_and_reactivate(client_factory, db):
    admin = _admin(client_factory, db)
    admin_row = db.query(Professor).filter_by(username="admin").one()
    prof = make_user(db, "ana")
    ana = client_factory()
    login(ana, "ana")
    r = admin.patch(f"/api/admin/contas/{prof.id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    # P29: a sessão existente da conta desativada precisa ser derrubada (delete_all_sessions).
    assert ana.get("/api/auth/me").status_code == 401
    assert ana.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 401
    # P1: toda ação do admin sobre a conta de um professor fica registrada em acesso_admin.
    assert db.query(AcessoAdmin).filter_by(
        admin_id=admin_row.id, professor_id=prof.id, resource="professor", action="update").count() == 1
    assert admin.post("/api/admin/agir-como", json={"professor_id": str(prof.id)}).status_code == 200
    admin.delete("/api/admin/agir-como")
    admin.patch(f"/api/admin/contas/{prof.id}", json={"is_active": True})
    assert ana.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 200
    assert db.query(AcessoAdmin).filter_by(
        admin_id=admin_row.id, professor_id=prof.id, resource="professor", action="update").count() == 2


def test_cannot_deactivate_or_delete_own_account(client_factory, db):
    admin = _admin(client_factory, db)
    me = db.query(Professor).filter_by(username="admin").one()
    r = admin.patch(f"/api/admin/contas/{me.id}", json={"is_active": False})
    assert r.status_code == 409 and r.json()["error_code"] == "PROPRIA_CONTA"
    r = admin.request("DELETE", f"/api/admin/contas/{me.id}", json={"confirmar_username": "admin"})
    assert r.status_code == 409 and r.json()["error_code"] == "PROPRIA_CONTA"
    other = make_user(db, "admin2", role="ADMIN_LOCAL")
    r = admin.patch(f"/api/admin/contas/{other.id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    # Conta alvo é ADMIN_LOCAL, não PROFESSOR: nenhuma linha de acesso_admin é gravada (P1).
    assert db.query(AcessoAdmin).filter_by(professor_id=other.id).count() == 0


def test_reset_password(client_factory, db):
    admin = _admin(client_factory, db)
    admin_row = db.query(Professor).filter_by(username="admin").one()
    prof = make_user(db, "ana")
    ana = client_factory()
    login(ana, "ana")
    r = admin.post(f"/api/admin/contas/{prof.id}/senha-provisoria")
    senha = r.json()["senha_provisoria"]
    assert ana.get("/api/auth/me").status_code == 401
    fresh = client_factory()
    login(fresh, "ana", senha)
    assert fresh.get("/api/auth/me").json()["must_change_password"] is True
    assert db.query(AcessoAdmin).filter_by(
        admin_id=admin_row.id, professor_id=prof.id, resource="professor", action="update").count() == 1


def test_delete_account_requires_confirmation_and_removes_audio(client_factory, db):
    admin = _admin(client_factory, db)
    admin_row = db.query(Professor).filter_by(username="admin").one()
    prof = make_user(db, "ana")
    aula = make_aula(db, prof, status="AUDIO_VALIDATED")
    (store_root() / "original").mkdir(parents=True, exist_ok=True)
    (store_root() / "original" / "x.wav").write_bytes(b"x")
    db.add(Audio(aula_id=aula.id, original_filename="x.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/x.wav", mime_type="audio/wav", size_bytes=1, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.commit()
    r = admin.request("DELETE", f"/api/admin/contas/{prof.id}", json={"confirmar_username": "errado"})
    assert r.status_code == 422 and r.json()["error_code"] == "CONFIRMACAO_INVALIDA"
    r = admin.request("DELETE", f"/api/admin/contas/{prof.id}", json={"confirmar_username": "ana"})
    assert r.status_code == 204
    assert not (store_root() / "original" / "x.wav").exists()
    db.expire_all()
    assert db.get(Professor, prof.id).deleted_at is not None
    assert db.get(Aula, aula.id).deleted_at is not None
    assert db.query(Sessao).filter_by(professor_id=prof.id).count() == 0
    assert "ana" not in [c["username"] for c in admin.get("/api/admin/contas").json()]
    assert db.query(AcessoAdmin).filter_by(
        admin_id=admin_row.id, professor_id=prof.id, resource="professor", action="delete").count() == 1


def test_cannot_delete_self(client_factory, db):
    admin = _admin(client_factory, db)
    me = db.query(Professor).filter_by(username="admin").one()
    r = admin.request("DELETE", f"/api/admin/contas/{me.id}", json={"confirmar_username": "admin"})
    assert r.status_code == 409 and r.json()["error_code"] == "PROPRIA_CONTA"


def test_admin_lists_all_aulas_with_filter(client_factory, db):
    admin = _admin(client_factory, db)
    ana, bia = make_user(db, "ana"), make_user(db, "bia")
    make_aula(db, ana)
    make_aula(db, bia)
    rows = admin.get("/api/admin/aulas").json()
    assert {r["professor"]["display_name"] for r in rows} == {"Ana", "Bia"}
    rows = admin.get(f"/api/admin/aulas?professor_id={ana.id}").json()
    assert [r["professor"]["id"] for r in rows] == [str(ana.id)]
    assert db.query(AcessoAdmin).filter_by(resource="aula", action="read").count() == 2


def test_professor_cannot_use_admin_routes(client, db):
    prof = make_user(db, "ana")
    login(client, "ana")
    assert client.get("/api/admin/contas").status_code == 403
    assert client.get("/api/admin/aulas").status_code == 403
    assert client.post(f"/api/admin/contas/{prof.id}/senha-provisoria").status_code == 403
