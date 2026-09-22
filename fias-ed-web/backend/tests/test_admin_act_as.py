import uuid

from app.audit import audit, last_admin_change, record
from app.auth.deps import Actor
from app.models import AcessoAdmin, Professor, utcnow
from tests.helpers import login, make_user


def test_admin_starts_and_stops_acting_as(client, db):
    admin = make_user(db, "admin", role="ADMIN_LOCAL")
    prof = make_user(db, "ana")
    login(client, "admin")
    r = client.post("/api/admin/agir-como", json={"professor_id": str(prof.id)})
    assert r.status_code == 200
    assert r.json()["acting_as"] == {"id": str(prof.id), "display_name": "Ana"}
    assert client.get("/api/auth/me").json()["acting_as"]["id"] == str(prof.id)
    row = db.query(AcessoAdmin).one()
    assert (row.admin_id, row.professor_id, row.resource, row.action) == (admin.id, prof.id, "professor", "read")
    assert client.delete("/api/admin/agir-como").json()["acting_as"] is None
    assert client.get("/api/auth/me").json()["acting_as"] is None


def test_cannot_act_as_self_or_missing(client, db):
    admin = make_user(db, "admin", role="ADMIN_LOCAL")
    login(client, "admin")
    r = client.post("/api/admin/agir-como", json={"professor_id": str(admin.id)})
    assert r.status_code == 422 and r.json()["error_code"] == "AGIR_COMO_PROPRIA_CONTA"
    r = client.post("/api/admin/agir-como", json={"professor_id": str(uuid.uuid4())})
    assert r.status_code == 404 and r.json()["error_code"] == "CONTA_NAO_ENCONTRADA"


def test_can_act_as_inactive_professor(client, db):
    make_user(db, "admin", role="ADMIN_LOCAL")
    prof = make_user(db, "ana", active=False)
    login(client, "admin")
    assert client.post("/api/admin/agir-como", json={"professor_id": str(prof.id)}).status_code == 200


def test_professor_cannot_act_as(client, db):
    make_user(db, "ana")
    other = make_user(db, "bia")
    login(client, "ana")
    r = client.post("/api/admin/agir-como", json={"professor_id": str(other.id)})
    assert r.status_code == 403 and r.json()["error_code"] == "FORBIDDEN"


def test_acting_as_cleared_when_target_deleted(client, db):
    make_user(db, "admin", role="ADMIN_LOCAL")
    prof = make_user(db, "ana")
    login(client, "admin")
    client.post("/api/admin/agir-como", json={"professor_id": str(prof.id)})
    target = db.get(Professor, prof.id)
    target.deleted_at = utcnow()
    db.commit()
    assert client.get("/api/auth/me").json()["acting_as"] is None


def test_audit_is_noop_without_acting_as(db):
    admin = make_user(db, "admin", role="ADMIN_LOCAL")
    audit(db, Actor(user=admin, session=None, acting_as=None), "aula", uuid.uuid4(), "read")
    db.commit()
    assert db.query(AcessoAdmin).count() == 0


def test_last_admin_change_ignores_reads(db):
    admin = make_user(db, "admin", role="ADMIN_LOCAL")
    prof = make_user(db, "ana")
    aula_id = uuid.uuid4()
    record(db, admin_id=admin.id, professor_id=prof.id, resource="aula", resource_id=aula_id, action="read")
    db.commit()
    assert last_admin_change(db, aula_id) is None
    record(db, admin_id=admin.id, professor_id=prof.id, resource="aula", resource_id=aula_id, action="upload")
    db.commit()
    assert last_admin_change(db, aula_id) is not None
