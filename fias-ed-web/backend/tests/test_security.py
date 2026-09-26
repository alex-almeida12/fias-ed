"""Testes do prompt §76 que valem para todas as rotas."""
import uuid

import pytest

from app.main import create_app
from tests.helpers import login, make_user

# As três rotas de app/publico/routes.py são as únicas portas do sistema sem
# autenticação (§10 da spec) — não vivem sob /api de propósito (main.py). Cada
# entrada aqui é uma decisão de segurança explícita: nenhuma outra rota deve
# ser acrescentada a este conjunto sem a mesma revisão que estas três tiveram.
PUBLIC = {("POST", "/api/auth/login"), ("GET", "/api/health"),
         ("GET", "/publico/qti/{token}"), ("POST", "/publico/qti/{token}/consentir"),
         ("POST", "/publico/qti/{token}/responder")}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _routes():
    # app.routes é uma lista de _IncludedRouter (wrappers internos do FastAPI 0.141) e não expõe
    # method/path diretamente nem o prefixo "/api" nos objetos aninhados. app.openapi() é a API
    # pública e estável que já resolve tudo isso (funciona mesmo com openapi_url=None).
    #
    # /publico entra aqui também: são as únicas rotas do sistema fora de /api, e se ficassem de
    # fora desta coleta nunca seriam varridas por este teste nem por PUBLIC — a isenção delas
    # deixaria de ser uma decisão registrada e passaria a ser um buraco silencioso.
    schema = create_app().openapi()
    for path, operations in schema["paths"].items():
        if not (path.startswith("/api") or path.startswith("/publico")):
            continue
        for method in operations:
            if method in _HTTP_METHODS:
                yield method.upper(), path


def _url(path: str) -> str:
    for name in ("aula_id", "escola_id", "conta_id"):
        path = path.replace("{" + name + "}", str(uuid.uuid4()))
    return path


ALL = sorted(set(_routes()))


def test_routes_are_actually_collected():
    """Guarda contra _routes() voltar a coletar 0 rotas silenciosamente (achado da revisão da Task 11)."""
    assert len(ALL) >= 25, len(ALL)
    for expected in (("POST", "/api/auth/login"), ("GET", "/api/health"), ("GET", "/api/aulas"),
                      ("POST", "/api/aulas"), ("GET", "/api/admin/contas"),
                      ("DELETE", "/api/aulas/{aula_id}")):
        assert expected in ALL, expected


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
