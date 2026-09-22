"""Testes do prompt §76 que valem para todas as rotas."""
import uuid

import pytest
from fastapi.routing import APIRoute

from app.main import create_app
from tests.helpers import login, make_user

PUBLIC = {("POST", "/api/auth/login"), ("GET", "/api/health")}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _routes():
    for route in create_app().routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield method, route.path


def _url(path: str) -> str:
    for name in ("aula_id", "escola_id", "conta_id"):
        path = path.replace("{" + name + "}", str(uuid.uuid4()))
    return path


ALL = sorted(set(_routes()))


@pytest.mark.parametrize("method,path", [r for r in ALL if r not in PUBLIC])
def test_every_route_requires_authentication(client, method, path):
    r = client.request(method, _url(path))
    assert r.status_code == 401, (method, path, r.status_code)
    assert r.json()["error_code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("method,path", [r for r in ALL if r[0] in MUTATING and r not in PUBLIC])
def test_every_mutation_requires_csrf(client, db, method, path):
    make_user(db, "admin", role="ADMIN_LOCAL")
    login(client, "admin")
    del client.headers["X-CSRF-Token"]
    r = client.request(method, _url(path))
    assert r.status_code == 403 and r.json()["error_code"] == "CSRF_INVALID", (method, path)


@pytest.mark.parametrize("method,path", [r for r in ALL if r[1].startswith("/api/admin")])
def test_admin_routes_forbidden_for_professor(client, db, method, path):
    make_user(db, "ana")
    login(client, "ana")
    r = client.request(method, _url(path), json={})
    assert r.status_code == 403, (method, path, r.status_code)


def test_sql_injection_in_login(client, db):
    make_user(db, "ana")
    r = client.post("/api/auth/login", json={"username": "ana' OR '1'='1", "password": "' OR '1'='1"})
    assert r.status_code == 401


def test_sql_injection_in_filter_is_rejected(client, db):
    make_user(db, "admin", role="ADMIN_LOCAL")
    login(client, "admin")
    r = client.get("/api/admin/aulas", params={"professor_id": "1 OR 1=1"})
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION"


def test_oversized_json_fields_rejected(client, db):
    make_user(db, "ana")
    login(client, "ana")
    assert client.post("/api/disciplinas", json={"name": "x" * 121}).status_code == 422
    assert client.post("/api/auth/login", json={"username": "x" * 65, "password": "y"}).status_code == 422
