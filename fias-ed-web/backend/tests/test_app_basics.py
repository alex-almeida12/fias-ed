import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import AppError
from app.core.logging import log_event
from app.main import create_app


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_unknown_route_returns_error_body(client):
    r = client.get("/api/nao-existe")
    assert r.status_code == 404
    assert r.json()["error_code"] == "NOT_FOUND"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_disabled(client, path):
    assert client.get(path).status_code == 404


def test_unhandled_error_hides_details():
    app = create_app()

    @app.get("/api/_boom")
    def boom():
        raise RuntimeError("segredo interno")

    c = TestClient(app, raise_server_exceptions=False, base_url="https://testserver")
    r = c.get("/api/_boom")
    assert r.status_code == 500
    assert r.json() == {"error_code": "INTERNAL", "message": "Algo deu errado. Tente novamente."}
    assert "segredo" not in r.text


def test_app_error_with_extra_fields():
    app = create_app()

    @app.get("/api/_conflito")
    def conflito():
        raise AppError(409, "ESCOLA_DUPLICADA", "Já existe.", duplicatas=[{"id": "x"}])

    r = TestClient(app, base_url="https://testserver").get("/api/_conflito")
    assert r.status_code == 409
    assert r.json() == {"error_code": "ESCOLA_DUPLICADA", "message": "Já existe.",
                        "duplicatas": [{"id": "x"}]}


def test_validation_error_format():
    app = create_app()

    class Body(BaseModel):
        name: str

    @app.post("/api/_eco")
    def eco(body: Body):
        return body

    r = TestClient(app, base_url="https://testserver").post("/api/_eco", json={})
    assert r.status_code == 422
    assert r.json()["error_code"] == "VALIDATION"
    assert r.json()["fields"] == ["name"]


def test_log_event_rejects_unknown_fields():
    with pytest.raises(ValueError):
        log_event("login", password="segredo")


def test_log_event_writes_json(caplog):
    caplog.set_level(logging.INFO, logger="fias_ed")
    log_event("login", professor_id="abc", status="ok")
    record = caplog.records[-1]
    assert record.fields == {"event": "login", "professor_id": "abc", "status": "ok"}
    from app.core.logging import JsonFormatter
    assert json.loads(JsonFormatter().format(record))["event"] == "login"


def test_shared_engine_importable():
    from fias_ed_engine.rules import load_rules
    assert load_rules("fias_rules")["rules_version"]
