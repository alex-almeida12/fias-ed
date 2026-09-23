import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.main import create_app
from app.ml.protocols import SegmentoASR
from app.models import Audio, Base
from app.transcricao.service import criar_transcricao, falante_provisorio, gravar_segmentos
from tests.audio_fixtures import VOZ_A, VOZ_B, make_fala
from tests.helpers import make_aula, make_user

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


@pytest.fixture
def aula_transcrita(db):
    """Simula o estado em que handle_transcribe (Task 5) deixa a aula: um
    falante provisório (role=UNASSIGNED, diarization_label="pendente") ao qual
    todos os segmentos apontam, status DIARIZING. Compartilhado entre
    test_align.py (repontamento) e test_job_diarize.py (o job inteiro)."""
    prof = make_user(db, "carla")
    aula = make_aula(db, prof, status="DIARIZING")
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1, duration_ms=9_000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True, derived_from_audio_id=None)
    db.add(audio)
    db.flush()
    transcricao = criar_transcricao(db, aula, audio, "fake-asr")
    provisorio = falante_provisorio(db, transcricao)
    segmentos = [SegmentoASR(0, 4_500, "professor explicando"),
                SegmentoASR(4_500, 9_000, "aluno perguntando")]
    gravar_segmentos(db, transcricao, segmentos, provisorio)
    db.commit()
    return aula


# ---- fala sintética para os testes de modelo real (marcador `lento`) ----------------

# Frases curtas e repetidas: o libflite lê com pronúncia inglesa, então o texto
# que o Whisper devolve não bate palavra por palavra com o que foi sintetizado —
# e não é isso que os testes checam. O que importa é que há fala de verdade no
# arquivo, com envelope e formantes, e não um tom puro que o VAD descarta.
_FRASE_A = "hoje a gente vai falar sobre o problema da aula passada"
_FRASE_B = "professor eu nao entendi a parte do meio dessa conta"


@pytest.fixture
def wav_fala(tmp_path):
    """Uma voz só, alguns segundos de fala contínua."""
    return make_fala(tmp_path / "fala.wav", [(_FRASE_A, VOZ_A)] * 3)


@pytest.fixture
def wav_duas_vozes(tmp_path):
    """Duas vozes alternando: é o mínimo para a diarização ter o que separar."""
    return make_fala(tmp_path / "duas-vozes.wav",
                     [(_FRASE_A, VOZ_A), (_FRASE_B, VOZ_B)] * 3)
