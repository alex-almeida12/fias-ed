import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.main import create_app
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


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


@pytest.fixture(scope="session")
def migrator_engine():
    command.upgrade(alembic_config(), "head")
    engine = create_engine(os.environ["MIGRATOR_DATABASE_URL"])
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(migrator_engine):
    yield
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with migrator_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))  # nosec B608 - nomes vêm do metadata


@pytest.fixture
def db():
    with SessionLocal(bind=get_engine()) as session:
        yield session
