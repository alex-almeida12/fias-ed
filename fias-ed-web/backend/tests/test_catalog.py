import uuid

import pytest

from app.catalog.names import name_key
from app.models import AcessoAdmin, Escola, Turma
from tests.helpers import login, make_user


@pytest.mark.parametrize("raw,key", [("  Escola  São José ", "escola sao jose"), ("ÁGUA", "agua")])
def test_name_key(raw, key):
    assert name_key(raw) == key


def _escola(client, name="Escola São José", municipality="Mossoró", **extra):
    return client.post("/api/escolas", json={"name": name, "municipality": municipality, **extra})


def test_create_and_list_escolas(client, db):
    make_user(db, "ana")
    login(client, "ana")
    r = _escola(client, region="Nordeste")
    assert r.status_code == 201
    assert r.json()["name"] == "Escola São José" and r.json()["region"] == "Nordeste"
    assert [e["name"] for e in client.get("/api/escolas").json()] == ["Escola São José"]


def test_escola_is_shared_between_professors(client_factory, db):
    make_user(db, "ana")
    make_user(db, "bia")
    a, b = client_factory(), client_factory()
    login(a, "ana")
    login(b, "bia")
    _escola(a)
    assert len(b.get("/api/escolas").json()) == 1


def test_duplicate_escola_detected(client, db):
    make_user(db, "ana")
    login(client, "ana")
    first = _escola(client).json()
    r = _escola(client, name="escola  sao jose", municipality="MOSSORÓ")
    assert r.status_code == 409 and r.json()["error_code"] == "ESCOLA_DUPLICADA"
    assert r.json()["duplicatas"][0]["id"] == first["id"]
    assert _escola(client, name="Escola São José", municipality="Natal").status_code == 201
    assert _escola(client, name="escola sao jose", confirmar_nova=True).status_code == 201


def test_turma_requires_valid_escola(client, db):
    make_user(db, "ana")
    login(client, "ana")
    r = client.post("/api/turmas", json={"name": "9º Ano B"})
    assert r.status_code == 422 and "escola_id" in r.json()["fields"]
    r = client.post("/api/turmas", json={"name": "9º Ano B", "escola_id": str(uuid.uuid4())})
    assert r.status_code == 422 and r.json()["error_code"] == "ESCOLA_INVALIDA"


def test_turmas_and_disciplinas_are_private(client_factory, db):
    make_user(db, "ana")
    make_user(db, "bia")
    a, b = client_factory(), client_factory()
    login(a, "ana")
    login(b, "bia")
    escola = _escola(a).json()
    t = a.post("/api/turmas", json={"name": "9º Ano B", "escola_id": escola["id"], "school_year": 2026})
    assert t.status_code == 201 and t.json()["escola"]["id"] == escola["id"]
    assert a.post("/api/disciplinas", json={"name": "Matemática"}).status_code == 201
    assert len(a.get("/api/turmas").json()) == 1 and len(a.get("/api/disciplinas").json()) == 1
    assert b.get("/api/turmas").json() == [] and b.get("/api/disciplinas").json() == []


@pytest.mark.parametrize("name", ["'; DROP TABLE turma; --", "<script>alert(1)</script>"])
def test_hostile_names_stored_literally(client, db, name):
    make_user(db, "ana")
    login(client, "ana")
    escola = _escola(client).json()
    r = client.post("/api/turmas", json={"name": name, "escola_id": escola["id"]})
    assert r.status_code == 201 and r.json()["name"] == name
    assert client.get("/api/turmas").json()[0]["name"] == name


def test_admin_edits_and_merges_escolas(client_factory, db):
    make_user(db, "admin", role="ADMIN_LOCAL")
    make_user(db, "ana")
    admin, ana = client_factory(), client_factory()
    login(admin, "admin")
    login(ana, "ana")
    keep = _escola(ana).json()
    dup = _escola(ana, name="E. São José", municipality="Mossoró").json()
    turma = ana.post("/api/turmas", json={"name": "8º A", "escola_id": dup["id"]}).json()
    r = admin.patch(f"/api/admin/escolas/{keep['id']}", json={"municipality": "Mossoró/RN"})
    assert r.status_code == 200 and r.json()["municipality"] == "Mossoró/RN"
    r = admin.post(f"/api/admin/escolas/{dup['id']}/juntar", json={"destino_id": keep["id"]})
    assert r.status_code == 200
    assert db.get(Turma, uuid.UUID(turma["id"])).escola_id == uuid.UUID(keep["id"])
    assert db.get(Escola, uuid.UUID(dup["id"])).deleted_at is not None
    assert [e["id"] for e in ana.get("/api/escolas").json()] == [keep["id"]]
    assert ana.patch(f"/api/admin/escolas/{keep['id']}", json={"name": "X"}).status_code == 403


def test_merge_into_itself_rejected(client, db):
    make_user(db, "admin", role="ADMIN_LOCAL")
    login(client, "admin")
    e = _escola(client).json()
    r = client.post(f"/api/admin/escolas/{e['id']}/juntar", json={"destino_id": e["id"]})
    assert r.status_code == 422 and r.json()["error_code"] == "JUNCAO_INVALIDA"


def test_admin_acting_as_creates_turma_for_professor(client, db):
    admin = make_user(db, "admin", role="ADMIN_LOCAL")
    prof = make_user(db, "ana")
    login(client, "admin")
    client.post("/api/admin/agir-como", json={"professor_id": str(prof.id)})
    escola = _escola(client).json()
    t = client.post("/api/turmas", json={"name": "7º C", "escola_id": escola["id"]}).json()
    assert db.get(Turma, uuid.UUID(t["id"])).professor_id == prof.id
    actions = {(r.resource, r.action) for r in db.query(AcessoAdmin).filter_by(admin_id=admin.id)}
    assert ("turma", "create") in actions
