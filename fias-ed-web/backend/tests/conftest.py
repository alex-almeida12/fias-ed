import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def app_instance(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIO_STORE", str(tmp_path / "audio"))
    get_settings.cache_clear()
    yield create_app()
    get_settings.cache_clear()


@pytest.fixture
def client_factory(app_instance):
    clients = []

    def make() -> TestClient:
        c = TestClient(app_instance, base_url="https://testserver")
        c.__enter__()
        clients.append(c)
        return c

    yield make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(client_factory):
    return client_factory()
