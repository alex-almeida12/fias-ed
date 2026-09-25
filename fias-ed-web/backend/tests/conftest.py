import os
import uuid
from datetime import date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.ciclos.service import posicao_no_ciclo
from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.main import create_app
from app.ml.protocols import SegmentoASR
from app.models import Audio, Aula, Base, Ciclo, ColetaQTI, Disciplina, Escola, ResultadoQTI, Turma
from app.transcricao.service import criar_transcricao, falante_provisorio, gravar_segmentos
from tests.audio_fixtures import VOZ_A, VOZ_B, make_fala
from tests.helpers import classificar_para_triangulacao, make_aula, make_user

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
def professor(db):
    return make_user(db, "professora-ciclo")


@pytest.fixture
def turma(db, professor):
    escola = Escola(name="Escola Teste", name_key="escola teste")
    db.add(escola)
    db.flush()
    turma = Turma(escola_id=escola.id, professor_id=professor.id, name="9º Ano B")
    db.add(turma)
    db.commit()
    return turma


@pytest.fixture
def disciplina(db, professor):
    disciplina = Disciplina(professor_id=professor.id, name="Matemática")
    db.add(disciplina)
    db.commit()
    return disciplina


@pytest.fixture
def ciclo(db, turma, disciplina, professor):
    c = Ciclo(turma_id=turma.id, disciplina_id=disciplina.id, professor_id=professor.id,
              n_aulas_previstas=8, iniciado_em=date(2026, 3, 1))
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def aula_em(db, professor):
    """Grava uma aula dentro de um ciclo dado, na data indicada. Aceita tanto o objeto
    Ciclo quanto o id (str/UUID) devolvido pela API — os testes usam as duas formas."""
    def _aula_em(ciclo_ou_id, lesson_date: str) -> Aula:
        c = ciclo_ou_id if isinstance(ciclo_ou_id, Ciclo) else db.get(Ciclo, uuid.UUID(str(ciclo_ou_id)))
        aula = Aula(professor_id=professor.id, turma_id=c.turma_id, disciplina_id=c.disciplina_id,
                    lesson_date=date.fromisoformat(lesson_date), status="DRAFT")
        db.add(aula)
        db.commit()
        db.refresh(aula)
        return aula
    return _aula_em


@pytest.fixture
def posicao(db):
    def _posicao(aula: Aula) -> str:
        # client.post(".../encerrar") grava em outra sessão; sem isso o identity map
        # desta sessão devolveria o Ciclo com o encerrado_em antigo (None).
        db.expire_all()
        return posicao_no_ciclo(db, aula)
    return _posicao


@pytest.fixture
def aula_avulsa(db):
    """Aula cuja turma/disciplina não têm ciclo nenhum associado."""
    prof = make_user(db, "professor-avulso")
    return make_aula(db, prof)


@pytest.fixture
def coleta_em(db):
    """Grava uma ColetaQTI viva no ciclo dado, na data indicada, com um
    ResultadoQTI associado — displayable=True e octantes plausíveis (escala
    1-5 do QTI-24), prontos para a triangulação ler.

    `displayable` e `created_at` são aceitos explicitamente para os testes que
    precisam forçar o caso "coleta existe mas não é exibível" ou empatar duas
    coletas no mesmo instante — `created_at` é `default=utcnow` do lado do
    Python (não do banco), então dá para sobrescrevê-lo na construção."""
    def _coleta_em(ciclo: Ciclo, coletado_em: str, *, displayable: bool = True,
                   created_at: datetime | None = None) -> ColetaQTI:
        kwargs = dict(ciclo_id=ciclo.id, coletado_em=date.fromisoformat(coletado_em),
                      origem="COLETA_NATIVA", response_count=12, displayable=displayable,
                      qti_config_version="1.0.0")
        if created_at is not None:
            kwargs["created_at"] = created_at
        coleta = ColetaQTI(**kwargs)
        db.add(coleta)
        db.flush()
        octantes = {"oc1": 4.0, "oc2": 3.5, "oc3": 2.0, "oc4": 4.5,
                    "oc5": 1.0, "oc6": 2.5, "oc7": 3.0, "oc8": 3.8}
        db.add(ResultadoQTI(coleta_id=coleta.id, octantes=octantes, agency=0.0, communion=0.0))
        db.commit()
        db.refresh(coleta)
        return coleta
    return _coleta_em


@pytest.fixture
def aula_classificada(db, monkeypatch, ciclo, aula_em):
    """Uma aula com transcrição, segmentos, ClassificacaoFIAS e IndicadorFIAS,
    pronta para triangular — mesmo molde de `aula_transcrita`. Vive no ciclo da
    fixture `ciclo`, mas por padrão nenhuma `coleta_em` é criada nele, então
    `coleta_vigente` ainda não acha nada para ela: serve aos testes de
    triangulação que não dependem de uma coleta QTI vigente. Um teste que peça
    `ciclo` junto desta fixture recebe o mesmo ciclo (fixtures são cacheadas por
    teste) e pode gravar ali uma coleta que `coleta_vigente` realmente escolha
    para esta aula."""
    aula = aula_em(ciclo, "2026-09-22")
    aula.status = "READY_FOR_FIAS"
    db.commit()
    classificar_para_triangulacao(db, aula, monkeypatch)
    db.refresh(aula)
    return aula


@pytest.fixture
def aula_classificada_em(db, monkeypatch, aula_em):
    """Como `aula_classificada`, mas com a data da aula escolhida pelo teste —
    necessário para exercitar `posicao_no_ciclo` (primeira/meio), que depende
    de quando cada aula do ciclo caiu, não só de que ela existe."""
    def _aula_classificada_em(ciclo_ou_id, lesson_date: str) -> Aula:
        aula = aula_em(ciclo_ou_id, lesson_date)
        aula.status = "READY_FOR_FIAS"
        db.commit()
        classificar_para_triangulacao(db, aula, monkeypatch)
        db.refresh(aula)
        return aula
    return _aula_classificada_em


@pytest.fixture
def aula_avulsa_classificada(db, monkeypatch, aula_avulsa):
    """O mesmo molde de `aula_classificada`, mas fora de qualquer ciclo —
    `posicao_no_ciclo` tem de devolver "fora" para ela."""
    aula_avulsa.status = "READY_FOR_FIAS"
    db.commit()
    classificar_para_triangulacao(db, aula_avulsa, monkeypatch)
    db.refresh(aula_avulsa)
    return aula_avulsa


@pytest.fixture
def aula_transcrita(db):
    """Simula o estado em que handle_transcribe (Task 5) deixa a aula: um
    falante provisório (role=UNASSIGNED, diarization_label="pendente") ao qual
    todos os segmentos apontam, status TRANSCRIBED — a transcrição terminou e o
    job de diarização está na fila, ainda sem ter começado. Compartilhado entre
    test_align.py (repontamento) e test_job_diarize.py (o job inteiro)."""
    prof = make_user(db, "carla")
    aula = make_aula(db, prof, status="TRANSCRIBED")
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
