# FIAS-ED Web — W1 Fundação: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subir o FIAS-ED Web no PC do pesquisador (Docker Compose) com login seguro, admin que age em nome dos professores, cadastro de aulas, upload e validação do áudio até `AUDIO_VALIDATED`, e as telas Home, Dashboard, Nova Aula, Aula e Admin com a identidade visual do shared.

**Architecture:** Quatro containers numa rede interna: `web` (nginx não-root servindo o React compilado e repassando `/api`), `api` (FastAPI + SQLAlchemy síncrono, psycopg 3), `worker` (mesma imagem, consome a tabela `job` com `FOR UPDATE SKIP LOCKED`) e `db` (PostgreSQL 16). Sessão no servidor com cookie opaco + token CSRF; mesma origem, sem CORS. O frontend é React + TypeScript + Vite com componentes próprios sobre `tokens.css` do shared.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2, Alembic, psycopg 3, argon2-cffi, ffprobe (FFmpeg); PostgreSQL 16; React, TypeScript, Vite, React Router, Vitest, Testing Library; nginx (imagem `nginxinc/nginx-unprivileged`); Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-22-fias-ed-web-w1-fundacao-design.md` (requisitos originais em `docs/PROMPT_MESTRE.md`).

## Global Constraints

- Tudo em `fias-ed-web/`; não alterar `artigos selecionados\`, `avalie-seu-professor\` nem arquivos de `fias-ed-shared/` (W1 não muda o shared, exceto `docs/PRIVACY.md` na Task 16).
- Única porta publicada: `127.0.0.1:8080`. Banco sem porta publicada. Nenhum container `privileged`, todos não-root, todos com healthcheck. Nenhuma pasta do Windows montada no compose de produção.
- Banco: API e worker conectam como `fias_ed_app` (só `SELECT, INSERT, UPDATE, DELETE`); Alembic roda como `fias_ed_migrator`. Senhas só no `.env` (ignorado); versionar só `.env.example`.
- Sem SQL concatenado com dados; sem `shell=True`/`os.system`; subprocess sempre com lista de argumentos.
- Senha: mínimo 12 caracteres; hash Argon2id (`argon2-cffi`, `PasswordHasher()` padrão).
- Sessão: cookie `fias_session` (`HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`), banco guarda só SHA-256 do token; 2 h de inatividade, 12 h absolutas. CSRF: cookie `fias_csrf` + cabeçalho `X-CSRF-Token` em POST/PUT/PATCH/DELETE. Bloqueio: 5 falhas → 15 min. Mensagem única de falha: "Usuário ou senha incorretos."
- Erros da API sempre `{"error_code": "...", "message": "..."}` (+ campos extras quando indicado), mensagens em português, nunca stack trace. `/docs`, `/redoc`, `/openapi.json` desativados.
- Logs: só pelo helper `log_event` com a lista fechada de campos (`ALLOWED_FIELDS`); nunca senha, token, cookie, nomes (professor, turma, arquivo), texto de transcrição, respostas QTI.
- Recurso de outro professor → 404. Rotas de admin chamadas por PROFESSOR → 403.
- "Professor efetivo" = o próprio usuário, ou o professor escolhido pelo ADMIN_LOCAL em "agir como" (`sessao.acting_as_professor_id`). Toda leitura/alteração do admin agindo como professor grava `acesso_admin`.
- Áudio: formatos mp3, wav, m4a, aac, flac; até 1,5 GB (`MAX_UPLOAD_BYTES=1610612736`); duração 60 s a 9000 s; original nunca modificado (arquivo `0o440` em `audio_store/original/<uuid>.<ext>`); caminho sempre derivado do UUID.
- Frontend: sem `dangerouslySetInnerHTML` e sem atributo `style` (CSP `style-src 'self'`), regra de lint; sem biblioteca de componentes; sem fontes de CDN; textos de interface em pt-BR com o vocabulário do prompt (nunca "avaliação", "nota", "desempenho").
- Toda mensagem de commit termina com a linha `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

## Decisões do plano (divergências do spec resolvidas contra os schemas do shared)

1. **Escola obrigatória na turma.** `turma.schema.json` exige `escola_id`; ao criar uma turma o professor escolhe ou cria a escola (o spec dizia "escola opcional"). O banco nunca diverge do schema.
2. **`processamento` sem linhas em W1.** O schema exige `asr_model`, hashes de modelos etc., que só existem em W2. A tabela é criada em W1 (compatível com o schema), mas a primeira linha nasce no W2.
3. **Upload em preparo.** `audio.schema.json` exige duração, canais, sample rate e MIME, conhecidos só após a validação. O upload fica na tabela interna `audio_upload`; a linha de `audio` é criada pelo job de validação.
4. **Mensagens de erro geradas no backend** (`error_message` no detalhe da aula e no corpo dos erros), porque os limites vêm da configuração; o frontend mostra `message`/`error_message` e mapeia só os status.
5. **Username excluído fica reservado** (índice único simples em `professor.username`).
6. **"Extensão falsa"** nos testes = um áudio FLAC real renomeado para `.mp3` → `AUDIO_FORMAT_MISMATCH`. Arquivo que não é áudio → `AUDIO_CORRUPTED`.

## Como rodar (referência para todas as tasks)

Todos os comandos a partir de `fias-ed-web/` (Git Bash):

- Testes do backend: `docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q`
  (um teste: `... run --rm api-test pytest -q tests/test_x.py::test_y`; `--build` só quando mudar dependências ou o Dockerfile).
- Qualquer comando no container de teste: `docker compose -f docker-compose.test.yml run --rm api-test <comando>`.
- Testes do frontend: `cd frontend && npm test` (Vitest em modo run) e `npm run lint`.
- Sistema completo: `docker compose up -d --build` → `http://localhost:8080`.

## Mapa de arquivos

```
.dockerignore                               (raiz do monorepo) exclui .venv, node_modules, .git…
fias-ed-web/
  .gitattributes  .gitignore  .env.example  docker-compose.yml  docker-compose.test.yml  README.md
  deploy/db-init/01-roles.sh               cria fias_ed_migrator e fias_ed_app
  deploy/nginx.conf                         proxy /api, SPA, cabeçalhos de segurança
  deploy/web.Dockerfile                     build do React + nginx não-root
  scripts/smoke.py                          teste de aceitação de ponta a ponta (stdlib)
  backend/
    Dockerfile  pyproject.toml  alembic.ini
    alembic/env.py  alembic/script.py.mako  alembic/versions/0001_w1_inicial.py (gerado)
    app/__init__.py                         APP_VERSION
    app/main.py                             create_app()
    app/core/config.py                      Settings, get_settings()
    app/core/db.py                          get_engine(), SessionLocal, get_db()
    app/core/errors.py                      AppError, handlers
    app/core/logging.py                     log_event, ALLOWED_FIELDS
    app/core/messages.py                    error_message(code)
    app/models.py                           todas as tabelas
    app/auth/passwords.py                   Argon2id
    app/auth/sessions.py                    sessão + CSRF
    app/auth/deps.py                        Actor, current_actor…
    app/auth/routes.py                      login/logout/me/password, me_payload
    app/users/service.py                    create_professor, validações
    app/audit.py                            acesso_admin
    app/admin/routes.py                     agir-como, contas, aulas de todos
    app/catalog/names.py                    name_key
    app/catalog/routes.py                   escolas, turmas, disciplinas (+ admin escolas)
    app/aulas/service.py                    get_owned_aula, aula_payload, has_active_job
    app/aulas/routes.py                     CRUD de aula, processar
    app/audio/storage.py                    caminhos seguros, exclusão
    app/audio/routes.py                     upload, reprodução
    app/audio/probe.py                      ffprobe
    app/audio/validation.py                 regras de formato/duração
    app/jobs/queue.py                       enqueue/claim/recover/fail
    app/jobs/handlers.py                    validate_audio
    app/jobs/worker.py                      loop do worker
    app/cli.py                              create-admin
    tests/…                                 um arquivo por área
  frontend/
    vite.config.ts  eslint.config.js  index.html  package.json
    src/main.tsx  src/test-setup.ts
    src/design/{index.css,fonts.css,base.css,components.css}
    src/design/components/{Button,Field,Dialog,Banner,EmptyState,StatusBadge}.tsx
    src/api/{client.ts,types.ts}
    src/app/{App.tsx,AuthContext.tsx,Layout.tsx,RequireAuth.tsx,status.ts}
    src/pages/{Home,TrocarSenha,Dashboard,NovaAula,Aula}.tsx
    src/pages/admin/{Contas,Aulas,Escolas}.tsx
    src/**/*.test.tsx
```

---

### Task 1: Esqueleto do backend, infraestrutura de testes e erros/logs

**Files:**
- Create: `.dockerignore` (raiz do monorepo)
- Create: `fias-ed-web/.gitattributes`, `fias-ed-web/.gitignore`, `fias-ed-web/.env.example`
- Create: `fias-ed-web/deploy/db-init/01-roles.sh`
- Create: `fias-ed-web/docker-compose.test.yml`
- Create: `fias-ed-web/backend/Dockerfile`, `fias-ed-web/backend/pyproject.toml`
- Create: `fias-ed-web/backend/app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/core/db.py`, `app/core/errors.py`, `app/core/logging.py`
- Test: `fias-ed-web/backend/tests/__init__.py`, `tests/conftest.py`, `tests/test_app_basics.py`

**Interfaces:**
- Produces: `app.core.config.get_settings() -> Settings` (campos listados abaixo, `lru_cache`, limpar com `get_settings.cache_clear()`); `app.core.db.get_engine()`, `SessionLocal`, `get_db()`; `app.core.errors.AppError(status: int, code: str, message: str, **extra)`; `app.core.logging.log_event(event: str, level=logging.INFO, **fields)` (levanta `ValueError` para campo fora de `ALLOWED_FIELDS`), `configure_logging()`; `app.main.create_app() -> FastAPI`; `app.APP_VERSION = "0.1.0"`.
- Produces (testes): fixtures `app_instance`, `client_factory`, `client` (TestClient com `base_url="https://testserver"`).

- [ ] **Step 1: Arquivos de infraestrutura**

`.dockerignore` (raiz do monorepo — o contexto de build é a raiz):
```
.git
.superpowers
**/.venv
**/node_modules
**/__pycache__
**/.pytest_cache
**/dist
fias-ed-android
fias-ed-web/.env
```

`fias-ed-web/.gitattributes`:
```
*.sh text eol=lf
*.conf text eol=lf
Dockerfile text eol=lf
*.Dockerfile text eol=lf
```

`fias-ed-web/.gitignore`:
```
.env
node_modules/
dist/
__pycache__/
.pytest_cache/
*.egg-info/
.source-snapshot.json
```

Registrar o estado das fontes científicas somente leitura (verificado na Task 18), a partir da raiz do monorepo:
```bash
cd fias-ed-shared && engine-py/.venv/Scripts/python scripts/source_snapshot.py create ../fias-ed-web/.source-snapshot.json && cd ..
```
Expected: arquivo `fias-ed-web/.source-snapshot.json` criado (ignorado pelo Git).

`fias-ed-web/.env.example`:
```
# Copie para .env e troque TODAS as senhas (use valores longos e aleatórios).
POSTGRES_PASSWORD=troque-esta-senha-do-superusuario
FIAS_ED_MIGRATOR_PASSWORD=troque-esta-senha-do-migrator
FIAS_ED_APP_PASSWORD=troque-esta-senha-da-aplicacao
DEVICE_ID=fias-ed-web
MAX_UPLOAD_BYTES=1610612736
MIN_AUDIO_SECONDS=60
MAX_AUDIO_SECONDS=9000
```

`fias-ed-web/deploy/db-init/01-roles.sh`:
```bash
#!/bin/bash
# Executado uma única vez pelo entrypoint do PostgreSQL ao criar o volume.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v db="$POSTGRES_DB" \
  -v migrator_pw="$FIAS_ED_MIGRATOR_PASSWORD" \
  -v app_pw="$FIAS_ED_APP_PASSWORD" <<'SQL'
CREATE ROLE fias_ed_migrator LOGIN PASSWORD :'migrator_pw';
CREATE ROLE fias_ed_app LOGIN PASSWORD :'app_pw';
ALTER DATABASE :"db" OWNER TO fias_ed_migrator;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO fias_ed_app;
ALTER SCHEMA public OWNER TO fias_ed_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO fias_ed_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fias_ed_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fias_ed_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fias_ed_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO fias_ed_app;
SQL
```

`fias-ed-web/docker-compose.test.yml`:
```yaml
name: fias-ed-test
services:
  db-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: test-superuser
      POSTGRES_DB: fias_ed
      FIAS_ED_MIGRATOR_PASSWORD: test-migrator
      FIAS_ED_APP_PASSWORD: test-app
    volumes:
      - ./deploy/db-init:/docker-entrypoint-initdb.d:ro
    tmpfs:
      - /var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d fias_ed"]
      interval: 2s
      timeout: 3s
      retries: 30
  api-test:
    build:
      context: ..
      dockerfile: fias-ed-web/backend/Dockerfile
      target: dev
    environment:
      DATABASE_URL: postgresql+psycopg://fias_ed_app:test-app@db-test:5432/fias_ed
      MIGRATOR_DATABASE_URL: postgresql+psycopg://fias_ed_migrator:test-migrator@db-test:5432/fias_ed
      AUDIO_STORE: /tmp/audio
    volumes:
      - ./backend:/app
    depends_on:
      db-test:
        condition: service_healthy
    command: ["pytest", "-q"]
```

`fias-ed-web/backend/Dockerfile`:
```dockerfile
# Contexto de build: raiz do monorepo (precisa de fias-ed-shared/).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    SHARED_DIR=/opt/fias-ed-shared AUDIO_STORE=/data/audio
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /data/audio && chown app:app /data/audio
COPY fias-ed-shared /opt/fias-ed-shared
# Editável: o motor localiza rules/ e schemas/ relativo ao próprio código.
RUN pip install -e /opt/fias-ed-shared/engine-py
WORKDIR /app
COPY fias-ed-web/backend /app

FROM base AS dev
RUN pip install -e ".[dev]"
USER app

FROM base AS prod
RUN pip install -e .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

`fias-ed-web/backend/pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "fias-ed-web-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.30,<1",
  "pydantic>=2.8,<3",
  "pydantic-settings>=2.4,<3",
  "sqlalchemy>=2.0.30,<2.1",
  "psycopg[binary]>=3.2,<4",
  "alembic>=1.13,<2",
  "argon2-cffi>=23.1,<26",
]

[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27", "bandit>=1.7.9", "pip-audit>=2.7"]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-p no:cacheprovider"
```

- [ ] **Step 2: Escrever os testes (falham)**

`fias-ed-web/backend/tests/__init__.py`: arquivo vazio.

`fias-ed-web/backend/tests/conftest.py`:
```python
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
```

`fias-ed-web/backend/tests/test_app_basics.py`:
```python
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
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q`
Expected: FAIL/ERROR na coleta (`ModuleNotFoundError: No module named 'app.main'`).

- [ ] **Step 4: Implementar**

`app/__init__.py`:
```python
APP_VERSION = "0.1.0"
```

`app/core/__init__.py`: vazio.

`app/core/config.py`:
```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    migrator_database_url: str | None = None
    audio_store: Path = Path("/data/audio")
    shared_dir: Path = Path("/opt/fias-ed-shared")
    device_id: str = "fias-ed-web"
    max_upload_bytes: int = 1_610_612_736
    min_audio_seconds: int = 60
    max_audio_seconds: int = 9_000
    session_idle_minutes: int = 120
    session_absolute_hours: int = 12
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    job_poll_seconds: float = 2.0
    job_stale_minutes: int = 30
    job_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`app/core/db.py`:
```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
SessionLocal = sessionmaker(expire_on_commit=False)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_db() -> Iterator[Session]:
    with SessionLocal(bind=get_engine()) as session:
        yield session
```

`app/core/logging.py`:
```python
import json
import logging
import sys

ALLOWED_FIELDS = frozenset({
    "event", "aula_id", "processamento_id", "job_id", "professor_id", "admin_id",
    "status", "duration_ms", "error_code", "error_type", "method", "path",
    "status_code", "attempt",
})

logger = logging.getLogger("fias_ed")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname}
        payload.update(getattr(record, "fields", {"event": record.getMessage()}))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Campos de log não permitidos: {sorted(unknown)}")
    safe = {k: (None if v is None else str(v)) for k, v in fields.items()}
    logger.log(level, event, extra={"fields": {"event": event, **safe}})
```

`app/core/errors.py`:
```python
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import log_event


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(code)
        self.status, self.code, self.message, self.extra = status, code, message, extra


_HTTP_DEFAULTS = {
    401: ("UNAUTHENTICATED", "Entre com seu usuário e senha."),
    403: ("FORBIDDEN", "Você não tem permissão para esta ação."),
    404: ("NOT_FOUND", "Não encontrado."),
    405: ("METHOD_NOT_ALLOWED", "Ação não permitida."),
}


def _body(code: str, message: str, **extra) -> dict:
    return {"error_code": code, "message": message, **extra}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, **exc.extra), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code, message = _HTTP_DEFAULTS.get(exc.status_code, ("HTTP_ERROR", "Não foi possível concluir a ação."))
        return JSONResponse(_body(code, message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()]
        return JSONResponse(_body("VALIDATION", "Confira os dados informados.", fields=fields),
                            status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log_event("unhandled_error", level=logging.ERROR, error_type=type(exc).__name__)
        return JSONResponse(_body("INTERNAL", "Algo deu errado. Tente novamente."), status_code=500)
```

`app/main.py`:
```python
import time

from fastapi import APIRouter, Depends, FastAPI, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, log_event

health_router = APIRouter()


@health_router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


async def request_log(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    route = request.scope.get("route")
    log_event("request", method=request.method,
              path=getattr(route, "path", "desconhecida"),
              status_code=response.status_code,
              duration_ms=int((time.monotonic() - started) * 1000))
    return response


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="FIAS-ED", docs_url=None, redoc_url=None, openapi_url=None)
    install_error_handlers(app)
    app.middleware("http")(request_log)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
```

(O `path` registrado é o modelo da rota, ex. `/api/aulas/{aula_id}`, nunca a URL com dados.)

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q`
Expected: todos os testes de `test_app_basics.py` PASS.

- [ ] **Step 6: Commit**

```bash
git add .dockerignore fias-ed-web
git commit -m "feat(web): esqueleto do backend, compose de testes, erros e logs estruturados

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Modelo de dados, Alembic, compatibilidade com o shared e privilégios do banco

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
- Create (gerado): `backend/alembic/versions/0001_w1_inicial.py`
- Modify: `backend/tests/conftest.py` (acrescentar fixtures de banco)
- Test: `backend/tests/test_schema_compat.py`, `backend/tests/test_db_privileges.py`

**Interfaces:**
- Consumes: `get_settings()`, `get_engine()`, `SessionLocal` (Task 1).
- Produces: `app.models` com `Base`, `utcnow()`, constantes `AULA_STATUS`, `ROLES`, `REGIONS`, `MIME_TYPES`, `JOB_STATUS`, `ADMIN_ACTIONS` e as classes `Professor`, `Escola`, `Turma`, `Disciplina`, `Aula`, `Audio`, `Processamento`, `Sessao`, `AudioUpload`, `Job`, `AcessoAdmin` (campos abaixo).
- Produces (testes): fixtures `migrator_engine` (sessão; aplica `alembic upgrade head`), `db` (Session como `fias_ed_app`); limpeza automática de todas as tabelas após cada teste.

- [ ] **Step 1: Escrever os testes (falham)**

Acrescentar ao fim de `backend/tests/conftest.py` (manter o conteúdo da Task 1):
```python
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


@pytest.fixture(scope="session")
def migrator_engine():
    command.upgrade(alembic_config(), "head")
    engine = create_engine(os.environ["MIGRATOR_DATABASE_URL"])
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(migrator_engine):
    yield
    from app.models import Base
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with migrator_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))  # nosec B608 - nomes vêm do metadata


@pytest.fixture
def db():
    from app.core.db import SessionLocal, get_engine
    with SessionLocal(bind=get_engine()) as session:
        yield session
```

`backend/tests/test_schema_compat.py`:
```python
"""Início do schema_compatibility_test (prompt §79): tabelas × schemas do shared."""
import json

import pytest
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.config import get_settings
from app.models import Base

ENTITY_TABLES = ["professor", "escola", "turma", "disciplina", "aula", "audio", "processamento"]


def load_schema(name: str):
    folder = get_settings().shared_dir / "schemas" / "entities"
    base = json.loads((folder / "_base.schema.json").read_text(encoding="utf-8"))
    schema = json.loads((folder / f"{name}.schema.json").read_text(encoding="utf-8"))
    props, required = dict(base["properties"]), set(base["required"])
    for part in schema["allOf"]:
        if "properties" in part:
            props.update(part["properties"])
            required |= set(part.get("required", []))
    return props, required


def allows_null(spec: dict) -> bool:
    t = spec.get("type")
    return isinstance(t, list) and "null" in t


def expected_types(spec: dict) -> tuple:
    if "enum" in spec:
        return (Enum,)
    t = spec["type"]
    if isinstance(t, list):
        t = next(x for x in t if x != "null")
    if t == "string":
        return {"uuid": (UUID,), "date-time": (DateTime,), "date": (Date,)}.get(spec.get("format"), (String, Text))
    return {"integer": (Integer, BigInteger), "number": (Float,), "boolean": (Boolean,), "object": (JSONB,)}[t]


@pytest.mark.parametrize("table", ENTITY_TABLES)
def test_table_matches_shared_schema(table):
    props, required = load_schema(table)
    cols = Base.metadata.tables[table].columns
    for name, spec in props.items():
        assert name in cols, f"{table}.{name} ausente"
        col = cols[name]
        assert isinstance(col.type, expected_types(spec)), f"{table}.{name}: tipo {col.type!r}"
        if "enum" in spec:
            assert set(col.type.enums) == set(spec["enum"]), f"{table}.{name}: enum difere"
        if "maxLength" in spec:
            assert col.type.length == spec["maxLength"], f"{table}.{name}: tamanho difere"
        if allows_null(spec):
            assert col.nullable, f"{table}.{name} deveria aceitar nulo"
        elif name in required:
            assert not col.nullable, f"{table}.{name} deveria ser NOT NULL"


def test_migrations_match_models(migrator_engine):
    from alembic import command
    from tests.conftest import alembic_config
    command.check(alembic_config())  # levanta erro se models e migrações divergirem
```

`backend/tests/test_db_privileges.py`:
```python
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import Professor


def test_app_user_cannot_run_ddl(db):
    with pytest.raises(DBAPIError):
        db.execute(text("CREATE TABLE invasora (id int)"))
    db.rollback()


def test_app_user_can_write_rows(db):
    db.add(Professor(username="ana", display_name="Ana", role="PROFESSOR", password_hash="x"))
    db.commit()
    assert db.query(Professor).count() == 1


def test_database_rejects_invalid_enum(db):
    with pytest.raises(IntegrityError):
        db.execute(text(
            "INSERT INTO professor (id, created_at, updated_at, version, sync_status, device_id,"
            " username, display_name, role, password_hash, is_active, must_change_password, failed_logins)"
            " VALUES (gen_random_uuid(), now(), now(), 1, 'LOCAL_ONLY', 'x', 'b', 'B', 'CHEFE', 'x',"
            " true, false, 0)"))
    db.rollback()


def test_base_fields_have_defaults(db):
    p = Professor(username="caio", display_name="Caio", role="PROFESSOR", password_hash="x")
    db.add(p)
    db.commit()
    assert p.version == 1 and p.sync_status == "LOCAL_ONLY" and p.device_id and p.deleted_at is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_schema_compat.py tests/test_db_privileges.py`
Expected: ERROR (`No module named 'app.models'` / `alembic.ini` ausente).

- [ ] **Step 3: Implementar `app/models.py`**

```python
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer,
                        MetaData, String, literal_column)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

AULA_STATUS = (
    "DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "PREPROCESSING", "TRANSCRIBING", "TRANSCRIBED",
    "DIARIZING", "READY_FOR_SPEAKER_REVIEW", "READY_FOR_TRANSCRIPT_REVIEW", "READY_FOR_FIAS",
    "FIAS_COMPLETED", "WAITING_QTI", "QTI_COMPLETED", "TRIANGULATED", "MTSS_INTERPRETED",
    "REPORT_READY", "ERROR",
)
SYNC_STATUS = ("LOCAL_ONLY", "PENDING_SYNC", "SYNCED", "CONFLICT")
ROLES = ("ADMIN_LOCAL", "PROFESSOR")
REGIONS = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
MIME_TYPES = ("audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac", "audio/flac", "audio/x-flac")
TRANSCRIPT_SOURCES = ("ASR_ORIGINAL", "TRANSCRICAO_REVISADA")
JOB_STATUS = ("queued", "running", "done", "failed")
ADMIN_ACTIONS = ("read", "create", "update", "delete", "upload", "process")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _device_id() -> str:
    return get_settings().device_id


def _enum(values: tuple, name: str) -> Enum:
    return Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class EntityMixin:
    """Campos comuns do _base.schema.json do shared."""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow,
                                                 nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, onupdate=literal_column("version + 1"),
                                         nullable=False)
    sync_status: Mapped[str] = mapped_column(_enum(SYNC_STATUS, "sync_status"), default="LOCAL_ONLY",
                                             nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), default=_device_id, nullable=False)


class Professor(EntityMixin, Base):
    __tablename__ = "professor"
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(_enum(ROLES, "role"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Escola(EntityMixin, Base):
    __tablename__ = "escola"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_key: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    municipality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(_enum(REGIONS, "region"), nullable=True)


class Turma(EntityMixin, Base):
    __tablename__ = "turma"
    escola_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escola.id"), nullable=False)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    school_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[str | None] = mapped_column(String(60), nullable=True)


class Disciplina(EntityMixin, Base):
    __tablename__ = "disciplina"
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Aula(EntityMixin, Base):
    __tablename__ = "aula"
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    turma_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("turma.id"), nullable=False)
    disciplina_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disciplina.id"), nullable=False)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(_enum(AULA_STATUS, "aula_status"), default="DRAFT", nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Audio(EntityMixin, Base):
    __tablename__ = "audio"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_filename: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(_enum(MIME_TYPES, "mime_type"), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False)
    derived_from_audio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audio.id"), nullable=True)


class Processamento(EntityMixin, Base):
    """Criada em W1 para manter o modelo completo; primeira linha nasce no W2."""
    __tablename__ = "processamento"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    app_version: Mapped[str] = mapped_column(String, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)
    asr_model: Mapped[str] = mapped_column(String, nullable=False)
    asr_model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    diarization_model: Mapped[str] = mapped_column(String, nullable=False)
    fias_model: Mapped[str] = mapped_column(String, nullable=False)
    fias_model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hardware: Mapped[str] = mapped_column(String(200), nullable=False)
    device: Mapped[str] = mapped_column(String(200), nullable=False)
    audio_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript_source: Mapped[str] = mapped_column(_enum(TRANSCRIPT_SOURCES, "transcript_source"), nullable=False)
    stage_times_ms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(_enum(AULA_STATUS, "processamento_status"), nullable=False)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_divergence_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ---- Tabelas internas (fora do modelo lógico compartilhado; nunca exportadas) ----

class Sessao(Base):
    __tablename__ = "sessao"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    acting_as_professor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("professor.id"), nullable=True)
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AudioUpload(Base):
    """Áudio recebido e ainda não validado (dados do schema Audio só existem após o ffprobe)."""
    __tablename__ = "audio_upload"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_filename: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_created", "status", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(_enum(JOB_STATUS, "job_status"), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AcessoAdmin(Base):
    __tablename__ = "acesso_admin"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), nullable=False)
    professor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("professor.id"), index=True, nullable=True)
    resource: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    action: Mapped[str] = mapped_column(_enum(ADMIN_ACTIONS, "admin_action"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
```

- [ ] **Step 4: Configurar o Alembic**

`backend/alembic.ini`:
```ini
[alembic]
script_location = alembic
file_template = %%(rev)s_%%(slug)s

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)s %(name)s %(message)s
```

`backend/alembic/env.py`:
```python
import os

from alembic import context
from sqlalchemy import create_engine

from app.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(os.environ["MIGRATOR_DATABASE_URL"])
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

`backend/alembic/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Gerar a migração (banco de teste vazio a cada execução):
```bash
docker compose -f docker-compose.test.yml run --rm api-test alembic revision --autogenerate --rev-id 0001 -m "w1 inicial"
```
Expected: cria `backend/alembic/versions/0001_w1_inicial.py`. Revisar o arquivo: 11 `op.create_table` (professor, escola, turma, disciplina, aula, audio, processamento, sessao, audio_upload, job, acesso_admin), cada `sa.Enum(...)` com `native_enum=False` e `create_constraint=True`. Se o autogenerate omitir `create_constraint=True` em algum Enum, acrescentar manualmente (o teste `test_database_rejects_invalid_enum` detecta a falta).

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS em todos os testes (incluindo os da Task 1; `test_migrations_match_models` confirma que migração e models batem).

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): modelo de dados compatível com os schemas do shared, Alembic e privilégios mínimos

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Senhas Argon2id, criação de contas e comando `create-admin`

**Files:**
- Create: `backend/app/auth/__init__.py`, `backend/app/auth/passwords.py`
- Create: `backend/app/users/__init__.py`, `backend/app/users/service.py`
- Create: `backend/app/cli.py`
- Test: `backend/tests/test_users.py`

**Interfaces:**
- Consumes: `Professor` (Task 2), `AppError` (Task 1), `SessionLocal`, `get_engine`.
- Produces: `app.auth.passwords`: `MIN_PASSWORD_LENGTH = 12`, `hash_password(p) -> str`, `verify_password(stored, p) -> bool`, `needs_rehash(stored) -> bool`, `generate_provisional_password() -> str`, `DUMMY_HASH: str`.
- Produces: `app.users.service`: `normalize_username(raw) -> str` (levanta `AppError(422, "USERNAME_INVALID")`), `validate_password(p) -> None` (levanta `AppError(422, "PASSWORD_TOO_SHORT")`), `create_professor(db, *, username, display_name, role, password, must_change_password) -> Professor` (levanta `AppError(409, "USERNAME_TAKEN")`; não faz commit).
- Produces: `python -m app.cli create-admin --username U --display-name N` (senha via `getpass`).

- [ ] **Step 1: Escrever os testes (falham)**

`backend/tests/test_users.py`:
```python
import pytest

from app.auth.passwords import (generate_provisional_password, hash_password, needs_rehash,
                                verify_password)
from app.core.errors import AppError
from app.models import Professor
from app.users.service import create_professor, normalize_username, validate_password


def test_hash_is_argon2id_and_verifies():
    h = hash_password("uma-senha-bem-longa")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "uma-senha-bem-longa")
    assert not verify_password(h, "outra-senha-longa")
    assert not needs_rehash(h)


def test_verify_handles_garbage_hash():
    assert not verify_password("não-é-hash", "qualquer")


def test_provisional_password_is_long_and_random():
    a, b = generate_provisional_password(), generate_provisional_password()
    assert len(a) >= 16 and a != b


@pytest.mark.parametrize("raw,expected", [(" Ana.Silva ", "ana.silva"), ("prof_01", "prof_01")])
def test_normalize_username(raw, expected):
    assert normalize_username(raw) == expected


@pytest.mark.parametrize("raw", ["ab", "com espaço", "ç", "x" * 65, "a/b"])
def test_normalize_username_rejects(raw):
    with pytest.raises(AppError) as e:
        normalize_username(raw)
    assert e.value.code == "USERNAME_INVALID"


def test_validate_password_min_length():
    with pytest.raises(AppError) as e:
        validate_password("curta")
    assert e.value.code == "PASSWORD_TOO_SHORT"
    validate_password("x" * 12)


def test_create_professor_and_duplicate(db):
    p = create_professor(db, username="Ana", display_name="Ana Souza", role="PROFESSOR",
                         password="senha-muito-segura", must_change_password=True)
    db.commit()
    assert p.username == "ana" and p.must_change_password and p.password_hash.startswith("$argon2id$")
    with pytest.raises(AppError) as e:
        create_professor(db, username="ana", display_name="Outra", role="PROFESSOR",
                         password="senha-muito-segura", must_change_password=False)
    assert e.value.code == "USERNAME_TAKEN" and e.value.status == 409


def test_cli_create_admin(db, monkeypatch, capsys):
    from app import cli
    answers = iter(["senha-do-admin-123", "senha-do-admin-123"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    assert cli.main(["create-admin", "--username", "pesquisador", "--display-name", "Pesquisador"]) == 0
    admin = db.query(Professor).filter_by(username="pesquisador").one()
    assert admin.role == "ADMIN_LOCAL" and not admin.must_change_password
    assert "senha-do-admin-123" not in capsys.readouterr().out


def test_cli_rejects_mismatched_passwords(db, monkeypatch):
    from app import cli
    answers = iter(["senha-do-admin-123", "senha-diferente-456"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    assert cli.main(["create-admin", "--username", "x-admin", "--display-name", "X"]) == 1
    assert db.query(Professor).count() == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_users.py`
Expected: ERROR (`No module named 'app.auth'`).

- [ ] **Step 3: Implementar**

`app/auth/__init__.py` e `app/users/__init__.py`: vazios.

`app/auth/passwords.py`:
```python
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 12
_hasher = PasswordHasher()  # Argon2id, perfil padrão RFC 9106 da biblioteca


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def generate_provisional_password() -> str:
    return secrets.token_urlsafe(12)  # 16 caracteres


# Usado para igualar o tempo de resposta quando o usuário não existe.
DUMMY_HASH = hash_password("fias-ed-senha-ficticia")
```

`app/users/service.py`:
```python
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import MIN_PASSWORD_LENGTH, hash_password
from app.core.errors import AppError
from app.models import Professor

_USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,64}$")


def normalize_username(raw: str) -> str:
    username = raw.strip().lower()
    if not _USERNAME_RE.match(username):
        raise AppError(422, "USERNAME_INVALID",
                       "Use de 3 a 64 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado.")
    return username


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AppError(422, "PASSWORD_TOO_SHORT",
                       f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")


def create_professor(db: Session, *, username: str, display_name: str, role: str, password: str,
                     must_change_password: bool) -> Professor:
    username = normalize_username(username)
    validate_password(password)
    if db.scalar(select(Professor.id).where(Professor.username == username)):
        raise AppError(409, "USERNAME_TAKEN", "Este nome de usuário já está em uso.")
    professor = Professor(username=username, display_name=display_name.strip(), role=role,
                          password_hash=hash_password(password),
                          must_change_password=must_change_password)
    db.add(professor)
    db.flush()
    return professor
```

`app/cli.py`:
```python
import argparse
import getpass
import sys

from app.core.db import SessionLocal, get_engine
from app.core.errors import AppError
from app.users.service import create_professor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Cria um administrador local")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name", required=True)
    args = parser.parse_args(argv)

    password = getpass.getpass("Senha do administrador: ")
    if password != getpass.getpass("Repita a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    with SessionLocal(bind=get_engine()) as db:
        try:
            create_professor(db, username=args.username, display_name=args.display_name,
                             role="ADMIN_LOCAL", password=password, must_change_password=False)
            db.commit()
        except AppError as exc:
            print(exc.message, file=sys.stderr)
            return 1
    print("Administrador criado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_users.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): senhas Argon2id, criação de contas e comando create-admin

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Sessão, login/logout, troca de senha, CSRF e bloqueio

**Files:**
- Create: `backend/app/auth/sessions.py`, `backend/app/auth/deps.py`, `backend/app/auth/routes.py`
- Modify: `backend/app/main.py` (incluir o router de auth)
- Create: `backend/tests/helpers.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: passwords/service (Task 3), models (Task 2).
- Produces: `app.auth.sessions`: `COOKIE_SESSION = "fias_session"`, `COOKIE_CSRF = "fias_csrf"`, `CSRF_HEADER = "X-CSRF-Token"`, `NewSession(token, csrf, row)`, `create_session(db, professor) -> NewSession`, `resolve_session(db, token) -> Sessao | None`, `delete_all_sessions(db, professor_id)`, `csrf_ok(sessao, header) -> bool`, `set_session_cookies(response, new_session)`, `clear_session_cookies(response)`.
- Produces: `app.auth.deps`: `Actor` (dataclass: `user: Professor`, `session: Sessao`, `acting_as: Professor | None`, propriedades `effective_professor_id: uuid.UUID`, `is_admin: bool`), dependências `current_actor_any` (sem checar troca de senha), `current_actor` (exige `must_change_password=False`), `current_admin` (exige ADMIN_LOCAL; nunca vale "agir como" para rotas de admin).
- Produces: `app.auth.routes.router` (prefixo aplicado em `main`: `/api`) e `me_payload(actor: Actor) -> dict` com chaves `id, username, display_name, role, must_change_password, acting_as` (`acting_as` = `{"id", "display_name"}` ou `None`).
- Produces (testes): `tests/helpers.py` com `PASSWORD`, `make_user(db, username, role="PROFESSOR", *, password=PASSWORD, must_change=False, active=True) -> Professor` e `login(client, username, password=PASSWORD)` (faz login e coloca o cabeçalho `X-CSRF-Token` no client).

- [ ] **Step 1: Escrever os testes (falham)**

`backend/tests/helpers.py`:
```python
from app.auth.passwords import hash_password
from app.models import Professor

PASSWORD = "senha-de-teste-123"
_HASH = hash_password(PASSWORD)


def make_user(db, username: str, role: str = "PROFESSOR", *, password: str = PASSWORD,
              must_change: bool = False, active: bool = True) -> Professor:
    user = Professor(username=username, display_name=username.title(), role=role,
                     password_hash=_HASH if password == PASSWORD else hash_password(password),
                     must_change_password=must_change, is_active=active)
    db.add(user)
    db.commit()
    return user


def login(client, username: str, password: str = PASSWORD):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = client.cookies["fias_csrf"]
    return r
```

`backend/tests/test_auth.py`:
```python
from datetime import timedelta

from fastapi import Depends

from app.auth.deps import Actor, current_actor
from app.models import Professor, Sessao, utcnow
from tests.helpers import PASSWORD, login, make_user


def test_login_sets_secure_cookies(client, db):
    make_user(db, "ana")
    r = client.post("/api/auth/login", json={"username": "Ana", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["username"] == "ana" and r.json()["acting_as"] is None
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("fias_session="))
    csrf_cookie = next(c for c in cookies if c.startswith("fias_csrf="))
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"):
        assert flag.lower() in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()
    token = session_cookie.split(";")[0].split("=", 1)[1]
    row = db.query(Sessao).one()
    assert row.token_sha256 != token and len(row.token_sha256) == 64


def test_wrong_password_and_unknown_user_same_message(client, db):
    make_user(db, "ana")
    a = client.post("/api/auth/login", json={"username": "ana", "password": "errada-errada-1"})
    b = client.post("/api/auth/login", json={"username": "ninguem", "password": "errada-errada-1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() == {"error_code": "LOGIN_FAILED", "message": "Usuário ou senha incorretos."}


def test_lockout_after_five_failures(client, db):
    make_user(db, "ana")
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "ana", "password": "errada-errada-1"})
    r = client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD})
    assert r.status_code == 401
    user = db.query(Professor).filter_by(username="ana").one()
    db.refresh(user)
    user.locked_until = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 200


def test_inactive_user_cannot_login(client, db):
    make_user(db, "ana", active=False)
    assert client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 401


def test_me_requires_session(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["error_code"] == "UNAUTHENTICATED"


def test_forged_session_cookie_rejected(client):
    client.cookies.set("fias_session", "forjado")
    assert client.get("/api/auth/me").status_code == 401


def test_idle_expiry(client, db):
    make_user(db, "ana")
    login(client, "ana")
    s = db.query(Sessao).one()
    s.last_seen_at = utcnow() - timedelta(minutes=121)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401
    assert db.query(Sessao).count() == 0


def test_absolute_expiry(client, db):
    make_user(db, "ana")
    login(client, "ana")
    s = db.query(Sessao).one()
    s.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_logout_invalidates_session(client, db):
    make_user(db, "ana")
    login(client, "ana")
    assert client.post("/api/auth/logout").status_code == 204
    assert db.query(Sessao).count() == 0
    assert client.get("/api/auth/me").status_code == 401


def test_mutation_without_csrf_rejected(client, db):
    make_user(db, "ana")
    login(client, "ana")
    del client.headers["X-CSRF-Token"]
    r = client.post("/api/auth/logout")
    assert r.status_code == 403 and r.json()["error_code"] == "CSRF_INVALID"
    client.headers["X-CSRF-Token"] = "valor-errado"
    assert client.post("/api/auth/logout").status_code == 403


def test_password_change_invalidates_other_sessions(client_factory, db):
    make_user(db, "ana")
    a, b = client_factory(), client_factory()
    login(a, "ana")
    login(b, "ana")
    r = a.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "nova-senha-segura-1"})
    assert r.status_code == 200
    assert a.get("/api/auth/me").status_code == 200  # nova sessão emitida para quem trocou
    assert b.get("/api/auth/me").status_code == 401


def test_password_change_requires_current_password(client, db):
    make_user(db, "ana")
    login(client, "ana")
    r = client.post("/api/auth/password", json={"current_password": "errada-errada-1", "new_password": "nova-senha-segura-1"})
    assert r.status_code == 401 and r.json()["error_code"] == "PASSWORD_WRONG"


def test_must_change_password_blocks_other_routes(app_instance, client, db):
    @app_instance.get("/api/_pronto")
    def pronto(actor: Actor = Depends(current_actor)):
        return {"ok": True}

    make_user(db, "ana", must_change=True)
    login(client, "ana")
    assert client.get("/api/auth/me").json()["must_change_password"] is True
    r = client.get("/api/_pronto")
    assert r.status_code == 403 and r.json()["error_code"] == "PASSWORD_CHANGE_REQUIRED"
    client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "nova-senha-segura-1"})
    client.headers["X-CSRF-Token"] = client.cookies["fias_csrf"]
    assert client.get("/api/_pronto").status_code == 200
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_auth.py`
Expected: ERROR (`No module named 'app.auth.deps'`).

- [ ] **Step 3: Implementar `app/auth/sessions.py`**

```python
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Professor, Sessao, utcnow

COOKIE_SESSION = "fias_session"
COOKIE_CSRF = "fias_csrf"
CSRF_HEADER = "X-CSRF-Token"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class NewSession:
    token: str
    csrf: str
    row: Sessao


def create_session(db: Session, professor: Professor) -> NewSession:
    s = get_settings()
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = utcnow()
    row = Sessao(professor_id=professor.id, token_sha256=_sha256(token), csrf_token_sha256=_sha256(csrf),
                 created_at=now, last_seen_at=now,
                 expires_at=now + timedelta(hours=s.session_absolute_hours))
    db.add(row)
    db.flush()
    return NewSession(token, csrf, row)


def resolve_session(db: Session, token: str | None) -> Sessao | None:
    if not token:
        return None
    row = db.scalar(select(Sessao).where(Sessao.token_sha256 == _sha256(token)))
    if row is None:
        return None
    now = utcnow()
    idle_limit = row.last_seen_at + timedelta(minutes=get_settings().session_idle_minutes)
    if row.expires_at <= now or idle_limit <= now:
        db.delete(row)
        db.commit()
        return None
    row.last_seen_at = now
    return row


def delete_all_sessions(db: Session, professor_id: uuid.UUID) -> None:
    db.execute(delete(Sessao).where(Sessao.professor_id == professor_id))


def csrf_ok(sessao: Sessao, header_value: str | None) -> bool:
    return hmac.compare_digest(_sha256(header_value or ""), sessao.csrf_token_sha256)


def set_session_cookies(response: Response, new_session: NewSession) -> None:
    max_age = get_settings().session_absolute_hours * 3600
    common = {"secure": True, "samesite": "strict", "path": "/", "max_age": max_age}
    response.set_cookie(COOKIE_SESSION, new_session.token, httponly=True, **common)
    response.set_cookie(COOKIE_CSRF, new_session.csrf, httponly=False, **common)


def clear_session_cookies(response: Response) -> None:
    for name in (COOKIE_SESSION, COOKIE_CSRF):
        response.delete_cookie(name, path="/", secure=True, samesite="strict")
```

- [ ] **Step 4: Implementar `app/auth/deps.py`**

```python
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.sessions import COOKIE_SESSION, CSRF_HEADER, csrf_ok, resolve_session
from app.core.db import get_db
from app.core.errors import AppError
from app.models import Professor, Sessao

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class Actor:
    user: Professor
    session: Sessao
    acting_as: Professor | None

    @property
    def effective_professor_id(self) -> uuid.UUID:
        return self.acting_as.id if self.acting_as else self.user.id

    @property
    def is_admin(self) -> bool:
        return self.user.role == "ADMIN_LOCAL"


def _unauthenticated() -> AppError:
    return AppError(401, "UNAUTHENTICATED", "Entre com seu usuário e senha.")


def current_actor_any(request: Request, db: Session = Depends(get_db)) -> Actor:
    sessao = resolve_session(db, request.cookies.get(COOKIE_SESSION))
    if sessao is None:
        raise _unauthenticated()
    user = db.get(Professor, sessao.professor_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        db.delete(sessao)
        db.commit()
        raise _unauthenticated()
    if request.method in _MUTATING and not csrf_ok(sessao, request.headers.get(CSRF_HEADER)):
        raise AppError(403, "CSRF_INVALID", "Sua sessão precisa ser renovada. Recarregue a página.")
    acting = None
    if sessao.acting_as_professor_id is not None:
        target = db.get(Professor, sessao.acting_as_professor_id)
        if user.role == "ADMIN_LOCAL" and target is not None and target.deleted_at is None:
            acting = target
        else:
            sessao.acting_as_professor_id = None
    db.commit()
    return Actor(user=user, session=sessao, acting_as=acting)


def current_actor(actor: Actor = Depends(current_actor_any)) -> Actor:
    if actor.user.must_change_password:
        raise AppError(403, "PASSWORD_CHANGE_REQUIRED", "Troque sua senha provisória para continuar.")
    return actor


def current_admin(actor: Actor = Depends(current_actor)) -> Actor:
    if not actor.is_admin:
        raise AppError(403, "FORBIDDEN", "Você não tem permissão para esta ação.")
    return actor
```

- [ ] **Step 5: Implementar `app/auth/routes.py` e registrar em `main`**

```python
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import Actor, current_actor_any
from app.auth.passwords import DUMMY_HASH, hash_password, needs_rehash, verify_password
from app.auth.sessions import (clear_session_cookies, create_session, delete_all_sessions,
                               set_session_cookies)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Professor, utcnow
from app.users.service import validate_password

router = APIRouter()


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def me_payload(actor: Actor) -> dict:
    u = actor.user
    return {
        "id": str(u.id), "username": u.username, "display_name": u.display_name, "role": u.role,
        "must_change_password": u.must_change_password,
        "acting_as": ({"id": str(actor.acting_as.id), "display_name": actor.acting_as.display_name}
                      if actor.acting_as else None),
    }


def _login_failed() -> AppError:
    return AppError(401, "LOGIN_FAILED", "Usuário ou senha incorretos.")


@router.post("/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    s, now = get_settings(), utcnow()
    user = db.scalar(select(Professor).where(Professor.username == body.username.strip().lower(),
                                             Professor.deleted_at.is_(None)))
    if user is None or (user.locked_until is not None and user.locked_until > now):
        verify_password(DUMMY_HASH, body.password)
        raise _login_failed()
    if not verify_password(user.password_hash, body.password):
        user.failed_logins += 1
        if user.failed_logins >= s.login_max_failures:
            user.locked_until = now + timedelta(minutes=s.login_lock_minutes)
            user.failed_logins = 0
            log_event("login_locked", level=logging.WARNING, professor_id=user.id)
        db.commit()
        raise _login_failed()
    if not user.is_active:
        raise _login_failed()
    user.failed_logins, user.locked_until = 0, None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    new_session = create_session(db, user)
    db.commit()
    set_session_cookies(response, new_session)
    log_event("login", professor_id=user.id)
    return me_payload(Actor(user=user, session=new_session.row, acting_as=None))


@router.post("/auth/logout", status_code=204)
def logout(response: Response, actor: Actor = Depends(current_actor_any), db: Session = Depends(get_db)):
    db.delete(db.merge(actor.session))
    db.commit()
    clear_session_cookies(response)


@router.get("/auth/me")
def me(actor: Actor = Depends(current_actor_any)):
    return me_payload(actor)


@router.post("/auth/password")
def change_password(body: PasswordIn, response: Response, actor: Actor = Depends(current_actor_any),
                    db: Session = Depends(get_db)):
    user = db.merge(actor.user)
    if not verify_password(user.password_hash, body.current_password):
        raise AppError(401, "PASSWORD_WRONG", "A senha atual não confere.")
    validate_password(body.new_password)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    delete_all_sessions(db, user.id)
    new_session = create_session(db, user)
    db.commit()
    set_session_cookies(response, new_session)
    log_event("password_changed", professor_id=user.id)
    return me_payload(Actor(user=user, session=new_session.row, acting_as=None))
```

Em `app/main.py`, dentro de `create_app()`, depois do `health_router`:
```python
    from app.auth.routes import router as auth_router
    app.include_router(auth_router, prefix="/api")
```

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS em todos.

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): sessão no servidor, login/logout, troca de senha, CSRF e bloqueio por tentativas

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---
### Task 5: Registro de acesso do admin e "agir como"

**Files:**
- Create: `backend/app/audit.py`
- Create: `backend/app/admin/__init__.py`, `backend/app/admin/routes.py`
- Modify: `backend/app/main.py` (incluir o router de admin)
- Test: `backend/tests/test_admin_act_as.py`

**Interfaces:**
- Consumes: `Actor`, `current_admin`, `current_actor` (Task 4), `me_payload` (Task 4), `AcessoAdmin`, `Professor` (Task 2).
- Produces: `app.audit.record(db, *, admin_id, professor_id, resource, resource_id, action) -> None`; `app.audit.audit(db, actor, resource: str, resource_id: uuid.UUID | None, action: str) -> None` (só grava quando `actor.acting_as` existe; não faz commit); `app.audit.last_admin_change(db, aula_id) -> datetime | None` (maior `created_at` com `resource="aula"`, `resource_id=aula_id`, `action != "read"`).
- Produces: `app.admin.routes.router` (`APIRouter(prefix="/admin")`, incluído em `/api`) com `POST /admin/agir-como` `{"professor_id": uuid}` e `DELETE /admin/agir-como`, ambos devolvendo `me_payload`. Tasks 6 e 10 acrescentam rotas a este arquivo.
- Convenção de `resource` em `acesso_admin`: `"aula"` para tudo que é de uma aula (inclusive upload e processamento, com `resource_id = aula_id`), `"turma"`, `"disciplina"`, `"professor"`.

- [ ] **Step 1: Escrever os testes (falham)**

`backend/tests/test_admin_act_as.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_admin_act_as.py`
Expected: ERROR (`No module named 'app.audit'`).

- [ ] **Step 3: Implementar**

`app/audit.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AcessoAdmin


def record(db: Session, *, admin_id: uuid.UUID, professor_id: uuid.UUID | None, resource: str,
           resource_id: uuid.UUID | None, action: str) -> None:
    db.add(AcessoAdmin(admin_id=admin_id, professor_id=professor_id, resource=resource,
                       resource_id=resource_id, action=action))


def audit(db: Session, actor, resource: str, resource_id: uuid.UUID | None, action: str) -> None:
    """Registra leitura/alteração do admin sobre dados de outro professor.

    Não faz nada quando o usuário age sobre os próprios dados."""
    if actor.acting_as is None:
        return
    record(db, admin_id=actor.user.id, professor_id=actor.acting_as.id, resource=resource,
           resource_id=resource_id, action=action)


def last_admin_change(db: Session, aula_id: uuid.UUID) -> datetime | None:
    return db.scalar(select(func.max(AcessoAdmin.created_at)).where(
        AcessoAdmin.resource == "aula", AcessoAdmin.resource_id == aula_id, AcessoAdmin.action != "read"))
```

`app/admin/__init__.py`: vazio.

`app/admin/routes.py`:
```python
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import record
from app.auth.deps import Actor, current_admin
from app.auth.routes import me_payload
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Professor

router = APIRouter(prefix="/admin")


class AgirComoIn(BaseModel):
    professor_id: uuid.UUID


@router.post("/agir-como")
def agir_como(body: AgirComoIn, actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    if body.professor_id == actor.user.id:
        raise AppError(422, "AGIR_COMO_PROPRIA_CONTA", "Você já está na sua própria conta.")
    target = db.get(Professor, body.professor_id)
    if target is None or target.deleted_at is not None:
        raise AppError(404, "CONTA_NAO_ENCONTRADA", "Conta não encontrada.")
    actor.session.acting_as_professor_id = target.id
    record(db, admin_id=actor.user.id, professor_id=target.id, resource="professor",
           resource_id=target.id, action="read")
    db.commit()
    log_event("admin_act_as", admin_id=actor.user.id, professor_id=target.id)
    return me_payload(Actor(user=actor.user, session=actor.session, acting_as=target))


@router.delete("/agir-como")
def parar_de_agir(actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    actor.session.acting_as_professor_id = None
    db.commit()
    return me_payload(Actor(user=actor.user, session=actor.session, acting_as=None))
```

Em `app/main.py`, dentro de `create_app()`, depois do router de auth:
```python
    from app.admin.routes import router as admin_router
    app.include_router(admin_router, prefix="/api")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): admin age em nome do professor, com registro de acesso

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Escolas (cadastro comum), turmas e disciplinas

**Files:**
- Create: `backend/app/catalog/__init__.py`, `backend/app/catalog/names.py`, `backend/app/catalog/routes.py`
- Modify: `backend/app/main.py` (incluir o router do catálogo)
- Test: `backend/tests/test_catalog.py`

**Interfaces:**
- Consumes: `current_actor`, `current_admin`, `Actor` (Task 4); `audit` (Task 5); models (Task 2).
- Produces: `app.catalog.names.name_key(text: str) -> str` (minúsculas, sem acentos, espaços colapsados).
- Produces rotas (prefixo `/api`):
  - `GET /escolas` → `[{"id","name","municipality","region"}]`; `POST /escolas` `{"name","municipality"?, "region"?, "confirmar_nova"?: bool}` → 201 escola, ou 409 `ESCOLA_DUPLICADA` com `duplicatas: [escola]`.
  - `GET /turmas` → `[{"id","name","school_year","level","escola": escola}]`; `POST /turmas` `{"name","escola_id","school_year"?, "level"?}` → 201.
  - `GET /disciplinas` → `[{"id","name"}]`; `POST /disciplinas` `{"name"}` → 201.
  - `PATCH /admin/escolas/{id}` `{"name"?, "municipality"?, "region"?}`; `POST /admin/escolas/{id}/juntar` `{"destino_id"}` → 200 escola destino.

- [ ] **Step 1: Escrever os testes (falham)**

`backend/tests/test_catalog.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_catalog.py`
Expected: ERROR (`No module named 'app.catalog'`).

- [ ] **Step 3: Implementar**

`app/catalog/__init__.py`: vazio.

`app/catalog/names.py`:
```python
import unicodedata


def name_key(text: str) -> str:
    """Chave de comparação: minúsculas, sem acentos, espaços colapsados."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.lower().split())
```

`app/catalog/routes.py`:
```python
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import Actor, current_actor, current_admin
from app.catalog.names import name_key
from app.core.db import get_db
from app.core.errors import AppError
from app.models import Disciplina, Escola, Turma, utcnow

router = APIRouter()

Name120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Name200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Municipio = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Regiao = Literal["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]


class EscolaIn(BaseModel):
    name: Name200
    municipality: Municipio | None = None
    region: Regiao | None = None
    confirmar_nova: bool = False


class EscolaPatch(BaseModel):
    name: Name200 | None = None
    municipality: Municipio | None = None
    region: Regiao | None = None


class JuntarIn(BaseModel):
    destino_id: uuid.UUID


class TurmaIn(BaseModel):
    name: Name120
    escola_id: uuid.UUID
    school_year: int | None = Field(default=None, ge=1900, le=2100)
    level: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None


class DisciplinaIn(BaseModel):
    name: Name120


def escola_out(e: Escola) -> dict:
    return {"id": str(e.id), "name": e.name, "municipality": e.municipality, "region": e.region}


def turma_out(t: Turma, e: Escola) -> dict:
    return {"id": str(t.id), "name": t.name, "school_year": t.school_year, "level": t.level,
            "escola": escola_out(e)}


def disciplina_out(d: Disciplina) -> dict:
    return {"id": str(d.id), "name": d.name}


def _active_escola(db: Session, escola_id: uuid.UUID) -> Escola | None:
    e = db.get(Escola, escola_id)
    return e if e is not None and e.deleted_at is None else None


@router.get("/escolas")
def list_escolas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.scalars(select(Escola).where(Escola.deleted_at.is_(None)).order_by(Escola.name))
    return [escola_out(e) for e in rows]


@router.post("/escolas", status_code=201)
def create_escola(body: EscolaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    key, municipality = name_key(body.name), (body.municipality or None)
    if not body.confirmar_nova:
        same_name = db.scalars(select(Escola).where(Escola.name_key == key, Escola.deleted_at.is_(None)))
        duplicates = [e for e in same_name if name_key(e.municipality or "") == name_key(municipality or "")]
        if duplicates:
            raise AppError(409, "ESCOLA_DUPLICADA", "Já existe uma escola com este nome neste município.",
                           duplicatas=[escola_out(e) for e in duplicates])
    escola = Escola(name=body.name, name_key=key, municipality=municipality, region=body.region)
    db.add(escola)
    db.commit()
    return escola_out(escola)


@router.get("/turmas")
def list_turmas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.execute(select(Turma, Escola).join(Escola, Escola.id == Turma.escola_id).where(
        Turma.professor_id == actor.effective_professor_id, Turma.deleted_at.is_(None)).order_by(Turma.name)).all()
    audit(db, actor, "turma", None, "read")
    db.commit()
    return [turma_out(t, e) for t, e in rows]


@router.post("/turmas", status_code=201)
def create_turma(body: TurmaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    escola = _active_escola(db, body.escola_id)
    if escola is None:
        raise AppError(422, "ESCOLA_INVALIDA", "Escolha uma escola da lista ou cadastre uma nova.")
    turma = Turma(escola_id=escola.id, professor_id=actor.effective_professor_id, name=body.name,
                  school_year=body.school_year, level=body.level or None)
    db.add(turma)
    db.flush()
    audit(db, actor, "turma", turma.id, "create")
    db.commit()
    return turma_out(turma, escola)


@router.get("/disciplinas")
def list_disciplinas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.scalars(select(Disciplina).where(Disciplina.professor_id == actor.effective_professor_id,
                                               Disciplina.deleted_at.is_(None)).order_by(Disciplina.name))
    result = [disciplina_out(d) for d in rows]
    audit(db, actor, "disciplina", None, "read")
    db.commit()
    return result


@router.post("/disciplinas", status_code=201)
def create_disciplina(body: DisciplinaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    disciplina = Disciplina(professor_id=actor.effective_professor_id, name=body.name)
    db.add(disciplina)
    db.flush()
    audit(db, actor, "disciplina", disciplina.id, "create")
    db.commit()
    return disciplina_out(disciplina)


@router.patch("/admin/escolas/{escola_id}")
def patch_escola(escola_id: uuid.UUID, body: EscolaPatch, actor: Actor = Depends(current_admin),
                 db: Session = Depends(get_db)):
    escola = _active_escola(db, escola_id)
    if escola is None:
        raise AppError(404, "ESCOLA_NAO_ENCONTRADA", "Escola não encontrada.")
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"]:
        escola.name, escola.name_key = changes["name"], name_key(changes["name"])
    if "municipality" in changes:
        escola.municipality = changes["municipality"] or None
    if "region" in changes:
        escola.region = changes["region"]
    db.commit()
    return escola_out(escola)


@router.post("/admin/escolas/{escola_id}/juntar")
def juntar_escolas(escola_id: uuid.UUID, body: JuntarIn, actor: Actor = Depends(current_admin),
                   db: Session = Depends(get_db)):
    if escola_id == body.destino_id:
        raise AppError(422, "JUNCAO_INVALIDA", "Escolha uma escola diferente para manter.")
    origem, destino = _active_escola(db, escola_id), _active_escola(db, body.destino_id)
    if origem is None or destino is None:
        raise AppError(404, "ESCOLA_NAO_ENCONTRADA", "Escola não encontrada.")
    db.execute(update(Turma).where(Turma.escola_id == origem.id).values(escola_id=destino.id))
    origem.deleted_at = utcnow()
    db.commit()
    return escola_out(destino)
```

Em `app/main.py`, dentro de `create_app()`:
```python
    from app.catalog.routes import router as catalog_router
    app.include_router(catalog_router, prefix="/api")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): escolas como cadastro comum com detecção de duplicatas, turmas e disciplinas

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Aulas, mensagens humanas de erro e armazenamento seguro

**Files:**
- Create: `backend/app/core/messages.py`
- Create: `backend/app/audio/__init__.py`, `backend/app/audio/storage.py`
- Create: `backend/app/aulas/__init__.py`, `backend/app/aulas/service.py`, `backend/app/aulas/routes.py`
- Modify: `backend/app/main.py` (incluir o router de aulas)
- Modify: `backend/tests/helpers.py` (acrescentar `make_aula`)
- Test: `backend/tests/test_messages.py`, `backend/tests/test_aulas.py`

**Interfaces:**
- Consumes: `get_settings` (Task 1), `current_actor` (Task 4), `audit`, `last_admin_change` (Task 5), models (Task 2).
- Produces: `app.core.messages.error_message(code: str | None) -> str | None`, `format_duration(seconds: int) -> str`, `format_size(num_bytes: int) -> str`.
- Produces: `app.audio.storage`: `store_root() -> Path`, `ensure_dirs() -> None` (cria `tmp/` e `original/`), `abs_path(rel: str) -> Path` (levanta `ValueError` fora da raiz), `delete_file(rel: str) -> None`.
- Produces: `app.aulas.service`: `get_owned_aula(db, actor, aula_id) -> Aula` (404 `AULA_NAO_ENCONTRADA`), `has_active_job(db, aula_id) -> bool`, `current_audio(db, aula_id) -> Audio | None`, `pending_upload(db, aula_id) -> AudioUpload | None`, `aula_summary(aula, turma, disciplina) -> dict`, `aula_payload(db, aula) -> dict`, `soft_delete_aula(db, aula) -> list[str]` (devolve caminhos relativos a apagar depois do commit).
- Produces rotas: `POST /api/aulas` (201), `GET /api/aulas`, `GET /api/aulas/{id}`, `DELETE /api/aulas/{id}` (204).
- `aula_payload` tem as chaves: `id, lesson_date, status, turma{id,name}, disciplina{id,name}, note, error_code, error_message, audio (ou null: original_filename, mime_type, size_bytes, duration_ms, channels, sample_rate), upload_pendente (ou null: original_filename, size_bytes), job_ativo, alterada_pelo_admin_em (ISO ou null)`. `aula_summary` tem `id, lesson_date, status, turma, disciplina`.
- Produces (testes): `tests/helpers.make_aula(db, professor, status="DRAFT") -> Aula` (cria escola, turma e disciplina do professor).

- [ ] **Step 1: Escrever os testes (falham)**

Acrescentar ao fim de `backend/tests/helpers.py`:
```python
from datetime import date

from app.models import Aula, Disciplina, Escola, Turma


def make_aula(db, professor, status: str = "DRAFT") -> Aula:
    escola = Escola(name="Escola Teste", name_key="escola teste")
    db.add(escola)
    db.flush()
    turma = Turma(escola_id=escola.id, professor_id=professor.id, name="9º Ano B")
    disciplina = Disciplina(professor_id=professor.id, name="Matemática")
    db.add_all([turma, disciplina])
    db.flush()
    aula = Aula(professor_id=professor.id, turma_id=turma.id, disciplina_id=disciplina.id,
                lesson_date=date(2026, 9, 22), status=status)
    db.add(aula)
    db.commit()
    return aula
```

`backend/tests/test_messages.py`:
```python
import pytest

from app.core.config import get_settings
from app.core.messages import error_message, format_duration, format_size


@pytest.mark.parametrize("seconds,text", [(60, "1 minuto"), (45 * 60, "45 minutos"), (3600, "1h"),
                                          (9000, "2h30"), (5400, "1h30")])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


@pytest.mark.parametrize("size,text", [(1_610_612_736, "1,5 GB"), (2 * 1024 ** 3, "2 GB"),
                                       (500 * 1024 ** 2, "500 MB")])
def test_format_size(size, text):
    assert format_size(size) == text


def test_messages_use_configured_limits(monkeypatch):
    monkeypatch.setenv("MAX_AUDIO_SECONDS", "5400")
    get_settings.cache_clear()
    assert error_message("AUDIO_TOO_LONG") == \
        "O áudio tem mais de 1h30. Divida a gravação e envie cada parte como uma aula."
    get_settings.cache_clear()


def test_all_codes_have_messages():
    for code in ("AUDIO_FORMAT_MISMATCH", "AUDIO_UNSUPPORTED_FORMAT", "AUDIO_TOO_LONG", "AUDIO_TOO_SHORT",
                 "AUDIO_CORRUPTED", "AUDIO_TOO_LARGE", "AUDIO_LOCKED", "JOB_FAILED"):
        assert error_message(code)
    assert error_message(None) is None
    assert error_message("DESCONHECIDO") == "Algo deu errado. Tente novamente."
```

`backend/tests/test_aulas.py`:
```python
import uuid

from app.audio.storage import abs_path, ensure_dirs, store_root
from app.models import Aula, Audio, AudioUpload, Job
from tests.helpers import login, make_aula, make_user


def _catalog(client):
    escola = client.post("/api/escolas", json={"name": "Escola A"}).json()
    turma = client.post("/api/turmas", json={"name": "9º B", "escola_id": escola["id"]}).json()
    disciplina = client.post("/api/disciplinas", json={"name": "Ciências"}).json()
    return turma, disciplina


def test_create_list_and_get_aula(client, db):
    make_user(db, "ana")
    login(client, "ana")
    turma, disciplina = _catalog(client)
    r = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                        "lesson_date": "2026-09-22", "note": "Aula de revisão"})
    assert r.status_code == 201
    aula = r.json()
    assert aula["status"] == "DRAFT" and aula["turma"]["name"] == "9º B" and aula["note"] == "Aula de revisão"
    assert aula["audio"] is None and aula["upload_pendente"] is None and aula["job_ativo"] is False
    assert aula["alterada_pelo_admin_em"] is None and aula["error_message"] is None
    assert [a["id"] for a in client.get("/api/aulas").json()] == [aula["id"]]
    assert client.get(f"/api/aulas/{aula['id']}").json()["id"] == aula["id"]


def test_cannot_use_other_professor_turma(client_factory, db):
    make_user(db, "ana")
    make_user(db, "bia")
    a, b = client_factory(), client_factory()
    login(a, "ana")
    login(b, "bia")
    turma, disciplina = _catalog(a)
    _, disc_b = _catalog(b)
    r = b.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disc_b["id"], "lesson_date": "2026-09-22"})
    assert r.status_code == 422 and r.json()["error_code"] == "TURMA_INVALIDA"


def test_other_professor_aula_is_404(client, db):
    make_user(db, "ana")
    bia = make_user(db, "bia")
    aula = make_aula(db, bia)
    login(client, "ana")
    r = client.get(f"/api/aulas/{aula.id}")
    assert r.status_code == 404 and r.json()["error_code"] == "AULA_NAO_ENCONTRADA"
    assert client.delete(f"/api/aulas/{aula.id}").status_code == 404
    assert client.get("/api/aulas").json() == []


def test_note_limit(client, db):
    make_user(db, "ana")
    login(client, "ana")
    turma, disciplina = _catalog(client)
    r = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                        "lesson_date": "2026-09-22", "note": "x" * 2001})
    assert r.status_code == 422


def test_error_message_in_payload(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="ERROR")
    aula.error_code = "AUDIO_TOO_SHORT"
    db.commit()
    login(client, "ana")
    body = client.get(f"/api/aulas/{aula.id}").json()
    assert body["error_message"].startswith("O áudio tem menos de 1 minuto")


def test_delete_removes_files_and_hides_aula(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_VALIDATED")
    login(client, "ana")
    ensure_dirs()
    for rel in ("original/a.wav", "original/b.wav"):
        abs_path(rel).write_bytes(b"RIFF")
    db.add(Audio(aula_id=aula.id, original_filename="a.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/a.wav", mime_type="audio/wav", size_bytes=4, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.add(AudioUpload(aula_id=aula.id, original_filename="b.wav", internal_filename=f"{uuid.uuid4()}.wav",
                       path="original/b.wav", size_bytes=4, sha256="0" * 64))
    db.commit()
    assert client.delete(f"/api/aulas/{aula.id}").status_code == 204
    assert not (store_root() / "original" / "a.wav").exists()
    assert not (store_root() / "original" / "b.wav").exists()
    db.expire_all()
    assert db.get(Aula, aula.id).deleted_at is not None
    assert db.query(AudioUpload).count() == 0
    assert client.get(f"/api/aulas/{aula.id}").status_code == 404


def test_delete_blocked_while_job_active(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    db.add(Job(type="validate_audio", aula_id=aula.id, status="queued"))
    db.commit()
    login(client, "ana")
    r = client.delete(f"/api/aulas/{aula.id}")
    assert r.status_code == 409 and r.json()["error_code"] == "AULA_BUSY"


def test_storage_rejects_paths_outside_root():
    import pytest
    with pytest.raises(ValueError):
        abs_path("../../etc/passwd")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_messages.py tests/test_aulas.py`
Expected: ERROR (`No module named 'app.core.messages'`).

- [ ] **Step 3: Implementar `app/core/messages.py`**

```python
from app.core.config import get_settings

_FORMAT = ("Este arquivo não parece ser um áudio MP3, WAV, M4A, AAC ou FLAC. "
           "Tente exportar o áudio novamente no gravador.")


def format_duration(seconds: int) -> str:
    minutes = seconds // 60
    hours, rest = divmod(minutes, 60)
    if hours == 0:
        return "1 minuto" if minutes == 1 else f"{minutes} minutos"
    return f"{hours}h" if rest == 0 else f"{hours}h{rest:02d}"


def format_size(num_bytes: int) -> str:
    gb = num_bytes / 1024 ** 3
    if gb >= 1:
        text = f"{gb:.1f}".rstrip("0").rstrip(".")
        return f"{text.replace('.', ',')} GB"
    return f"{round(num_bytes / 1024 ** 2)} MB"


def error_message(code: str | None) -> str | None:
    if code is None:
        return None
    s = get_settings()
    messages = {
        "AUDIO_FORMAT_MISMATCH": _FORMAT,
        "AUDIO_UNSUPPORTED_FORMAT": _FORMAT,
        "AUDIO_TOO_LONG": (f"O áudio tem mais de {format_duration(s.max_audio_seconds)}. "
                           "Divida a gravação e envie cada parte como uma aula."),
        "AUDIO_TOO_SHORT": (f"O áudio tem menos de {format_duration(s.min_audio_seconds)}. "
                            "Verifique se é o arquivo certo."),
        "AUDIO_CORRUPTED": ("Não conseguimos ler este arquivo. Ele pode estar incompleto; "
                            "tente copiá-lo de novo do gravador."),
        "AUDIO_TOO_LARGE": (f"O arquivo passa de {format_size(s.max_upload_bytes)}. Tente exportar o "
                            "áudio em MP3 ou M4A, que ocupam menos espaço."),
        "AUDIO_LOCKED": "A análise desta aula já começou. Para usar outro áudio, crie uma nova aula.",
        "JOB_FAILED": ("Algo deu errado ao preparar sua aula. Tente processar novamente; "
                       "se continuar, avise o administrador."),
    }
    return messages.get(code, "Algo deu errado. Tente novamente.")
```

- [ ] **Step 4: Implementar `app/audio/storage.py`**

`app/audio/__init__.py`: vazio.

```python
from pathlib import Path

from app.core.config import get_settings


def store_root() -> Path:
    return get_settings().audio_store


def ensure_dirs() -> None:
    for sub in ("tmp", "original"):
        (store_root() / sub).mkdir(parents=True, exist_ok=True)


def abs_path(rel: str) -> Path:
    root = store_root().resolve()
    path = (root / rel).resolve()
    if root not in path.parents:
        raise ValueError("caminho fora do armazenamento de áudio")
    return path


def delete_file(rel: str) -> None:
    abs_path(rel).unlink(missing_ok=True)
```

- [ ] **Step 5: Implementar `app/aulas/service.py` e `app/aulas/routes.py`**

`app/aulas/__init__.py`: vazio.

`app/aulas/service.py`:
```python
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import last_admin_change
from app.core.errors import AppError
from app.core.messages import error_message
from app.models import Audio, AudioUpload, Aula, Disciplina, Job, Processamento, Turma, utcnow


def get_owned_aula(db: Session, actor, aula_id: uuid.UUID) -> Aula:
    aula = db.scalar(select(Aula).where(Aula.id == aula_id, Aula.professor_id == actor.effective_professor_id,
                                        Aula.deleted_at.is_(None)))
    if aula is None:
        raise AppError(404, "AULA_NAO_ENCONTRADA", "Aula não encontrada.")
    return aula


def has_active_job(db: Session, aula_id: uuid.UUID) -> bool:
    return db.scalar(select(Job.id).where(Job.aula_id == aula_id, Job.status.in_(("queued", "running")))
                     .limit(1)) is not None


def current_audio(db: Session, aula_id: uuid.UUID) -> Audio | None:
    return db.scalar(select(Audio).where(Audio.aula_id == aula_id, Audio.is_original.is_(True),
                                         Audio.deleted_at.is_(None)))


def pending_upload(db: Session, aula_id: uuid.UUID) -> AudioUpload | None:
    return db.scalar(select(AudioUpload).where(AudioUpload.aula_id == aula_id))


def aula_summary(aula: Aula, turma: Turma, disciplina: Disciplina) -> dict:
    return {"id": str(aula.id), "lesson_date": aula.lesson_date.isoformat(), "status": aula.status,
            "turma": {"id": str(turma.id), "name": turma.name},
            "disciplina": {"id": str(disciplina.id), "name": disciplina.name}}


def aula_payload(db: Session, aula: Aula) -> dict:
    audio, upload = current_audio(db, aula.id), pending_upload(db, aula.id)
    changed = last_admin_change(db, aula.id)
    return {
        **aula_summary(aula, db.get(Turma, aula.turma_id), db.get(Disciplina, aula.disciplina_id)),
        "note": aula.note,
        "error_code": aula.error_code,
        "error_message": error_message(aula.error_code),
        "audio": None if audio is None else {
            "original_filename": audio.original_filename, "mime_type": audio.mime_type,
            "size_bytes": audio.size_bytes, "duration_ms": audio.duration_ms,
            "channels": audio.channels, "sample_rate": audio.sample_rate},
        "upload_pendente": None if upload is None else {
            "original_filename": upload.original_filename, "size_bytes": upload.size_bytes},
        "job_ativo": has_active_job(db, aula.id),
        "alterada_pelo_admin_em": changed.isoformat() if changed else None,
    }


def soft_delete_aula(db: Session, aula: Aula) -> list[str]:
    now, paths = utcnow(), []
    for audio in db.scalars(select(Audio).where(Audio.aula_id == aula.id, Audio.deleted_at.is_(None))):
        audio.deleted_at = now
        paths.append(audio.path)
    upload = pending_upload(db, aula.id)
    if upload is not None:
        paths.append(upload.path)
        db.delete(upload)
    db.execute(update(Processamento).where(Processamento.aula_id == aula.id,
                                           Processamento.deleted_at.is_(None)).values(deleted_at=now))
    aula.deleted_at = now
    return paths
```

`app/aulas/routes.py`:
```python
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio.storage import delete_file
from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import (aula_payload, aula_summary, get_owned_aula, has_active_job,
                               soft_delete_aula)
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Aula, Disciplina, Turma

router = APIRouter()


class AulaIn(BaseModel):
    turma_id: uuid.UUID
    disciplina_id: uuid.UUID
    lesson_date: date
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


def _owned(db: Session, model, obj_id: uuid.UUID, professor_id: uuid.UUID):
    obj = db.get(model, obj_id)
    return obj if obj is not None and obj.deleted_at is None and obj.professor_id == professor_id else None


@router.post("/aulas", status_code=201)
def create_aula(body: AulaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    professor_id = actor.effective_professor_id
    if _owned(db, Turma, body.turma_id, professor_id) is None:
        raise AppError(422, "TURMA_INVALIDA", "Escolha uma das suas turmas.")
    if _owned(db, Disciplina, body.disciplina_id, professor_id) is None:
        raise AppError(422, "DISCIPLINA_INVALIDA", "Escolha uma das suas disciplinas.")
    aula = Aula(professor_id=professor_id, turma_id=body.turma_id, disciplina_id=body.disciplina_id,
                lesson_date=body.lesson_date, note=body.note or None, status="DRAFT")
    db.add(aula)
    db.flush()
    audit(db, actor, "aula", aula.id, "create")
    db.commit()
    log_event("aula_created", aula_id=aula.id)
    return aula_payload(db, aula)


@router.get("/aulas")
def list_aulas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Aula, Turma, Disciplina)
        .join(Turma, Turma.id == Aula.turma_id).join(Disciplina, Disciplina.id == Aula.disciplina_id)
        .where(Aula.professor_id == actor.effective_professor_id, Aula.deleted_at.is_(None))
        .order_by(Aula.lesson_date.desc(), Aula.created_at.desc())).all()
    audit(db, actor, "aula", None, "read")
    db.commit()
    return [aula_summary(a, t, d) for a, t, d in rows]


@router.get("/aulas/{aula_id}")
def get_aula(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    return aula_payload(db, aula)


@router.delete("/aulas/{aula_id}", status_code=204)
def delete_aula(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if has_active_job(db, aula.id):
        raise AppError(409, "AULA_BUSY", "Aguarde o processamento terminar para excluir a aula.")
    paths = soft_delete_aula(db, aula)
    audit(db, actor, "aula", aula.id, "delete")
    db.commit()
    for rel in paths:
        delete_file(rel)
    log_event("aula_deleted", aula_id=aula.id)
```

Em `app/main.py`, dentro de `create_app()`:
```python
    from app.aulas.routes import router as aulas_router
    app.include_router(aulas_router, prefix="/api")
```

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): aulas com exclusão física dos áudios e mensagens de erro humanas

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Upload do áudio em streaming, substituição e reprodução

**Files:**
- Create: `backend/app/audio/routes.py`
- Modify: `backend/app/main.py` (incluir o router de áudio)
- Create: `backend/tests/audio_fixtures.py`
- Test: `backend/tests/test_audio_upload.py`

**Interfaces:**
- Consumes: `get_owned_aula`, `aula_payload`, `has_active_job`, `pending_upload`, `current_audio` (Task 7); `store_root`, `ensure_dirs`, `abs_path`, `delete_file` (Task 7); `error_message` (Task 7); `audit` (Task 5).
- Produces: `app.audio.routes`: `ALLOWED_EXTENSIONS = {"mp3","wav","m4a","aac","flac"}`, `UPLOAD_STATUSES = {"DRAFT","AUDIO_IMPORTED","AUDIO_VALIDATED","ERROR"}`, `sanitize_filename(raw: str) -> str`, `extension_of(name: str) -> str`; rotas `PUT /api/aulas/{id}/audio` (corpo binário, cabeçalho `X-Filename` com o nome percent-encoded; 201 com `aula_payload`) e `GET /api/aulas/{id}/audio` (arquivo original, suporta `Range`).
- Produces (testes): `tests/audio_fixtures.make_audio(path: Path, seconds: float = 65, fmt: str = "wav") -> Path` (gera tom senoidal com ffmpeg; `fmt` em `wav|flac|mp3|m4a|aac`) e `upload(client, aula_id, path, filename=None)`.

- [ ] **Step 1: Escrever os testes (falham)**

`backend/tests/audio_fixtures.py`:
```python
import subprocess  # nosec B404 - geração de áudio de teste
from pathlib import Path
from urllib.parse import quote

_CODECS = {
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "mp3": ["-c:a", "libmp3lame"],
    "m4a": ["-c:a", "aac"],
    "aac": ["-c:a", "aac", "-f", "adts"],
}


def make_audio(path: Path, seconds: float = 65, fmt: str = "wav") -> Path:
    subprocess.run(  # nosec B603 B607 - argumentos fixos em lista
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-ac", "1", "-ar", "16000", *_CODECS[fmt], str(path)], check=True)
    return path


def upload(client, aula_id, path: Path, filename: str | None = None):
    return client.put(f"/api/aulas/{aula_id}/audio", content=path.read_bytes(),
                      headers={"X-Filename": quote(filename or path.name),
                               "Content-Type": "application/octet-stream"})
```

`backend/tests/test_audio_upload.py`:
```python
import hashlib
import stat
import uuid

import pytest

from app.audio.routes import sanitize_filename
from app.audio.storage import store_root
from app.core.config import get_settings
from app.models import Audio, AudioUpload
from tests.audio_fixtures import make_audio, upload
from tests.helpers import login, make_aula, make_user


@pytest.mark.parametrize("raw,clean", [
    ("aula%201.wav", "aula 1.wav"),
    ("..%2F..%2Fetc%2Fpasswd.wav", "passwd.wav"),
    ("..%5C..%5Cwin.ini.mp3", "win.ini.mp3"),
    ("%00%0A.wav", "wav"),
    ("", "audio"),
])
def test_sanitize_filename(raw, clean):
    assert sanitize_filename(raw) == clean


def test_upload_success(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    src = make_audio(tmp_path / "gravação.wav")
    r = upload(client, aula.id, src)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "AUDIO_IMPORTED"
    assert body["upload_pendente"] == {"original_filename": "gravação.wav", "size_bytes": src.stat().st_size}
    row = db.query(AudioUpload).one()
    stored = store_root() / row.path
    assert row.path.startswith("original/") and row.internal_filename.endswith(".wav")
    assert uuid.UUID(row.internal_filename.split(".")[0])
    assert row.sha256 == hashlib.sha256(src.read_bytes()).hexdigest()
    assert not stored.stat().st_mode & stat.S_IWUSR
    assert list((store_root() / "tmp").iterdir()) == []


def test_traversal_name_never_used_as_path(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"), filename="../../etc/passwd.wav")
    assert r.status_code == 201
    row = db.query(AudioUpload).one()
    assert row.original_filename == "passwd.wav" and ".." not in row.path


def test_unsupported_extension(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"), filename="virus.exe")
    assert r.status_code == 415 and r.json()["error_code"] == "AUDIO_UNSUPPORTED_FORMAT"


def test_too_large_rejected_and_cleaned(client, db, tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")
    get_settings.cache_clear()
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"))
    assert r.status_code == 413 and r.json()["error_code"] == "AUDIO_TOO_LARGE"
    assert db.query(AudioUpload).count() == 0
    assert not (store_root() / "tmp").exists() or list((store_root() / "tmp").iterdir()) == []


def test_empty_file_rejected(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = client.put(f"/api/aulas/{aula.id}/audio", content=b"", headers={"X-Filename": "a.wav"})
    assert r.status_code == 422 and r.json()["error_code"] == "AUDIO_EMPTY"


def test_replacement_deletes_previous_files(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    upload(client, aula.id, make_audio(tmp_path / "a.wav"))
    first = db.query(AudioUpload).one().path
    upload(client, aula.id, make_audio(tmp_path / "b.wav", seconds=70))
    db.expire_all()
    rows = db.query(AudioUpload).all()
    assert len(rows) == 1 and rows[0].path != first
    assert not (store_root() / first).exists()


def test_replacement_soft_deletes_validated_audio(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_VALIDATED")
    (store_root() / "original").mkdir(parents=True, exist_ok=True)
    (store_root() / "original" / "velho.wav").write_bytes(b"x")
    db.add(Audio(aula_id=aula.id, original_filename="velho.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/velho.wav", mime_type="audio/wav", size_bytes=1, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.commit()
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "novo.wav"))
    assert r.status_code == 201 and r.json()["status"] == "AUDIO_IMPORTED" and r.json()["audio"] is None
    assert not (store_root() / "original" / "velho.wav").exists()


def test_upload_locked_after_analysis_started(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="TRANSCRIBING")
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"))
    assert r.status_code == 409 and r.json()["error_code"] == "AUDIO_LOCKED"


def test_upload_to_other_professor_aula_is_404(client, db, tmp_path):
    make_user(db, "ana")
    aula = make_aula(db, make_user(db, "bia"))
    login(client, "ana")
    assert upload(client, aula.id, make_audio(tmp_path / "x.wav")).status_code == 404


def test_playback_requires_validated_audio_and_supports_range(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_VALIDATED")
    login(client, "ana")
    assert client.get(f"/api/aulas/{aula.id}/audio").status_code == 404
    (store_root() / "original").mkdir(parents=True, exist_ok=True)
    (store_root() / "original" / "ok.wav").write_bytes(b"0123456789")
    db.add(Audio(aula_id=aula.id, original_filename="ok.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/ok.wav", mime_type="audio/wav", size_bytes=10, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.commit()
    r = client.get(f"/api/aulas/{aula.id}/audio")
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/wav")
    r = client.get(f"/api/aulas/{aula.id}/audio", headers={"Range": "bytes=0-3"})
    assert r.status_code == 206 and r.content == b"0123"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_audio_upload.py`
Expected: ERROR (`No module named 'app.audio.routes'`).

- [ ] **Step 3: Implementar `app/audio/routes.py`**

```python
import hashlib
import os
import uuid
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio.storage import abs_path, delete_file, ensure_dirs, store_root
from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import aula_payload, current_audio, get_owned_aula, has_active_job, pending_upload
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.core.messages import error_message
from app.models import Audio, AudioUpload, Aula, utcnow

router = APIRouter()

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "aac", "flac"}
UPLOAD_STATUSES = {"DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "ERROR"}


def sanitize_filename(raw: str) -> str:
    name = unquote(raw).replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip().strip(".")
    return name[:255] or "audio"


def extension_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _too_large() -> AppError:
    return AppError(413, "AUDIO_TOO_LARGE", error_message("AUDIO_TOO_LARGE"))


def _detach_previous(db: Session, aula: Aula) -> list[str]:
    """Remove o upload pendente e marca o áudio validado como excluído; devolve arquivos a apagar."""
    paths = []
    upload = pending_upload(db, aula.id)
    if upload is not None:
        paths.append(upload.path)
        db.delete(upload)
    for audio in db.scalars(select(Audio).where(Audio.aula_id == aula.id, Audio.deleted_at.is_(None))):
        audio.deleted_at = utcnow()
        paths.append(audio.path)
    return paths


@router.put("/aulas/{aula_id}/audio", status_code=201)
async def upload_audio(aula_id: uuid.UUID, request: Request, actor: Actor = Depends(current_actor),
                       db: Session = Depends(get_db)):
    s = get_settings()
    aula = get_owned_aula(db, actor, aula_id)
    if aula.status not in UPLOAD_STATUSES:
        raise AppError(409, "AUDIO_LOCKED", error_message("AUDIO_LOCKED"))
    if has_active_job(db, aula.id):
        raise AppError(409, "AULA_BUSY", "Aguarde o processamento atual terminar.")
    original = sanitize_filename(request.headers.get("X-Filename", ""))
    ext = extension_of(original)
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(415, "AUDIO_UNSUPPORTED_FORMAT", error_message("AUDIO_UNSUPPORTED_FORMAT"))
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > s.max_upload_bytes:
        raise _too_large()

    ensure_dirs()
    internal = f"{uuid.uuid4()}.{ext}"
    tmp, final_rel = store_root() / "tmp" / internal, f"original/{internal}"
    digest, size = hashlib.sha256(), 0
    try:
        with tmp.open("wb") as fh:
            async for chunk in request.stream():
                size += len(chunk)
                if size > s.max_upload_bytes:
                    raise _too_large()
                digest.update(chunk)
                fh.write(chunk)
        if size == 0:
            raise AppError(422, "AUDIO_EMPTY", "O arquivo enviado está vazio.")
        os.replace(tmp, abs_path(final_rel))
        os.chmod(abs_path(final_rel), 0o440)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    old_paths = _detach_previous(db, aula)
    db.add(AudioUpload(aula_id=aula.id, original_filename=original, internal_filename=internal,
                       path=final_rel, size_bytes=size, sha256=digest.hexdigest()))
    aula.status, aula.error_code = "AUDIO_IMPORTED", None
    audit(db, actor, "aula", aula.id, "upload")
    db.commit()
    for rel in old_paths:
        delete_file(rel)
    log_event("audio_uploaded", aula_id=aula.id)
    return aula_payload(db, aula)


@router.get("/aulas/{aula_id}/audio")
def play_audio(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    audio = current_audio(db, aula.id)
    if audio is None:
        raise AppError(404, "AUDIO_NAO_ENCONTRADO", "Esta aula ainda não tem áudio conferido.")
    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    return FileResponse(abs_path(audio.path), media_type=audio.mime_type, content_disposition_type="inline")
```

Em `app/main.py`, dentro de `create_app()`:
```python
    from app.audio.routes import router as audio_router
    app.include_router(audio_router, prefix="/api")
```

Nota: o suporte a `Range` vem do `FileResponse` do Starlette (≥ 0.39). Se o teste de `Range` falhar por versão, fixar `starlette>=0.40` em `pyproject.toml` e rebuildar (`--build`).

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): upload do áudio em streaming com SHA-256, substituição segura e reprodução

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Fila de jobs, worker e validação do áudio com ffprobe

**Files:**
- Create: `backend/app/audio/probe.py`, `backend/app/audio/validation.py`
- Create: `backend/app/jobs/__init__.py`, `backend/app/jobs/queue.py`, `backend/app/jobs/handlers.py`, `backend/app/jobs/worker.py`
- Modify: `backend/app/aulas/routes.py` (rota `POST /aulas/{id}/processar`)
- Test: `backend/tests/test_validation.py`, `backend/tests/test_jobs.py`

**Interfaces:**
- Consumes: `AudioUpload`, `Audio`, `Aula`, `Job` (Task 2); `has_active_job`, `pending_upload`, `get_owned_aula`, `aula_payload` (Task 7); `abs_path`, `delete_file` (Task 7); `audit` (Task 5); `make_audio`, `upload` (Task 8).
- Produces: `app.audio.probe.ProbeResult(format_name, codec, duration_ms, channels, sample_rate)`, `ProbeError`, `probe(path: Path) -> ProbeResult`.
- Produces: `app.audio.validation.FORMATS` (extensão → formatos ffprobe aceitos, codecs aceitos ou `None`, MIME), `ValidationFailed(code)`, `check(ext: str, result: ProbeResult) -> str` (devolve o MIME).
- Produces: `app.jobs.queue`: `enqueue(db, aula_id, job_type) -> Job`, `claim_next(db) -> Job | None`, `recover_stale(db) -> None`, `finish_job(db, job)`, `fail_job(db, job, code)`.
- Produces: `app.jobs.handlers.HANDLERS = {"validate_audio": handle_validate_audio}`; `app.jobs.worker.run_once(db) -> bool` e `main()` (`python -m app.jobs.worker`).
- Produces rota: `POST /api/aulas/{id}/processar` → 202 com `aula_payload` (`job_ativo: true`); 409 `AULA_STATE` se não houver upload pendente; 409 `AULA_BUSY` com job ativo.

- [ ] **Step 1: Escrever os testes (falham)**

`backend/tests/test_validation.py`:
```python
import shutil

import pytest

from app.audio.probe import ProbeError, probe
from app.audio.validation import ValidationFailed, check
from app.core.config import get_settings
from tests.audio_fixtures import make_audio


@pytest.mark.parametrize("fmt,mime", [("wav", "audio/wav"), ("flac", "audio/flac"), ("mp3", "audio/mpeg"),
                                      ("m4a", "audio/mp4"), ("aac", "audio/aac")])
def test_valid_formats(tmp_path, fmt, mime):
    result = probe(make_audio(tmp_path / f"a.{fmt}", fmt=fmt))
    assert 60_000 <= result.duration_ms <= 70_000  # AAC/ADTS estima pela taxa de bits and result.channels == 1 and result.sample_rate == 16000
    assert check(fmt, result) == mime


def test_fake_extension_is_mismatch(tmp_path):
    flac = make_audio(tmp_path / "a.flac", fmt="flac")
    fake = tmp_path / "a.mp3"
    shutil.copy(flac, fake)
    with pytest.raises(ValidationFailed) as e:
        check("mp3", probe(fake))
    assert e.value.code == "AUDIO_FORMAT_MISMATCH"


def test_non_audio_file_raises_probe_error(tmp_path):
    fake = tmp_path / "a.wav"
    fake.write_text("isto não é áudio")
    with pytest.raises(ProbeError):
        probe(fake)


def test_duration_limits(tmp_path, monkeypatch):
    with pytest.raises(ValidationFailed) as e:
        check("wav", probe(make_audio(tmp_path / "curto.wav", seconds=5)))
    assert e.value.code == "AUDIO_TOO_SHORT"
    monkeypatch.setenv("MAX_AUDIO_SECONDS", "61")
    get_settings.cache_clear()
    with pytest.raises(ValidationFailed) as e:
        check("wav", probe(make_audio(tmp_path / "longo.wav", seconds=65)))
    assert e.value.code == "AUDIO_TOO_LONG"
    get_settings.cache_clear()
```

`backend/tests/test_jobs.py`:
```python
import shutil
from datetime import timedelta

from app.audio.storage import store_root
from app.jobs import queue
from app.jobs.worker import run_once
from app.models import Audio, AudioUpload, Aula, Job, utcnow
from tests.audio_fixtures import make_audio, upload
from tests.helpers import login, make_aula, make_user


def _processar(client, db, tmp_path, src):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    assert upload(client, aula.id, src).status_code == 201
    r = client.post(f"/api/aulas/{aula.id}/processar")
    assert r.status_code == 202 and r.json()["job_ativo"] is True
    return aula


def test_valid_audio_reaches_audio_validated(client, db, tmp_path):
    aula = _processar(client, db, tmp_path, make_audio(tmp_path / "aula.wav"))
    assert run_once(db) is True
    body = client.get(f"/api/aulas/{aula.id}").json()
    assert body["status"] == "AUDIO_VALIDATED" and body["job_ativo"] is False
    assert body["audio"]["mime_type"] == "audio/wav" and body["audio"]["channels"] == 1
    assert db.query(AudioUpload).count() == 0
    audio = db.query(Audio).one()
    assert audio.is_original and audio.derived_from_audio_id is None and (store_root() / audio.path).exists()


def test_fake_extension_ends_in_error_and_file_removed(client, db, tmp_path):
    flac = make_audio(tmp_path / "a.flac", fmt="flac")
    fake = tmp_path / "gravacao.mp3"
    shutil.copy(flac, fake)
    aula = _processar(client, db, tmp_path, fake)
    path = db.query(AudioUpload).one().path
    run_once(db)
    body = client.get(f"/api/aulas/{aula.id}").json()
    assert body["status"] == "ERROR" and body["error_code"] == "AUDIO_FORMAT_MISMATCH"
    assert body["error_message"].startswith("Este arquivo não parece ser um áudio")
    assert not (store_root() / path).exists()


def test_non_audio_is_corrupted(client, db, tmp_path):
    fake = tmp_path / "a.wav"
    fake.write_text("texto")
    aula = _processar(client, db, tmp_path, fake)
    run_once(db)
    assert client.get(f"/api/aulas/{aula.id}").json()["error_code"] == "AUDIO_CORRUPTED"


def test_processar_requires_pending_upload_and_no_active_job(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = client.post(f"/api/aulas/{aula.id}/processar")
    assert r.status_code == 409 and r.json()["error_code"] == "AULA_STATE"
    upload(client, aula.id, make_audio(tmp_path / "a.wav"))
    client.post(f"/api/aulas/{aula.id}/processar")
    r = client.post(f"/api/aulas/{aula.id}/processar")
    assert r.status_code == 409 and r.json()["error_code"] == "AULA_BUSY"


def test_run_once_without_jobs(db):
    assert run_once(db) is False


def test_stale_job_is_requeued_then_failed(db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    job = Job(type="validate_audio", aula_id=aula.id, status="running", attempts=1,
              locked_at=utcnow() - timedelta(minutes=31))
    db.add(job)
    db.commit()
    queue.recover_stale(db)
    db.refresh(job)
    assert job.status == "queued" and job.locked_at is None
    job.status, job.attempts, job.locked_at = "running", 3, utcnow() - timedelta(minutes=31)
    db.commit()
    queue.recover_stale(db)
    db.refresh(job)
    assert job.status == "failed" and job.error_code == "JOB_FAILED"
    assert db.get(Aula, aula.id).status == "ERROR"


def test_handler_exception_is_retried(db, monkeypatch):
    from app.jobs import handlers
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    db.add(Job(type="validate_audio", aula_id=aula.id))
    db.commit()

    def boom(db_, job_):
        raise RuntimeError("falha simulada")

    monkeypatch.setitem(handlers.HANDLERS, "validate_audio", boom)
    run_once(db)
    job = db.query(Job).one()
    assert job.status == "queued" and job.attempts == 1
    run_once(db)
    run_once(db)
    db.refresh(job)
    assert job.status == "failed" and db.get(Aula, aula.id).error_code == "JOB_FAILED"


def test_claim_skips_locked_rows(db):
    from app.core.db import SessionLocal, get_engine
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    db.add(Job(type="validate_audio", aula_id=aula.id))
    db.commit()
    with SessionLocal(bind=get_engine()) as other:
        from sqlalchemy import select
        other.scalar(select(Job).with_for_update())  # segura a linha
        assert queue.claim_next(db) is None
        other.rollback()
    assert queue.claim_next(db) is not None


def test_job_for_deleted_aula_is_closed(db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_IMPORTED")
    aula.deleted_at = utcnow()
    db.add(Job(type="validate_audio", aula_id=aula.id))
    db.commit()
    run_once(db)
    assert db.query(Job).one().status == "done"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_validation.py tests/test_jobs.py`
Expected: ERROR (`No module named 'app.audio.probe'`).

- [ ] **Step 3: Implementar `app/audio/probe.py` e `app/audio/validation.py`**

`app/audio/probe.py`:
```python
import json
import subprocess  # nosec B404 - ffprobe com argumentos em lista (prompt §57)
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    format_name: str
    codec: str
    duration_ms: int
    channels: int
    sample_rate: int


class ProbeError(Exception):
    pass


def probe(path: Path) -> ProbeResult:
    try:
        completed = subprocess.run(  # nosec B603 B607 - lista de argumentos, sem shell
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, timeout=120, check=True)
        data = json.loads(completed.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ProbeError("arquivo ilegível") from exc
    fmt = data.get("format") or {}
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if stream is None or "format_name" not in fmt:
        raise ProbeError("sem stream de áudio")
    try:
        duration = float(fmt.get("duration") or stream.get("duration") or 0)
        return ProbeResult(format_name=fmt["format_name"], codec=stream.get("codec_name", ""),
                           duration_ms=int(round(duration * 1000)), channels=int(stream.get("channels", 0)),
                           sample_rate=int(stream.get("sample_rate", 0)))
    except (TypeError, ValueError) as exc:
        raise ProbeError("metadados inválidos") from exc
```

`app/audio/validation.py`:
```python
from app.audio.probe import ProbeResult
from app.core.config import get_settings

# extensão → (format_name aceitos pelo ffprobe, codecs aceitos ou None, MIME gravado)
FORMATS = {
    "mp3": ({"mp3"}, None, "audio/mpeg"),
    "wav": ({"wav"}, None, "audio/wav"),
    "m4a": ({"mov,mp4,m4a,3gp,3g2,mj2"}, {"aac", "alac"}, "audio/mp4"),
    "aac": ({"aac"}, None, "audio/aac"),
    "flac": ({"flac"}, None, "audio/flac"),
}


class ValidationFailed(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def check(ext: str, result: ProbeResult) -> str:
    s = get_settings()
    if ext not in FORMATS:
        raise ValidationFailed("AUDIO_UNSUPPORTED_FORMAT")
    formats, codecs, mime = FORMATS[ext]
    if result.format_name not in formats or (codecs is not None and result.codec not in codecs):
        raise ValidationFailed("AUDIO_FORMAT_MISMATCH")
    if result.channels < 1 or result.sample_rate < 8000 or result.duration_ms <= 0:
        raise ValidationFailed("AUDIO_CORRUPTED")
    if result.duration_ms < s.min_audio_seconds * 1000:
        raise ValidationFailed("AUDIO_TOO_SHORT")
    if result.duration_ms > s.max_audio_seconds * 1000:
        raise ValidationFailed("AUDIO_TOO_LONG")
    return mime
```

- [ ] **Step 4: Implementar a fila, o handler e o worker**

`app/jobs/__init__.py`: vazio.

`app/jobs/queue.py`:
```python
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Aula, Job, utcnow


def enqueue(db: Session, aula_id: uuid.UUID, job_type: str) -> Job:
    job = Job(type=job_type, aula_id=aula_id, status="queued")
    db.add(job)
    db.flush()
    return job


def claim_next(db: Session) -> Job | None:
    job = db.scalar(select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1)
                    .with_for_update(skip_locked=True))
    if job is None:
        db.rollback()
        return None
    job.status, job.locked_at, job.attempts = "running", utcnow(), job.attempts + 1
    db.commit()
    return job


def finish_job(db: Session, job: Job) -> None:
    job.status, job.finished_at = "done", utcnow()


def fail_job(db: Session, job: Job, code: str) -> None:
    job.status, job.error_code, job.finished_at = "failed", code, utcnow()
    aula = db.get(Aula, job.aula_id)
    if aula is not None and aula.deleted_at is None:
        aula.status, aula.error_code = "ERROR", code


def recover_stale(db: Session) -> None:
    s = get_settings()
    limit = utcnow() - timedelta(minutes=s.job_stale_minutes)
    stale = db.scalars(select(Job).where(Job.status == "running", Job.locked_at < limit)
                       .with_for_update(skip_locked=True)).all()
    for job in stale:
        if job.attempts >= s.job_max_attempts:
            fail_job(db, job, "JOB_FAILED")
        else:
            job.status, job.locked_at = "queued", None
    db.commit()
```

`app/jobs/handlers.py`:
```python
import uuid

from sqlalchemy.orm import Session

from app.audio.probe import ProbeError, probe
from app.audio.storage import abs_path, delete_file
from app.audio.validation import ValidationFailed, check
from app.aulas.service import pending_upload
from app.core.logging import log_event
from app.jobs.queue import finish_job
from app.models import Audio, Aula, Job


def handle_validate_audio(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    upload = pending_upload(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or upload is None:
        finish_job(db, job)
        db.commit()
        return
    ext = upload.internal_filename.rsplit(".", 1)[-1]
    try:
        result = probe(abs_path(upload.path))
        mime = check(ext, result)
    except ProbeError:
        code = "AUDIO_CORRUPTED"
    except ValidationFailed as exc:
        code = exc.code
    else:
        db.add(Audio(id=uuid.uuid4(), aula_id=aula.id, original_filename=upload.original_filename,
                     internal_filename=upload.internal_filename, path=upload.path, mime_type=mime,
                     size_bytes=upload.size_bytes, duration_ms=result.duration_ms, sha256=upload.sha256,
                     channels=result.channels, sample_rate=result.sample_rate, is_original=True,
                     derived_from_audio_id=None))
        db.delete(upload)
        aula.status, aula.error_code = "AUDIO_VALIDATED", None
        finish_job(db, job)
        db.commit()
        log_event("audio_validated", aula_id=aula.id, job_id=job.id)
        return
    rel = upload.path
    db.delete(upload)
    aula.status, aula.error_code = "ERROR", code
    finish_job(db, job)
    db.commit()
    delete_file(rel)
    log_event("audio_rejected", aula_id=aula.id, job_id=job.id, error_code=code)


HANDLERS = {"validate_audio": handle_validate_audio}
```

`app/jobs/worker.py`:
```python
import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.core.logging import configure_logging, log_event
from app.jobs import handlers
from app.jobs.queue import claim_next, fail_job, recover_stale
from app.models import Job


def run_once(db: Session) -> bool:
    recover_stale(db)
    job = claim_next(db)
    if job is None:
        return False
    job_id = job.id
    try:
        handlers.HANDLERS[job.type](db, job)
    except Exception as exc:  # o worker nunca pode morrer por causa de um job
        db.rollback()
        job = db.get(Job, job_id)
        log_event("job_error", level=logging.ERROR, job_id=job_id, error_type=type(exc).__name__,
                  attempt=job.attempts)
        if job.attempts >= get_settings().job_max_attempts:
            fail_job(db, job, "JOB_FAILED")
        else:
            job.status, job.locked_at = "queued", None
        db.commit()
    return True


def main() -> None:
    configure_logging()
    log_event("worker_started")
    while True:
        with SessionLocal(bind=get_engine()) as db:
            worked = run_once(db)
        if not worked:
            time.sleep(get_settings().job_poll_seconds)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Rota `processar` em `app/aulas/routes.py`**

Acrescentar ao import de `app.aulas.service` o nome `pending_upload`, acrescentar `from app.jobs.queue import enqueue` e, ao fim do arquivo:
```python
@router.post("/aulas/{aula_id}/processar", status_code=202)
def processar_aula(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if has_active_job(db, aula.id):
        raise AppError(409, "AULA_BUSY", "Esta aula já está sendo preparada.")
    if aula.status != "AUDIO_IMPORTED" or pending_upload(db, aula.id) is None:
        raise AppError(409, "AULA_STATE", "Envie o áudio da aula antes de processar.")
    enqueue(db, aula.id, "validate_audio")
    audit(db, actor, "aula", aula.id, "process")
    db.commit()
    log_event("aula_processing_requested", aula_id=aula.id)
    return aula_payload(db, aula)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): fila de jobs no PostgreSQL, worker e validação do áudio com ffprobe

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Administração de contas, aulas de todos os professores e fluxo "agir como"

**Files:**
- Modify: `backend/app/admin/routes.py` (acrescentar rotas de contas e aulas)
- Test: `backend/tests/test_admin_contas.py`, `backend/tests/test_admin_act_as_flow.py`

**Interfaces:**
- Consumes: `create_professor`, `normalize_username` (Task 3); `generate_provisional_password`, `hash_password` (Task 3); `delete_all_sessions` (Task 4); `record` (Task 5); `soft_delete_aula`, `aula_summary` (Task 7); `delete_file` (Task 7).
- Produces rotas (prefixo `/api/admin`):
  - `GET /contas` → `[conta]`, `conta = {"id","username","display_name","role","is_active","must_change_password","created_at"}`.
  - `POST /contas` `{"username","display_name","role"?: "PROFESSOR"|"ADMIN_LOCAL"}` → 201 `{"conta": conta, "senha_provisoria": str}`.
  - `PATCH /contas/{id}` `{"display_name"?, "is_active"?}` → conta (409 `PROPRIA_CONTA` / `ULTIMO_ADMIN` ao desativar).
  - `POST /contas/{id}/senha-provisoria` → `{"senha_provisoria": str}`.
  - `DELETE /contas/{id}` `{"confirmar_username"}` → 204 (422 `CONFIRMACAO_INVALIDA`; 409 `PROPRIA_CONTA` / `ULTIMO_ADMIN`).
  - `GET /aulas?professor_id=` → `[aula_summary + {"professor": {"id","display_name"}}]`.

- [ ] **Step 1: Escrever os testes (falham)**

`backend/tests/test_admin_contas.py`:
```python
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
    prof = make_user(db, "ana")
    ana = client_factory()
    login(ana, "ana")
    r = admin.patch(f"/api/admin/contas/{prof.id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert ana.get("/api/auth/me").status_code == 401
    assert ana.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 401
    assert admin.post("/api/admin/agir-como", json={"professor_id": str(prof.id)}).status_code == 200
    admin.delete("/api/admin/agir-como")
    admin.patch(f"/api/admin/contas/{prof.id}", json={"is_active": True})
    assert ana.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 200


def test_cannot_deactivate_self_or_last_admin(client_factory, db):
    admin = _admin(client_factory, db)
    me = db.query(Professor).filter_by(username="admin").one()
    r = admin.patch(f"/api/admin/contas/{me.id}", json={"is_active": False})
    assert r.status_code == 409 and r.json()["error_code"] == "PROPRIA_CONTA"
    other = make_user(db, "admin2", role="ADMIN_LOCAL")
    r = admin.patch(f"/api/admin/contas/{other.id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False


def test_reset_password(client_factory, db):
    admin = _admin(client_factory, db)
    prof = make_user(db, "ana")
    ana = client_factory()
    login(ana, "ana")
    r = admin.post(f"/api/admin/contas/{prof.id}/senha-provisoria")
    senha = r.json()["senha_provisoria"]
    assert ana.get("/api/auth/me").status_code == 401
    fresh = client_factory()
    login(fresh, "ana", senha)
    assert fresh.get("/api/auth/me").json()["must_change_password"] is True


def test_delete_account_requires_confirmation_and_removes_audio(client_factory, db):
    admin = _admin(client_factory, db)
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
```

`backend/tests/test_admin_act_as_flow.py`:
```python
from app.jobs.worker import run_once
from app.models import AcessoAdmin, Aula
from tests.audio_fixtures import make_audio, upload
from tests.helpers import login, make_user


def test_admin_creates_and_processes_aula_for_professor(client_factory, db, tmp_path):
    admin_user = make_user(db, "admin", role="ADMIN_LOCAL")
    prof = make_user(db, "ana")
    admin, ana = client_factory(), client_factory()
    login(admin, "admin")
    login(ana, "ana")
    admin.post("/api/admin/agir-como", json={"professor_id": str(prof.id)})
    escola = admin.post("/api/escolas", json={"name": "Escola X"}).json()
    turma = admin.post("/api/turmas", json={"name": "6º A", "escola_id": escola["id"]}).json()
    disciplina = admin.post("/api/disciplinas", json={"name": "História"}).json()
    aula = admin.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                          "lesson_date": "2026-09-22"}).json()
    assert upload(admin, aula["id"], make_audio(tmp_path / "a.wav")).status_code == 201
    assert admin.post(f"/api/aulas/{aula['id']}/processar").status_code == 202
    run_once(db)

    assert db.query(Aula).one().professor_id == prof.id
    seen_by_prof = ana.get(f"/api/aulas/{aula['id']}").json()
    assert seen_by_prof["status"] == "AUDIO_VALIDATED"
    assert seen_by_prof["alterada_pelo_admin_em"] is not None
    actions = {r.action for r in db.query(AcessoAdmin).filter_by(admin_id=admin_user.id, resource="aula")}
    assert {"create", "upload", "process"} <= actions


def test_professor_own_actions_are_not_flagged(client, db, tmp_path):
    make_user(db, "ana")
    login(client, "ana")
    escola = client.post("/api/escolas", json={"name": "Escola Y"}).json()
    turma = client.post("/api/turmas", json={"name": "6º B", "escola_id": escola["id"]}).json()
    disciplina = client.post("/api/disciplinas", json={"name": "Artes"}).json()
    aula = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                           "lesson_date": "2026-09-22"}).json()
    assert client.get(f"/api/aulas/{aula['id']}").json()["alterada_pelo_admin_em"] is None
    assert db.query(AcessoAdmin).count() == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_admin_contas.py tests/test_admin_act_as_flow.py`
Expected: FAIL (404 nas rotas `/api/admin/contas` e `/api/admin/aulas`).

- [ ] **Step 3: Acrescentar a `app/admin/routes.py`**

Substituir o bloco de imports do arquivo por:
```python
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.audio.storage import delete_file
from app.audit import record
from app.auth.deps import Actor, current_admin
from app.auth.passwords import generate_provisional_password, hash_password
from app.auth.routes import me_payload
from app.auth.sessions import delete_all_sessions
from app.aulas.service import aula_summary, soft_delete_aula
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Aula, Disciplina, Professor, Sessao, Turma, utcnow
from app.users.service import create_professor
```

E acrescentar ao fim do arquivo:
```python
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ContaIn(BaseModel):
    username: Annotated[str, StringConstraints(max_length=64)]
    display_name: DisplayName
    role: Literal["PROFESSOR", "ADMIN_LOCAL"] = "PROFESSOR"


class ContaPatch(BaseModel):
    display_name: DisplayName | None = None
    is_active: bool | None = None


class ExcluirIn(BaseModel):
    confirmar_username: Annotated[str, StringConstraints(max_length=64)]


def conta_out(p: Professor) -> dict:
    return {"id": str(p.id), "username": p.username, "display_name": p.display_name, "role": p.role,
            "is_active": p.is_active, "must_change_password": p.must_change_password,
            "created_at": p.created_at.isoformat()}


def _get_conta(db: Session, conta_id: uuid.UUID) -> Professor:
    conta = db.get(Professor, conta_id)
    if conta is None or conta.deleted_at is not None:
        raise AppError(404, "CONTA_NAO_ENCONTRADA", "Conta não encontrada.")
    return conta


def _other_active_admins(db: Session, exclude_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Professor).where(
        Professor.role == "ADMIN_LOCAL", Professor.is_active.is_(True), Professor.deleted_at.is_(None),
        Professor.id != exclude_id))


def _protect(db: Session, actor: Actor, conta: Professor, verbo: str) -> None:
    if conta.id == actor.user.id:
        raise AppError(409, "PROPRIA_CONTA", f"Você não pode {verbo} a própria conta.")
    if conta.role == "ADMIN_LOCAL" and conta.is_active and _other_active_admins(db, conta.id) == 0:
        raise AppError(409, "ULTIMO_ADMIN", "É preciso manter pelo menos um administrador ativo.")


@router.get("/contas")
def list_contas(actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Professor).where(Professor.deleted_at.is_(None)).order_by(Professor.display_name))
    return [conta_out(p) for p in rows]


@router.post("/contas", status_code=201)
def create_conta(body: ContaIn, actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    senha = generate_provisional_password()
    conta = create_professor(db, username=body.username, display_name=body.display_name, role=body.role,
                             password=senha, must_change_password=True)
    db.commit()
    log_event("account_created", admin_id=actor.user.id, professor_id=conta.id)
    return {"conta": conta_out(conta), "senha_provisoria": senha}


@router.patch("/contas/{conta_id}")
def patch_conta(conta_id: uuid.UUID, body: ContaPatch, actor: Actor = Depends(current_admin),
                db: Session = Depends(get_db)):
    conta = _get_conta(db, conta_id)
    if body.display_name is not None:
        conta.display_name = body.display_name
    if body.is_active is False and conta.is_active:
        _protect(db, actor, conta, "desativar")
        conta.is_active = False
        delete_all_sessions(db, conta.id)
    elif body.is_active is True:
        conta.is_active = True
    db.commit()
    return conta_out(conta)


@router.post("/contas/{conta_id}/senha-provisoria")
def reset_senha(conta_id: uuid.UUID, actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    conta = _get_conta(db, conta_id)
    senha = generate_provisional_password()
    conta.password_hash = hash_password(senha)
    conta.must_change_password, conta.failed_logins, conta.locked_until = True, 0, None
    delete_all_sessions(db, conta.id)
    db.commit()
    log_event("password_reset", admin_id=actor.user.id, professor_id=conta.id)
    return {"senha_provisoria": senha}


@router.delete("/contas/{conta_id}", status_code=204)
def delete_conta(conta_id: uuid.UUID, body: ExcluirIn, actor: Actor = Depends(current_admin),
                 db: Session = Depends(get_db)):
    conta = _get_conta(db, conta_id)
    if conta.id == actor.user.id:
        raise AppError(409, "PROPRIA_CONTA", "Você não pode excluir a própria conta.")
    if body.confirmar_username.strip().lower() != conta.username:
        raise AppError(422, "CONFIRMACAO_INVALIDA", "Digite o nome de usuário da conta para confirmar.")
    _protect(db, actor, conta, "excluir")
    paths: list[str] = []
    for aula in db.scalars(select(Aula).where(Aula.professor_id == conta.id, Aula.deleted_at.is_(None))):
        paths += soft_delete_aula(db, aula)
    now = utcnow()
    for model in (Turma, Disciplina):
        db.execute(update(model).where(model.professor_id == conta.id, model.deleted_at.is_(None))
                   .values(deleted_at=now))
    delete_all_sessions(db, conta.id)
    db.execute(update(Sessao).where(Sessao.acting_as_professor_id == conta.id)
               .values(acting_as_professor_id=None))
    conta.deleted_at, conta.is_active = now, False
    db.commit()
    for rel in paths:
        delete_file(rel)
    log_event("account_deleted", admin_id=actor.user.id, professor_id=conta.id)


@router.get("/aulas")
def list_all_aulas(professor_id: uuid.UUID | None = None, actor: Actor = Depends(current_admin),
                   db: Session = Depends(get_db)):
    query = (select(Aula, Turma, Disciplina, Professor)
             .join(Turma, Turma.id == Aula.turma_id).join(Disciplina, Disciplina.id == Aula.disciplina_id)
             .join(Professor, Professor.id == Aula.professor_id)
             .where(Aula.deleted_at.is_(None), Professor.deleted_at.is_(None))
             .order_by(Aula.lesson_date.desc(), Aula.created_at.desc()))
    if professor_id is not None:
        query = query.where(Aula.professor_id == professor_id)
    rows = db.execute(query).all()
    record(db, admin_id=actor.user.id, professor_id=professor_id, resource="aula", resource_id=None,
           action="read")
    db.commit()
    return [{**aula_summary(a, t, d), "professor": {"id": str(p.id), "display_name": p.display_name}}
            for a, t, d, p in rows]
```

Nota: o teste `test_admin_lists_all_aulas_with_filter` espera 2 linhas de leitura (uma por chamada da lista).

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): administração de contas (senha provisória, desativar, excluir) e aulas de todos os professores

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Testes de segurança transversais, logs sem dados sensíveis e auditorias Python

**Files:**
- Test: `backend/tests/test_security.py`, `backend/tests/test_logs.py`
- Modify (se necessário): `backend/pyproject.toml` (subir versões apontadas pelo `pip-audit`)

**Interfaces:**
- Consumes: toda a API das Tasks 1–10; `make_audio`, `upload` (Task 8); `run_once` (Task 9).
- Produces: nenhum código novo de produção, salvo correções que os testes revelarem.

- [ ] **Step 1: Escrever os testes**

`backend/tests/test_security.py`:
```python
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
```

`backend/tests/test_logs.py`:
```python
import json
import logging

from app.jobs.worker import run_once
from tests.audio_fixtures import make_audio, upload
from tests.helpers import PASSWORD, login, make_user


def test_full_flow_logs_no_sensitive_data(client, db, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="fias_ed")
    make_user(db, "professora.segredo")
    login(client, "professora.segredo")
    escola = client.post("/api/escolas", json={"name": "Escola Confidencial"}).json()
    turma = client.post("/api/turmas", json={"name": "Turma Sigilosa", "escola_id": escola["id"]}).json()
    disciplina = client.post("/api/disciplinas", json={"name": "Disciplina Reservada"}).json()
    aula = client.post("/api/aulas", json={"turma_id": turma["id"], "disciplina_id": disciplina["id"],
                                           "lesson_date": "2026-09-22", "note": "Observação privada"}).json()
    upload(client, aula["id"], make_audio(tmp_path / "gravacao-intima.wav"))
    client.post(f"/api/aulas/{aula['id']}/processar")
    run_once(db)
    client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "outra-senha-longa-9"})

    everything = caplog.text + json.dumps([getattr(r, "fields", {}) for r in caplog.records], ensure_ascii=False)
    for secret in (PASSWORD, "outra-senha-longa-9", "professora.segredo", "Professora.Segredo",
                   "Escola Confidencial", "Turma Sigilosa", "Disciplina Reservada", "Observação privada",
                   "gravacao-intima", client.cookies.get("fias_session"), client.cookies.get("fias_csrf")):
        assert secret not in everything, secret
    assert any(getattr(r, "fields", {}).get("event") == "audio_validated" for r in caplog.records)
```

- [ ] **Step 2: Rodar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS. Se algum teste falhar, é um defeito real de produção: corrigir o código da rota envolvida (não o teste) e rodar de novo.

- [ ] **Step 3: Auditorias Python (prompt §69)**

Run: `docker compose -f docker-compose.test.yml run --rm api-test bandit -r app --severity-level high`
Expected: `No issues identified.` para severidade alta (saída com código 0).

Run: `docker compose -f docker-compose.test.yml run --rm api-test pip-audit --skip-editable`
Expected: `No known vulnerabilities found`. Se houver achado, subir a versão mínima da dependência em `pyproject.toml`, rodar com `--build` e repetir; se não houver correção disponível, registrar o achado e a avaliação na seção "Auditorias" do README (Task 16).

Guardar as duas saídas (texto) no relatório da task — o README da Task 16 cita os resultados.

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/backend
git commit -m "test(web): segurança transversal (autenticação, CSRF, admin, injeção) e logs sem dados sensíveis

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---
### Task 12: Frontend — base do projeto, design system, cliente da API e status humanos

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/eslint.config.js`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/vite-env.d.ts`, `frontend/src/test-setup.ts`, `frontend/src/test-utils.tsx`
- Create: `frontend/src/design/index.css`, `fonts.css`, `base.css`, `components.css`
- Create: `frontend/src/design/components/Button.tsx`, `Field.tsx`, `Dialog.tsx`, `Banner.tsx`, `EmptyState.tsx`, `StatusBadge.tsx`
- Create: `frontend/src/api/client.ts`, `frontend/src/api/types.ts`
- Create: `frontend/src/app/status.ts`, `frontend/src/app/format.ts`
- Test: `frontend/src/app/status.test.ts`, `frontend/src/app/format.test.ts`, `frontend/src/api/client.test.ts`, `frontend/src/lint.test.ts`, `frontend/src/design/components/components.test.tsx`

**Interfaces:**
- Produces: `api<T>(path, init?: RequestInit & { json?: unknown }): Promise<T>` (prefixa `/api`, envia `X-CSRF-Token` do cookie `fias_csrf` em métodos que não são GET, lança `ApiError(status, code, message, extra)`); `uploadAudio(aulaId, file, onProgress: (fraction) => void): Promise<Aula>` (XHR `PUT`, cabeçalho `X-Filename` com `encodeURIComponent`); `sendAndProcess(aulaId, file, onProgress): Promise<Aula>` (upload + `POST /aulas/{id}/processar`).
- Produces tipos (`src/api/types.ts`): `Role`, `Me`, `Escola`, `Turma`, `Disciplina`, `AulaResumo`, `AudioInfo`, `Aula`, `Conta`.
- Produces: `STATUS_TEXT`, `statusText(s)`, `statusTone(s): "progress" | "attention" | "done"`, `JOB_MESSAGE` (`src/app/status.ts`); `formatDate(iso)`, `formatDateTime(iso)`, `formatDuration(ms)`, `formatBytes(n)` (`src/app/format.ts`).
- Produces componentes: `Button` (`variant?: "primary"|"secondary"|"tertiary"`, `type` padrão `"button"`), `TextField`, `SelectField`, `TextAreaField` (props de input + `label`, `error?`), `Dialog` (`title`, `children`, `actions`, `onClose`), `Banner` (`kind?: "info"|"error"|"warning"|"success"`), `EmptyState` (`title`, `children`, `action?`), `StatusBadge` (`status`).
- Produces (testes): `jsonResponse(body, status=200)`, `mockApi(handlers: Record<"MÉTODO /api/...", (init, url) => Response>)`.

- [ ] **Step 1: Criar o projeto e instalar dependências**

`frontend/package.json`:
```json
{
  "name": "fias-ed-web-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run",
    "lint": "eslint ."
  }
}
```

Run (de `fias-ed-web/frontend`):
```bash
npm install react react-dom react-router
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom @types/node vitest jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom eslint @eslint/js typescript-eslint eslint-plugin-react-hooks globals
```
Expected: `package-lock.json` criado; nenhuma dependência de runtime além de `react`, `react-dom`, `react-router`.

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "types": ["node", "@testing-library/jest-dom"],
    "baseUrl": ".",
    "paths": { "@shared/*": ["../../fias-ed-shared/*"] }
  },
  "include": ["src", "vite.config.ts"]
}
```

`frontend/vite.config.ts`:
```ts
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const shared = fileURLToPath(new URL("../../fias-ed-shared", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@shared": shared } },
  server: { fs: { allow: [".", shared] }, proxy: { "/api": "http://127.0.0.1:8080" } },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"], css: false },
});
```

`frontend/eslint.config.js`:
```js
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "no-restricted-syntax": [
        "error",
        { selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']", message: "Proibido: renderize texto (prompt §59)." },
        { selector: "JSXAttribute[name.name='style']", message: "Use classes CSS: a CSP bloqueia estilos inline." },
      ],
    },
  },
);
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FIAS-ED</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
```

`frontend/src/main.tsx` (a `App` chega na Task 13; por ora monta um título para o build funcionar):
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./design/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <h1>FIAS-ED</h1>
  </StrictMode>,
);
```

`frontend/src/test-setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  document.cookie = "fias_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});
```

`frontend/src/test-utils.tsx`:
```tsx
import { vi } from "vitest";

export function jsonResponse(body: unknown, status = 200): Response {
  if (status === 204) return new Response(null, { status });
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

type Handler = (init: RequestInit | undefined, url: string) => Response | Promise<Response>;

export function mockApi(handlers: Record<string, Handler>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const key = `${(init?.method ?? "GET").toUpperCase()} ${url}`;
    const handler = handlers[key];
    if (!handler) throw new Error(`Rota não simulada: ${key}`);
    return handler(init, url);
  });
}
```

- [ ] **Step 2: Escrever os testes (falham)**

`frontend/src/app/status.test.ts`:
```ts
import { describe, expect, test } from "vitest";
import aulaSchema from "@shared/schemas/entities/aula.schema.json";
import { STATUS_TEXT, statusText, statusTone } from "./status";

type Part = { properties?: { status?: { enum: string[] } } };
const statuses = (aulaSchema as { allOf: Part[] }).allOf.find((p) => p.properties?.status)!.properties!.status!.enum;

describe("status em linguagem humana", () => {
  test.each(statuses)("%s tem texto", (s) => {
    expect(STATUS_TEXT[s]).toBeTruthy();
  });

  test("nenhum texto usa vocabulário de julgamento", () => {
    for (const text of Object.values(STATUS_TEXT)) expect(text).not.toMatch(/avalia|nota|desempenho|ruim/i);
  });

  test("tons", () => {
    expect(statusTone("ERROR")).toBe("attention");
    expect(statusTone("READY_FOR_SPEAKER_REVIEW")).toBe("attention");
    expect(statusTone("AUDIO_VALIDATED")).toBe("done");
    expect(statusTone("TRANSCRIBING")).toBe("progress");
    expect(statusText("DRAFT")).toBe("Aguardando o áudio da aula");
  });
});
```

`frontend/src/app/format.test.ts`:
```ts
import { expect, test } from "vitest";
import { formatBytes, formatDate, formatDuration } from "./format";

test("formatDate", () => expect(formatDate("2026-09-22")).toBe("22/09/2026"));
test("formatDuration", () => {
  expect(formatDuration(65_000)).toBe("1 min");
  expect(formatDuration(45 * 60_000)).toBe("45 min");
  expect(formatDuration(3_900_000)).toBe("1h05");
});
test("formatBytes", () => {
  expect(formatBytes(1_610_612_736)).toBe("1,5 GB");
  expect(formatBytes(2_500_000)).toBe("2,4 MB");
});
```

`frontend/src/api/client.test.ts`:
```ts
import { expect, test } from "vitest";
import { api, ApiError } from "./client";
import { jsonResponse, mockApi } from "../test-utils";

test("GET não envia CSRF; POST envia o valor do cookie", async () => {
  document.cookie = "fias_csrf=abc123";
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse({ ok: 1 }),
    "POST /api/aulas": () => jsonResponse({ id: "1" }, 201),
  });
  await api("/auth/me");
  await api("/aulas", { method: "POST", json: { a: 1 } });
  const [, getInit] = spy.mock.calls[0];
  const [, postInit] = spy.mock.calls[1];
  expect(new Headers(getInit!.headers).get("X-CSRF-Token")).toBeNull();
  expect(new Headers(postInit!.headers).get("X-CSRF-Token")).toBe("abc123");
  expect(postInit!.body).toBe(JSON.stringify({ a: 1 }));
  expect(postInit!.credentials).toBe("same-origin");
});

test("erro vira ApiError com código e mensagem da API", async () => {
  mockApi({ "GET /api/aulas/x": () => jsonResponse({ error_code: "AULA_NAO_ENCONTRADA", message: "Aula não encontrada." }, 404) });
  await expect(api("/aulas/x")).rejects.toMatchObject({ status: 404, code: "AULA_NAO_ENCONTRADA", message: "Aula não encontrada." });
  await expect(api("/aulas/x")).rejects.toBeInstanceOf(ApiError);
});

test("204 devolve undefined", async () => {
  mockApi({ "DELETE /api/aulas/1": () => jsonResponse(null, 204) });
  expect(await api("/aulas/1", { method: "DELETE" })).toBeUndefined();
});
```

`frontend/src/lint.test.ts`:
```ts
// @vitest-environment node
import { ESLint } from "eslint";
import { expect, test } from "vitest";

test("lint proíbe dangerouslySetInnerHTML e style inline", async () => {
  const eslint = new ESLint();
  const [result] = await eslint.lintText(
    'export const A = () => <div dangerouslySetInnerHTML={{ __html: "x" }} style={{ color: "red" }} />;\n',
    { filePath: "src/exemplo.tsx" },
  );
  const messages = result.messages.map((m) => m.message).join("\n");
  expect(messages).toContain("§59");
  expect(messages).toContain("CSP");
});
```

`frontend/src/design/components/components.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { Banner } from "./Banner";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { TextField } from "./Field";
import { StatusBadge } from "./StatusBadge";

test("TextField associa rótulo e erro", () => {
  render(<TextField label="Usuário" error="Obrigatório" />);
  const input = screen.getByLabelText("Usuário");
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(input).toHaveAccessibleDescription("Obrigatório");
});

test("Button é type=button por padrão", () => {
  render(<Button>Salvar</Button>);
  expect(screen.getByRole("button", { name: "Salvar" })).toHaveAttribute("type", "button");
});

test("Dialog fecha com Esc e tem nome acessível", async () => {
  const onClose = vi.fn();
  render(<Dialog title="Excluir aula?" onClose={onClose} actions={<Button>Ok</Button>}>Texto</Dialog>);
  expect(screen.getByRole("dialog", { name: "Excluir aula?" })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalled();
});

test("Banner de erro é alerta", () => {
  render(<Banner kind="error">Falhou</Banner>);
  expect(screen.getByRole("alert")).toHaveTextContent("Falhou");
});

test("StatusBadge mostra texto humano", () => {
  render(<StatusBadge status="AUDIO_VALIDATED" />);
  expect(screen.getByText("Áudio conferido")).toBeInTheDocument();
});

test("texto hostil é renderizado como texto", () => {
  render(<Banner>{"<script>alert(1)</script>"}</Banner>);
  expect(screen.getByRole("status").textContent).toBe("<script>alert(1)</script>");
  expect(document.querySelector("script")).toBeNull();
});
```

- [ ] **Step 3: Rodar e ver falhar**

Run (de `frontend/`): `npm test`
Expected: FAIL (módulos `./status`, `./format`, `./client`, componentes não existem).

- [ ] **Step 4: Implementar status, formatação e cliente**

`frontend/src/app/status.ts`:
```ts
const ANALISANDO = "Analisando sua aula…";
const INTERPRETANDO = "Preparando a interpretação pedagógica…";
const PADROES = "Padrões de interação prontos";

export const STATUS_TEXT: Record<string, string> = {
  DRAFT: "Aguardando o áudio da aula",
  AUDIO_IMPORTED: "Áudio recebido, pronto para processar",
  AUDIO_VALIDATED: "Áudio conferido",
  PREPROCESSING: ANALISANDO,
  TRANSCRIBING: ANALISANDO,
  TRANSCRIBED: ANALISANDO,
  DIARIZING: ANALISANDO,
  READY_FOR_SPEAKER_REVIEW: "Confirme qual voz é a sua",
  READY_FOR_TRANSCRIPT_REVIEW: "Revise a transcrição, se quiser",
  READY_FOR_FIAS: PADROES,
  FIAS_COMPLETED: PADROES,
  WAITING_QTI: "Aguardando a percepção dos estudantes",
  QTI_COMPLETED: INTERPRETANDO,
  TRIANGULATED: INTERPRETANDO,
  MTSS_INTERPRETED: INTERPRETANDO,
  REPORT_READY: "Relatório da aula disponível",
  ERROR: "Precisa de atenção",
};

/** Mensagem do prompt §36 para a etapa executada em W1 (validação do áudio). */
export const JOB_MESSAGE = "Preparando sua aula...";

export type Tone = "progress" | "attention" | "done";

const ATTENTION = new Set(["ERROR", "DRAFT", "READY_FOR_SPEAKER_REVIEW", "READY_FOR_TRANSCRIPT_REVIEW", "WAITING_QTI"]);
const DONE = new Set(["AUDIO_IMPORTED", "AUDIO_VALIDATED", "READY_FOR_FIAS", "FIAS_COMPLETED", "REPORT_READY"]);

export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? "Em andamento";
}

export function statusTone(status: string): Tone {
  if (ATTENTION.has(status)) return "attention";
  if (DONE.has(status)) return "done";
  return "progress";
}
```

`frontend/src/app/format.ts`:
```ts
export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60_000);
  const hours = Math.floor(minutes / 60);
  if (hours === 0) return `${minutes} min`;
  return `${hours}h${String(minutes % 60).padStart(2, "0")}`;
}

export function formatBytes(n: number): string {
  const gb = n / 1024 ** 3;
  const value = gb >= 1 ? gb : n / 1024 ** 2;
  const unit = gb >= 1 ? "GB" : "MB";
  return `${value.toFixed(1).replace(/\.0$/, "").replace(".", ",")} ${unit}`;
}
```

`frontend/src/api/types.ts`:
```ts
export type Role = "ADMIN_LOCAL" | "PROFESSOR";

export interface Me {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  must_change_password: boolean;
  acting_as: { id: string; display_name: string } | null;
}

export interface Escola { id: string; name: string; municipality: string | null; region: string | null }
export interface Turma { id: string; name: string; school_year: number | null; level: string | null; escola: Escola }
export interface Disciplina { id: string; name: string }

export interface AulaResumo {
  id: string;
  lesson_date: string;
  status: string;
  turma: { id: string; name: string };
  disciplina: { id: string; name: string };
  professor?: { id: string; display_name: string };
}

export interface AudioInfo {
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  duration_ms: number;
  channels: number;
  sample_rate: number;
}

export interface Aula extends AulaResumo {
  note: string | null;
  error_code: string | null;
  error_message: string | null;
  audio: AudioInfo | null;
  upload_pendente: { original_filename: string; size_bytes: number } | null;
  job_ativo: boolean;
  alterada_pelo_admin_em: string | null;
}

export interface Conta {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}
```

`frontend/src/api/client.ts`:
```ts
import type { Aula } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public extra: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

const GENERIC = "Algo deu errado. Tente novamente.";

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )fias_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const method = (rest.method ?? "GET").toUpperCase();
  const headers = new Headers(rest.headers);
  if (method !== "GET") headers.set("X-CSRF-Token", csrfToken());
  let body = rest.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  const res = await fetch(`/api${path}`, { ...rest, method, headers, body, credentials: "same-origin" });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.error_code ?? "UNKNOWN", data.message ?? GENERIC, data);
  return data as T;
}

export function uploadAudio(aulaId: string, file: File, onProgress: (fraction: number) => void): Promise<Aula> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/aulas/${aulaId}/audio`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRF-Token", csrfToken());
    xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* resposta sem JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as unknown as Aula);
      else reject(new ApiError(xhr.status, String(data.error_code ?? "UNKNOWN"), String(data.message ?? GENERIC), data));
    };
    xhr.onerror = () => reject(new ApiError(0, "NETWORK", "Não foi possível enviar o arquivo. Verifique a conexão."));
    xhr.send(file);
  });
}

export async function sendAndProcess(aulaId: string, file: File, onProgress: (fraction: number) => void): Promise<Aula> {
  await uploadAudio(aulaId, file, onProgress);
  return api<Aula>(`/aulas/${aulaId}/processar`, { method: "POST" });
}
```

- [ ] **Step 5: Implementar CSS e componentes**

`frontend/src/design/index.css`:
```css
@import "@shared/design-tokens/build/tokens.css";
@import "./fonts.css";
@import "./base.css";
@import "./components.css";
```

`frontend/src/design/fonts.css` (fontes locais do shared; nunca CDN):
```css
@font-face { font-family: "Ubuntu"; font-weight: 400; font-style: normal; font-display: swap;
  src: url("@shared/design-tokens/fonts/Ubuntu-Regular.woff2") format("woff2"); }
@font-face { font-family: "Ubuntu"; font-weight: 500; font-style: normal; font-display: swap;
  src: url("@shared/design-tokens/fonts/Ubuntu-Medium.woff2") format("woff2"); }
@font-face { font-family: "Ubuntu"; font-weight: 700; font-style: normal; font-display: swap;
  src: url("@shared/design-tokens/fonts/Ubuntu-Bold.woff2") format("woff2"); }
@font-face { font-family: "Rokkitt"; font-weight: 100 900; font-style: normal; font-display: swap;
  src: url("@shared/design-tokens/fonts/Rokkitt%5Bwght%5D.woff2") format("woff2"); }
```
(Se o `vite build` não resolver o nome com `%5B…%5D`, trocar por `Rokkitt[wght].woff2`; conferir no `dist/assets` que o arquivo `.woff2` do Rokkitt foi copiado.)

`frontend/src/design/base.css`:
```css
*, *::before, *::after { box-sizing: border-box; }
html { font-size: 100%; }
body {
  margin: 0;
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-interface);
  font-size: var(--type-body-size);
  font-weight: var(--type-body-weight);
  line-height: var(--type-body-line);
}
h1, h2, h3 { margin: 0 0 var(--space-4); color: var(--color-navy); }
h1 { font-family: var(--type-h1-font); font-size: var(--type-h1-size); font-weight: var(--type-h1-weight); line-height: var(--type-h1-line); }
h2 { font-family: var(--type-h2-font); font-size: var(--type-h2-size); font-weight: var(--type-h2-weight); line-height: var(--type-h2-line); }
h3 { font-family: var(--type-h3-font); font-size: var(--type-h3-size); font-weight: var(--type-h3-weight); line-height: var(--type-h3-line); }
p { margin: 0 0 var(--space-4); }
a { color: var(--color-link); }
:focus-visible { outline: 3px solid var(--color-teal); outline-offset: 2px; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
```

`frontend/src/design/components.css`:
```css
/* Botões */
.btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2);
  min-height: 44px; padding: var(--space-2) var(--space-5); border-radius: var(--radius-sm);
  font-family: var(--type-button-font); font-size: var(--type-button-size); font-weight: var(--type-button-weight);
  border: var(--border-hairline) solid transparent; cursor: pointer; text-decoration: none; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn--primary { background: var(--color-action-primary); color: var(--color-white); }
.btn--secondary { background: var(--color-white); color: var(--color-teal); border-color: var(--color-teal); }
.btn--tertiary { background: transparent; color: var(--color-teal); padding-inline: var(--space-2); }

/* Campos */
.field { display: flex; flex-direction: column; gap: var(--space-1); margin-bottom: var(--space-4); }
.field__label { font-family: var(--type-label-font); font-size: var(--type-label-size); font-weight: var(--type-label-weight); }
.field__input { min-height: 44px; padding: var(--space-2) var(--space-3); border: var(--border-hairline) solid var(--color-muted);
  border-radius: var(--radius-sm); font: inherit; color: var(--color-text); background: var(--color-white); }
.field__input[aria-invalid="true"] { border-color: var(--color-error); }
.field__error { margin: 0; color: var(--color-error); font-size: var(--type-caption-size); }

/* Avisos */
.banner { padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); border-left: var(--border-strong) solid;
  margin-bottom: var(--space-4); background: var(--color-surface-alt); }
.banner--info { border-color: var(--color-info); }
.banner--error { border-color: var(--color-error); }
.banner--warning { border-color: var(--color-warning); }
.banner--success { border-color: var(--color-success); }

/* Diálogo */
.dialog-backdrop { position: fixed; inset: 0; background: rgb(47 65 86 / 0.45); display: grid; place-items: center; padding: var(--space-4); }
.dialog { background: var(--color-white); border-radius: var(--radius-md); padding: var(--space-6); max-width: 32rem; width: 100%;
  box-shadow: 0 8px 24px rgb(47 65 86 / 0.2); }
.dialog__actions { display: flex; justify-content: flex-end; gap: var(--space-3); margin-top: var(--space-5); flex-wrap: wrap; }

/* Estado vazio */
.empty { background: var(--color-surface-alt); border-radius: var(--radius-md); padding: var(--space-7) var(--space-5); text-align: center; }
.empty__title { font-family: var(--font-editorial); }

/* Status */
.badge { display: inline-block; padding: var(--space-1) var(--space-3); border-radius: var(--radius-sm);
  font-size: var(--type-caption-size); font-weight: 500; background: var(--color-surface-info); color: var(--color-navy); }
.badge--attention { background: var(--color-surface-alt); border: var(--border-hairline) solid var(--color-warning); }
.badge--done { background: var(--color-white); border: var(--border-hairline) solid var(--color-success); }

/* Estrutura */
.page { max-width: 72rem; margin: 0 auto; padding: var(--space-6) var(--space-4); }
.page__header { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-6); }
.topbar { display: flex; align-items: center; gap: var(--space-5); padding: var(--space-3) var(--space-4);
  background: var(--color-navy); color: var(--color-white); flex-wrap: wrap; }
.topbar__brand { font-family: var(--font-editorial); font-size: 1.5rem; font-weight: 600; color: var(--color-white); text-decoration: none; }
.topbar__nav { display: flex; gap: var(--space-4); flex: 1; flex-wrap: wrap; }
.topbar__nav a { color: var(--color-white); text-decoration: none; }
.topbar__nav a[aria-current="page"] { text-decoration: underline; text-underline-offset: 6px; }
.topbar .btn--tertiary { color: var(--color-white); }
.acting-banner { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap;
  background: var(--color-sky); color: var(--color-navy); padding: var(--space-2) var(--space-4); font-weight: 500; }

/* Listas e tabelas */
.list { list-style: none; margin: 0; padding: 0; border-top: var(--border-hairline) solid var(--color-border); }
.list__item { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap;
  padding: var(--space-4) var(--space-2); border-bottom: var(--border-hairline) solid var(--color-border); }
.list__item a { color: var(--color-navy); font-weight: 500; }
.meta { color: var(--color-text-muted); font-size: var(--type-caption-size); }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: var(--space-3) var(--space-2); border-bottom: var(--border-hairline) solid var(--color-border); }

/* Home */
.home { display: grid; gap: var(--space-7); max-width: 72rem; margin: 0 auto; padding: var(--space-7) var(--space-4); }
.home__brand { font-family: var(--font-editorial); font-size: 1.5rem; font-weight: 600; margin: 0 0 var(--space-5); }
.home__title { font-family: var(--type-display-font); font-size: var(--type-display-size); font-weight: var(--type-display-weight); line-height: var(--type-display-line); }
.home__login { background: var(--color-surface-alt); border-radius: var(--radius-md); padding: var(--space-6); }
@media (min-width: 900px) { .home { grid-template-columns: 3fr 2fr; align-items: center; min-height: 100vh; } }

/* Formulários em página */
.form-grid { display: grid; gap: 0 var(--space-5); }
@media (min-width: 900px) { .form-grid { grid-template-columns: 1fr 1fr; } }
.audio-area { background: var(--color-surface-alt); border-radius: var(--radius-md); padding: var(--space-5); margin: var(--space-5) 0; }
progress { width: 100%; accent-color: var(--color-teal); }
```

`frontend/src/design/components/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "tertiary" };

export function Button({ variant = "primary", className = "", type = "button", ...props }: Props) {
  return <button type={type} className={`btn btn--${variant} ${className}`.trim()} {...props} />;
}
```

`frontend/src/design/components/Field.tsx`:
```tsx
import { useId, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

type Common = { label: string; error?: string };

function useFieldIds(id?: string) {
  const auto = useId();
  const fieldId = id ?? auto;
  return { fieldId, errorId: `${fieldId}-erro` };
}

export function TextField({ label, error, id, ...input }: InputHTMLAttributes<HTMLInputElement> & Common) {
  const { fieldId, errorId } = useFieldIds(id);
  return (
    <div className="field">
      <label className="field__label" htmlFor={fieldId}>{label}</label>
      <input id={fieldId} className="field__input" aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined} {...input} />
      {error && <p id={errorId} className="field__error">{error}</p>}
    </div>
  );
}

export function SelectField({ label, error, id, children, ...select }: SelectHTMLAttributes<HTMLSelectElement> & Common) {
  const { fieldId, errorId } = useFieldIds(id);
  return (
    <div className="field">
      <label className="field__label" htmlFor={fieldId}>{label}</label>
      <select id={fieldId} className="field__input" aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined} {...select}>
        {children}
      </select>
      {error && <p id={errorId} className="field__error">{error}</p>}
    </div>
  );
}

export function TextAreaField({ label, error, id, ...area }: TextareaHTMLAttributes<HTMLTextAreaElement> & Common) {
  const { fieldId, errorId } = useFieldIds(id);
  return (
    <div className="field">
      <label className="field__label" htmlFor={fieldId}>{label}</label>
      <textarea id={fieldId} className="field__input" rows={3} aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined} {...area} />
      {error && <p id={errorId} className="field__error">{error}</p>}
    </div>
  );
}
```

`frontend/src/design/components/Dialog.tsx`:
```tsx
import { useEffect, useId, useRef, type ReactNode } from "react";

type Props = { title: string; children: ReactNode; actions: ReactNode; onClose: () => void };

export function Dialog({ title, children, actions, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="dialog-backdrop">
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} ref={ref}>
        <h2 id={titleId}>{title}</h2>
        <div>{children}</div>
        <div className="dialog__actions">{actions}</div>
      </div>
    </div>
  );
}
```

`frontend/src/design/components/Banner.tsx`:
```tsx
import type { ReactNode } from "react";

type Props = { kind?: "info" | "error" | "warning" | "success"; children: ReactNode };

export function Banner({ kind = "info", children }: Props) {
  return (
    <div className={`banner banner--${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
```

`frontend/src/design/components/EmptyState.tsx`:
```tsx
import type { ReactNode } from "react";

type Props = { title: string; children: ReactNode; action?: ReactNode };

export function EmptyState({ title, children, action }: Props) {
  return (
    <section className="empty">
      <h2 className="empty__title">{title}</h2>
      <p>{children}</p>
      {action}
    </section>
  );
}
```

`frontend/src/design/components/StatusBadge.tsx`:
```tsx
import { statusText, statusTone } from "../../app/status";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge--${statusTone(status)}`}>{statusText(status)}</span>;
}
```

- [ ] **Step 6: Rodar testes, lint e build**

Run (de `frontend/`): `npm test && npm run lint && npm run build`
Expected: todos os testes PASS; lint sem erros; build gera `dist/` com os `.woff2` em `dist/assets/`.

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/frontend
git commit -m "feat(web): base do frontend com tokens e fontes locais do shared, componentes e cliente da API

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Frontend — sessão, rotas, Home (entrada), troca de senha e layout com "agindo como"

**Files:**
- Create: `frontend/src/app/AuthContext.tsx`, `frontend/src/app/RequireAuth.tsx`, `frontend/src/app/Layout.tsx`, `frontend/src/app/App.tsx`
- Create: `frontend/src/pages/Home.tsx`, `frontend/src/pages/TrocarSenha.tsx`
- Modify: `frontend/src/main.tsx` (renderizar `App`)
- Test: `frontend/src/pages/Home.test.tsx`, `frontend/src/app/Layout.test.tsx`

**Interfaces:**
- Consumes: `api`, `ApiError`, tipos (Task 12); componentes (Task 12).
- Produces: `AuthProvider`, `useAuth(): { me: Me | null; loading: boolean; refresh(): Promise<void>; setMe(me: Me | null): void }`; `RequireAuth` (`allowPasswordChange?: boolean`), `RequireAdmin`; `Layout` (barra superior + faixa "agindo como" + `<Outlet />`); `App` (rotas: `/`, `/trocar-senha`, e sob `Layout`: `/aulas` — as páginas entram nas Tasks 14 e 15).
- Produces (testes): `renderApp(path)` exportado de `src/test-utils.tsx` (acrescentado nesta task).

- [ ] **Step 1: Escrever os testes (falham)**

Acrescentar a `frontend/src/test-utils.tsx` (imports no topo do arquivo, o resto no fim):
```tsx
import { render } from "@testing-library/react";
import { App } from "./app/App";

export function renderApp(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

export const PROFESSORA = {
  id: "p1", username: "ana", display_name: "Ana Souza", role: "PROFESSOR" as const,
  must_change_password: false, acting_as: null,
};
export const ADMIN = { ...PROFESSORA, id: "a1", username: "admin", display_name: "Pesquisador", role: "ADMIN_LOCAL" as const };
```

`frontend/src/pages/Home.test.tsx`:
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const unauth = () => jsonResponse({ error_code: "UNAUTHENTICATED", message: "Entre com seu usuário e senha." }, 401);

test("mostra a mensagem principal e o formulário de entrada", async () => {
  mockApi({ "GET /api/auth/me": unauth });
  renderApp("/");
  expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Grave sua aula.Melhore sua prática docente.");
  expect(screen.getByText("Envie o áudio de uma aula e conheça melhor os padrões de interação que acontecem em sala.")).toBeInTheDocument();
  expect(screen.getByLabelText("Usuário")).toBeInTheDocument();
});

test("entrar leva às aulas", async () => {
  mockApi({
    "GET /api/auth/me": unauth,
    "POST /api/auth/login": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/");
  await userEvent.type(await screen.findByLabelText("Usuário"), "ana");
  await userEvent.type(screen.getByLabelText("Senha"), "senha-de-teste-123");
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
  expect(screen.getByRole("link", { name: "Minhas aulas" })).toBeInTheDocument();
});

test("falha de login mostra a mensagem da API", async () => {
  mockApi({
    "GET /api/auth/me": unauth,
    "POST /api/auth/login": () => jsonResponse({ error_code: "LOGIN_FAILED", message: "Usuário ou senha incorretos." }, 401),
  });
  renderApp("/");
  await userEvent.type(await screen.findByLabelText("Usuário"), "ana");
  await userEvent.type(screen.getByLabelText("Senha"), "errada");
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Usuário ou senha incorretos.");
});

test("senha provisória obriga a troca", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse({ ...PROFESSORA, must_change_password: true }),
    "POST /api/auth/password": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/aulas");
  expect(await screen.findByRole("heading", { name: "Troque sua senha" })).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Senha atual"), "provisoria-123");
  await userEvent.type(screen.getByLabelText("Nova senha"), "curta");
  await userEvent.type(screen.getByLabelText("Repita a nova senha"), "curta");
  await userEvent.click(screen.getByRole("button", { name: "Salvar nova senha" }));
  expect(await screen.findByText("A senha precisa ter pelo menos 12 caracteres.")).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("Nova senha"));
  await userEvent.type(screen.getByLabelText("Nova senha"), "minha-senha-nova-1");
  await userEvent.clear(screen.getByLabelText("Repita a nova senha"));
  await userEvent.type(screen.getByLabelText("Repita a nova senha"), "minha-senha-nova-1");
  await userEvent.click(screen.getByRole("button", { name: "Salvar nova senha" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
});
```

`frontend/src/app/Layout.test.tsx`:
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { ADMIN, jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

test("professor não vê links de administração", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(PROFESSORA), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/aulas");
  expect(await screen.findByRole("link", { name: "Minhas aulas" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Contas" })).not.toBeInTheDocument();
});

test("admin vê links de administração", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(ADMIN), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/aulas");
  expect(await screen.findByRole("link", { name: "Contas" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Aulas dos professores" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Escolas" })).toBeInTheDocument();
});

test("faixa 'agindo como' e volta à própria conta", async () => {
  const acting = { ...ADMIN, acting_as: { id: "p1", display_name: "Ana Souza" } };
  mockApi({
    "GET /api/auth/me": () => jsonResponse(acting),
    "GET /api/aulas": () => jsonResponse([]),
    "DELETE /api/admin/agir-como": () => jsonResponse(ADMIN),
    "GET /api/admin/aulas": () => jsonResponse([]),
    "GET /api/admin/contas": () => jsonResponse([]),
  });
  renderApp("/aulas");
  expect(await screen.findByText("Você está agindo como: Ana Souza")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Voltar à minha conta" }));
  await waitFor(() => expect(screen.queryByText(/Você está agindo como/)).not.toBeInTheDocument());
});

test("sair encerra a sessão", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
    "POST /api/auth/logout": () => jsonResponse(null, 204),
  });
  renderApp("/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
  await waitFor(() => expect(window.location.pathname).toBe("/"));
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run (de `frontend/`): `npm test`
Expected: FAIL (`./app/App` não existe).

- [ ] **Step 3: Implementar sessão e rotas**

`frontend/src/app/AuthContext.tsx`:
```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Me } from "../api/types";

type AuthState = { me: Me | null; loading: boolean; refresh: () => Promise<void>; setMe: (me: Me | null) => void };

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  return <AuthContext.Provider value={{ me, loading, refresh, setMe }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider ausente");
  return ctx;
}
```

`frontend/src/app/RequireAuth.tsx`:
```tsx
import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children, allowPasswordChange = false }: { children: ReactNode; allowPasswordChange?: boolean }) {
  const { me, loading } = useAuth();
  if (loading) return <p className="page" role="status">Carregando…</p>;
  if (!me) return <Navigate to="/" replace />;
  if (me.must_change_password && !allowPasswordChange) return <Navigate to="/trocar-senha" replace />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  if (me?.role !== "ADMIN_LOCAL") return <Navigate to="/aulas" replace />;
  return <>{children}</>;
}
```

`frontend/src/app/Layout.tsx`:
```tsx
import { NavLink, Outlet, useNavigate } from "react-router";
import { api } from "../api/client";
import type { Me } from "../api/types";
import { Button } from "../design/components/Button";
import { useAuth } from "./AuthContext";

export function Layout() {
  const { me, setMe } = useAuth();
  const navigate = useNavigate();
  if (!me) return null;

  async function sair() {
    await api("/auth/logout", { method: "POST" });
    setMe(null);
    navigate("/", { replace: true });
  }

  async function voltar() {
    setMe(await api<Me>("/admin/agir-como", { method: "DELETE" }));
    navigate("/admin/aulas");
  }

  return (
    <>
      <header className="topbar">
        <NavLink to="/aulas" className="topbar__brand">FIAS-ED</NavLink>
        <nav className="topbar__nav" aria-label="Navegação principal">
          <NavLink to="/aulas" end>Minhas aulas</NavLink>
          {me.role === "ADMIN_LOCAL" && (
            <>
              <NavLink to="/admin/aulas">Aulas dos professores</NavLink>
              <NavLink to="/admin/contas">Contas</NavLink>
              <NavLink to="/admin/escolas">Escolas</NavLink>
            </>
          )}
        </nav>
        <span>{me.display_name}</span>
        <Button variant="tertiary" onClick={sair}>Sair</Button>
      </header>
      {me.acting_as && (
        <div className="acting-banner" role="status">
          <span>Você está agindo como: {me.acting_as.display_name}</span>
          <Button variant="secondary" onClick={voltar}>Voltar à minha conta</Button>
        </div>
      )}
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}
```

`frontend/src/app/App.tsx`:
```tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Home } from "../pages/Home";
import { TrocarSenha } from "../pages/TrocarSenha";
import { AuthProvider } from "./AuthContext";
import { Layout } from "./Layout";
import { RequireAuth } from "./RequireAuth";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/trocar-senha" element={<RequireAuth allowPasswordChange><TrocarSenha /></RequireAuth>} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/aulas" element={null} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./design/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 4: Implementar as páginas Home e Trocar senha**

`frontend/src/pages/Home.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { Me } from "../api/types";
import { useAuth } from "../app/AuthContext";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { TextField } from "../design/components/Field";

export function Home() {
  const { me, loading, setMe } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && me) return <Navigate to={me.must_change_password ? "/trocar-senha" : "/aulas"} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const next = await api<Me>("/auth/login", { method: "POST", json: { username, password } });
      setMe(next);
      navigate(next.must_change_password ? "/trocar-senha" : "/aulas", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível entrar. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="home">
      <section>
        <p className="home__brand">FIAS-ED</p>
        <h1 className="home__title">Grave sua aula.<br />Melhore sua prática docente.</h1>
        <p>Envie o áudio de uma aula e conheça melhor os padrões de interação que acontecem em sala.</p>
      </section>
      <section className="home__login" aria-labelledby="entrar-titulo">
        <h2 id="entrar-titulo">Entrar</h2>
        <form onSubmit={onSubmit} noValidate>
          <TextField label="Usuário" name="username" autoComplete="username" value={username}
            onChange={(e) => setUsername(e.target.value)} required />
          <TextField label="Senha" name="password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          {error && <Banner kind="error">{error}</Banner>}
          <Button type="submit" disabled={busy}>{busy ? "Entrando…" : "Entrar"}</Button>
        </form>
      </section>
    </main>
  );
}
```

`frontend/src/pages/TrocarSenha.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { Me } from "../api/types";
import { useAuth } from "../app/AuthContext";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { TextField } from "../design/components/Field";

export function TrocarSenha() {
  const { me, setMe } = useAuth();
  const navigate = useNavigate();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repetida, setRepetida] = useState("");
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (nova.length < 12) return setFieldError("A senha precisa ter pelo menos 12 caracteres.");
    if (nova !== repetida) return setFieldError("As duas senhas precisam ser iguais.");
    setFieldError(undefined);
    setBusy(true);
    try {
      setMe(await api<Me>("/auth/password", { method: "POST", json: { current_password: atual, new_password: nova } }));
      navigate("/aulas", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível trocar a senha.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <h1>Troque sua senha</h1>
      {me?.must_change_password && <p>Por segurança, crie uma senha só sua antes de continuar.</p>}
      <form onSubmit={onSubmit} noValidate>
        <TextField label="Senha atual" type="password" autoComplete="current-password" value={atual}
          onChange={(e) => setAtual(e.target.value)} required />
        <TextField label="Nova senha" type="password" autoComplete="new-password" value={nova}
          onChange={(e) => setNova(e.target.value)} error={fieldError} required />
        <TextField label="Repita a nova senha" type="password" autoComplete="new-password" value={repetida}
          onChange={(e) => setRepetida(e.target.value)} required />
        {error && <Banner kind="error">{error}</Banner>}
        <Button type="submit" disabled={busy}>Salvar nova senha</Button>
      </form>
    </main>
  );
}
```

- [ ] **Step 5: Rodar testes, lint e build**

Run (de `frontend/`): `npm test && npm run lint && npm run build`
Expected: PASS; lint limpo; build ok.

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/frontend
git commit -m "feat(web): entrada, troca obrigatória de senha, rotas protegidas e faixa 'agindo como'

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Frontend — Minhas aulas, Nova Aula com upload e página da Aula

**Files:**
- Create: `frontend/src/app/AudioPicker.tsx`
- Create: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/NovaAula.tsx`, `frontend/src/pages/NovaTurma.tsx`, `frontend/src/pages/AulaPage.tsx`
- Modify: `frontend/src/app/App.tsx` (rotas `/aulas`, `/aulas/nova`, `/aulas/:id`)
- Test: `frontend/src/pages/Dashboard.test.tsx`, `frontend/src/pages/NovaAula.test.tsx`, `frontend/src/pages/AulaPage.test.tsx`

**Interfaces:**
- Consumes: `api`, `ApiError`, `sendAndProcess` (Task 12); `useAuth` (Task 13); `statusText`, `JOB_MESSAGE`, `format*` (Task 12); componentes (Task 12).
- Produces: `AudioPicker({ file, onChange, label? })` (input de arquivo oculto + botão "Selecionar áudio", aceita `.mp3,.wav,.m4a,.aac,.flac`); `NovaTurma({ onCreated(turma: Turma), onCancel })` (inclui escolha/criação de escola com tratamento de `ESCOLA_DUPLICADA`); páginas `Dashboard`, `NovaAula`, `AulaPage`.

- [ ] **Step 1: Escrever os testes (falham)**

`frontend/src/pages/Dashboard.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

test("estado vazio convida a adicionar a primeira aula", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(PROFESSORA), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/aulas");
  expect(await screen.findByText("Nenhuma aula ainda")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Adicionar aula" })[0]).toHaveAttribute("href", "/aulas/nova");
});

test("lista aulas com status humano", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([{ id: "a1", lesson_date: "2026-09-22", status: "AUDIO_VALIDATED",
      turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" } }]),
  });
  renderApp("/aulas");
  expect(await screen.findByRole("link", { name: /22\/09\/2026/ })).toHaveAttribute("href", "/aulas/a1");
  expect(screen.getByText("9º B · Ciências")).toBeInTheDocument();
  expect(screen.getByText("Áudio conferido")).toBeInTheDocument();
});

test("admin agindo como vê o nome do professor no título", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse({ ...PROFESSORA, role: "ADMIN_LOCAL", acting_as: { id: "p9", display_name: "Bia" } }),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/aulas");
  expect(await screen.findByRole("heading", { name: "Aulas de Bia" })).toBeInTheDocument();
});
```

`frontend/src/pages/NovaAula.test.tsx`:
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { sendAndProcess } from "../api/client";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  sendAndProcess: vi.fn(),
}));

const ESCOLA = { id: "e1", name: "Escola A", municipality: "Mossoró", region: "Nordeste" };
const TURMA = { id: "t1", name: "9º B", school_year: 2026, level: null, escola: ESCOLA };
const AULA = { id: "a1", lesson_date: "2026-09-22", status: "DRAFT", turma: { id: "t1", name: "9º B" },
  disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null, error_message: null, audio: null,
  upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null };

beforeEach(() => vi.mocked(sendAndProcess).mockReset());

test("preenche, seleciona o áudio e processa a aula", async () => {
  vi.mocked(sendAndProcess).mockResolvedValue({ ...AULA, status: "AUDIO_IMPORTED", job_ativo: true });
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse([TURMA]),
    "GET /api/disciplinas": () => jsonResponse([{ id: "d1", name: "Ciências" }]),
    "GET /api/escolas": () => jsonResponse([ESCOLA]),
    "POST /api/aulas": () => jsonResponse(AULA, 201),
    "GET /api/aulas/a1": () => jsonResponse({ ...AULA, status: "AUDIO_IMPORTED", job_ativo: true }),
  });
  renderApp("/aulas/nova");
  await userEvent.selectOptions(await screen.findByLabelText("Turma"), "t1");
  await userEvent.selectOptions(screen.getByLabelText("Disciplina"), "d1");
  expect(screen.getByText("Selecione o arquivo de áudio gravado durante sua aula.")).toBeInTheDocument();
  const file = new File(["x"], "aula.mp3", { type: "audio/mpeg" });
  await userEvent.upload(screen.getByLabelText("Arquivo de áudio"), file);
  expect(screen.getByText(/aula\.mp3/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Processar aula" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1"));
  const post = spy.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(post![1]!.body))).toMatchObject({ turma_id: "t1", disciplina_id: "d1" });
  expect(vi.mocked(sendAndProcess)).toHaveBeenCalledWith("a1", file, expect.any(Function));
});

test("processar fica desabilitado sem arquivo", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse([TURMA]),
    "GET /api/disciplinas": () => jsonResponse([{ id: "d1", name: "Ciências" }]),
    "GET /api/escolas": () => jsonResponse([ESCOLA]),
  });
  renderApp("/aulas/nova");
  await userEvent.selectOptions(await screen.findByLabelText("Turma"), "t1");
  expect(screen.getByRole("button", { name: "Processar aula" })).toBeDisabled();
});

test("nova turma com escola duplicada oferece usar a existente", async () => {
  let turmas: unknown[] = [];
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse(turmas),
    "GET /api/disciplinas": () => jsonResponse([]),
    "GET /api/escolas": () => jsonResponse([]),
    "POST /api/escolas": () => jsonResponse({ error_code: "ESCOLA_DUPLICADA",
      message: "Já existe uma escola com este nome neste município.", duplicatas: [ESCOLA] }, 409),
    "POST /api/turmas": (init) => {
      expect(JSON.parse(String(init!.body)).escola_id).toBe("e1");
      turmas = [TURMA];
      return jsonResponse(TURMA, 201);
    },
  });
  renderApp("/aulas/nova");
  await userEvent.selectOptions(await screen.findByLabelText("Turma"), "__nova__");
  await userEvent.type(screen.getByLabelText("Nome da turma"), "9º B");
  await userEvent.selectOptions(screen.getByLabelText("Escola"), "__nova__");
  await userEvent.type(screen.getByLabelText("Nome da escola"), "escola a");
  await userEvent.type(screen.getByLabelText("Município"), "Mossoró");
  await userEvent.click(screen.getByRole("button", { name: "Salvar turma" }));
  expect(await screen.findByText("Já existe uma escola com este nome neste município.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Usar Escola A (Mossoró)" }));
  await waitFor(() => expect(screen.getByLabelText("Turma")).toHaveValue("t1"));
});
```

`frontend/src/pages/AulaPage.test.tsx`:
```tsx
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const BASE = { id: "a1", lesson_date: "2026-09-22", turma: { id: "t1", name: "9º B" },
  disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null, error_message: null, audio: null,
  upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null, status: "DRAFT" };

afterEach(() => vi.useRealTimers());

test("erro mostra a mensagem humana e permite enviar outro áudio", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "ERROR", error_code: "AUDIO_TOO_SHORT",
      error_message: "O áudio tem menos de 1 minuto. Verifique se é o arquivo certo." }),
  });
  renderApp("/aulas/a1");
  expect(await screen.findByRole("alert")).toHaveTextContent("O áudio tem menos de 1 minuto.");
  expect(screen.getByRole("button", { name: "Selecionar áudio" })).toBeInTheDocument();
});

test("aviso de alteração pelo administrador", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, alterada_pelo_admin_em: "2026-09-22T12:00:00+00:00" }),
  });
  renderApp("/aulas/a1");
  expect(await screen.findByText(/Alterada pelo administrador em/)).toBeInTheDocument();
});

test("acompanha o processamento até o áudio ser conferido", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let calls = 0;
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => {
      calls += 1;
      return jsonResponse(calls === 1
        ? { ...BASE, status: "AUDIO_IMPORTED", job_ativo: true, upload_pendente: { original_filename: "a.wav", size_bytes: 10 } }
        : { ...BASE, status: "AUDIO_VALIDATED", audio: { original_filename: "a.wav", mime_type: "audio/wav",
            size_bytes: 2_000_000, duration_ms: 3_000_000, channels: 1, sample_rate: 16000 } });
    },
  });
  renderApp("/aulas/a1");
  expect(await screen.findByText("Preparando sua aula...")).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
  await waitFor(() => expect(screen.getByText("Áudio conferido")).toBeInTheDocument());
  expect(screen.getByText("50 min")).toBeInTheDocument();
  expect(document.querySelector("audio")).toHaveAttribute("src", "/api/aulas/a1/audio");
});

test("substituir o áudio pede confirmação", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "AUDIO_VALIDATED", audio: { original_filename: "a.wav",
      mime_type: "audio/wav", size_bytes: 10, duration_ms: 70_000, channels: 1, sample_rate: 16000 } }),
  });
  renderApp("/aulas/a1");
  await userEvent.click(await screen.findByRole("button", { name: "Substituir áudio" }));
  expect(screen.getByRole("dialog", { name: "Substituir o áudio?" })).toHaveTextContent("O arquivo anterior será apagado.");
});

test("excluir a aula volta para a lista", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse(BASE),
    "DELETE /api/aulas/a1": () => jsonResponse(null, 204),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/aulas/a1");
  await userEvent.click(await screen.findByRole("button", { name: "Excluir aula" }));
  await userEvent.click(screen.getByRole("button", { name: "Excluir definitivamente" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run (de `frontend/`): `npm test`
Expected: FAIL (páginas ausentes).

- [ ] **Step 3: Implementar `AudioPicker` e `NovaTurma`**

`frontend/src/app/AudioPicker.tsx`:
```tsx
import { useId, useRef } from "react";
import { Button } from "../design/components/Button";
import { formatBytes } from "./format";

export const AUDIO_ACCEPT = ".mp3,.wav,.m4a,.aac,.flac";

type Props = { file: File | null; onChange: (file: File | null) => void; label?: string };

export function AudioPicker({ file, onChange, label = "Selecionar áudio" }: Props) {
  const inputId = useId();
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div>
      <label htmlFor={inputId} className="visually-hidden">Arquivo de áudio</label>
      <input id={inputId} ref={ref} type="file" accept={AUDIO_ACCEPT} className="visually-hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
      <Button variant="secondary" onClick={() => ref.current?.click()}>{label}</Button>
      {file && <p className="meta">{file.name} · {formatBytes(file.size)}</p>}
    </div>
  );
}
```

`frontend/src/pages/NovaTurma.tsx`:
```tsx
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Escola, Turma } from "../api/types";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { SelectField, TextField } from "../design/components/Field";

const REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"];

type Props = { onCreated: (turma: Turma) => void; onCancel: () => void };

export function NovaTurma({ onCreated, onCancel }: Props) {
  const [escolas, setEscolas] = useState<Escola[]>([]);
  const [nome, setNome] = useState("");
  const [escolaId, setEscolaId] = useState("");
  const [novaEscola, setNovaEscola] = useState({ name: "", municipality: "", region: "" });
  const [duplicatas, setDuplicatas] = useState<Escola[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Escola[]>("/escolas").then(setEscolas).catch(() => setEscolas([]));
  }, []);

  async function criarTurma(idDaEscola: string) {
    onCreated(await api<Turma>("/turmas", { method: "POST", json: { name: nome, escola_id: idDaEscola } }));
  }

  async function salvar(confirmarNova = false) {
    setError(null);
    try {
      if (escolaId !== "__nova__") return await criarTurma(escolaId);
      const escola = await api<Escola>("/escolas", { method: "POST", json: {
        name: novaEscola.name, municipality: novaEscola.municipality || null,
        region: novaEscola.region || null, confirmar_nova: confirmarNova } });
      await criarTurma(escola.id);
    } catch (err) {
      if (err instanceof ApiError && err.code === "ESCOLA_DUPLICADA") setDuplicatas(err.extra.duplicatas as Escola[]);
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a turma.");
    }
  }

  return (
    <div className="audio-area" role="group" aria-label="Nova turma">
      <TextField label="Nome da turma" value={nome} onChange={(e) => setNome(e.target.value)} maxLength={120} required />
      <SelectField label="Escola" value={escolaId} onChange={(e) => setEscolaId(e.target.value)} required>
        <option value="" disabled>Escolha a escola</option>
        {escolas.map((esc) => <option key={esc.id} value={esc.id}>{esc.name}{esc.municipality ? ` (${esc.municipality})` : ""}</option>)}
        <option value="__nova__">+ Cadastrar nova escola</option>
      </SelectField>
      {escolaId === "__nova__" && (
        <div className="form-grid">
          <TextField label="Nome da escola" value={novaEscola.name} maxLength={200} required
            onChange={(e) => setNovaEscola({ ...novaEscola, name: e.target.value })} />
          <TextField label="Município" value={novaEscola.municipality} maxLength={120}
            onChange={(e) => setNovaEscola({ ...novaEscola, municipality: e.target.value })} />
          <SelectField label="Região" value={novaEscola.region}
            onChange={(e) => setNovaEscola({ ...novaEscola, region: e.target.value })}>
            <option value="">Não informar</option>
            {REGIOES.map((r) => <option key={r} value={r}>{r}</option>)}
          </SelectField>
        </div>
      )}
      {error && <Banner kind="error">{error}</Banner>}
      {duplicatas.length > 0 && (
        <div className="dialog__actions">
          {duplicatas.map((d) => (
            <Button key={d.id} variant="secondary" onClick={() => void criarTurma(d.id)}>
              Usar {d.name}{d.municipality ? ` (${d.municipality})` : ""}
            </Button>
          ))}
          <Button variant="tertiary" onClick={() => void salvar(true)}>Cadastrar mesmo assim</Button>
        </div>
      )}
      <div className="dialog__actions">
        <Button variant="tertiary" onClick={onCancel}>Cancelar</Button>
        <Button onClick={() => void salvar()}>Salvar turma</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implementar `Dashboard`, `NovaAula` e `AulaPage`**

`frontend/src/pages/Dashboard.tsx`:
```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { AulaResumo } from "../api/types";
import { useAuth } from "../app/AuthContext";
import { formatDate } from "../app/format";
import { Banner } from "../design/components/Banner";
import { EmptyState } from "../design/components/EmptyState";
import { StatusBadge } from "../design/components/StatusBadge";

export function Dashboard() {
  const { me } = useAuth();
  const [aulas, setAulas] = useState<AulaResumo[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<AulaResumo[]>("/aulas").then(setAulas).catch(() => setError(true));
  }, [me?.acting_as?.id]);

  const adicionar = <Link className="btn btn--primary" to="/aulas/nova">Adicionar aula</Link>;
  return (
    <>
      <div className="page__header">
        <h1>{me?.acting_as ? `Aulas de ${me.acting_as.display_name}` : "Minhas aulas"}</h1>
        {aulas && aulas.length > 0 && adicionar}
      </div>
      {error && <Banner kind="error">Não foi possível carregar as aulas. Recarregue a página.</Banner>}
      {aulas === null && !error && <p role="status">Carregando…</p>}
      {aulas?.length === 0 && (
        <EmptyState title="Nenhuma aula ainda" action={adicionar}>
          Adicione sua primeira aula e envie o áudio gravado em sala.
        </EmptyState>
      )}
      {aulas && aulas.length > 0 && (
        <ul className="list">
          {aulas.map((a) => (
            <li key={a.id} className="list__item">
              <div>
                <Link to={`/aulas/${a.id}`}>Aula de {formatDate(a.lesson_date)}</Link>
                <p className="meta">{a.turma.name} · {a.disciplina.name}</p>
              </div>
              <StatusBadge status={a.status} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
```

`frontend/src/pages/NovaAula.tsx`:
```tsx
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError, sendAndProcess } from "../api/client";
import type { Aula, Disciplina, Turma } from "../api/types";
import { AudioPicker } from "../app/AudioPicker";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { SelectField, TextAreaField, TextField } from "../design/components/Field";
import { NovaTurma } from "./NovaTurma";

const today = () => new Date().toISOString().slice(0, 10);

export function NovaAula() {
  const navigate = useNavigate();
  const [turmas, setTurmas] = useState<Turma[]>([]);
  const [disciplinas, setDisciplinas] = useState<Disciplina[]>([]);
  const [turmaId, setTurmaId] = useState("");
  const [disciplinaId, setDisciplinaId] = useState("");
  const [novaDisciplina, setNovaDisciplina] = useState("");
  const [data, setData] = useState(today());
  const [nota, setNota] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Turma[]>("/turmas").then(setTurmas).catch(() => setTurmas([]));
    api<Disciplina[]>("/disciplinas").then(setDisciplinas).catch(() => setDisciplinas([]));
  }, []);

  async function salvarDisciplina() {
    const d = await api<Disciplina>("/disciplinas", { method: "POST", json: { name: novaDisciplina } });
    setDisciplinas([...disciplinas, d]);
    setDisciplinaId(d.id);
    setNovaDisciplina("");
  }

  const pronto = turmaId && turmaId !== "__nova__" && disciplinaId && disciplinaId !== "__nova__" && data && file;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pronto || !file) return;
    setError(null);
    let aula: Aula | null = null;
    try {
      aula = await api<Aula>("/aulas", { method: "POST", json: {
        turma_id: turmaId, disciplina_id: disciplinaId, lesson_date: data, note: nota || null } });
      setProgress(0);
      await sendAndProcess(aula.id, file, setProgress);
      navigate(`/aulas/${aula.id}`);
    } catch (err) {
      if (aula) return navigate(`/aulas/${aula.id}`);
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a aula.");
      setProgress(null);
    }
  }

  return (
    <>
      <h1>Nova aula</h1>
      <form onSubmit={onSubmit} noValidate>
        <div className="form-grid">
          <SelectField label="Turma" value={turmaId} onChange={(e) => setTurmaId(e.target.value)} required>
            <option value="" disabled>Escolha a turma</option>
            {turmas.map((t) => <option key={t.id} value={t.id}>{t.name} — {t.escola.name}</option>)}
            <option value="__nova__">+ Cadastrar nova turma</option>
          </SelectField>
          <SelectField label="Disciplina" value={disciplinaId} onChange={(e) => setDisciplinaId(e.target.value)} required>
            <option value="" disabled>Escolha a disciplina</option>
            {disciplinas.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            <option value="__nova__">+ Cadastrar nova disciplina</option>
          </SelectField>
        </div>
        {turmaId === "__nova__" && (
          <NovaTurma onCancel={() => setTurmaId("")} onCreated={(t) => { setTurmas([...turmas, t]); setTurmaId(t.id); }} />
        )}
        {disciplinaId === "__nova__" && (
          <div className="audio-area">
            <TextField label="Nome da disciplina" value={novaDisciplina} maxLength={120}
              onChange={(e) => setNovaDisciplina(e.target.value)} />
            <Button variant="secondary" onClick={() => void salvarDisciplina()} disabled={!novaDisciplina.trim()}>
              Salvar disciplina
            </Button>
          </div>
        )}
        <div className="form-grid">
          <TextField label="Data" type="date" value={data} onChange={(e) => setData(e.target.value)} required />
          <TextAreaField label="Observação (opcional)" value={nota} maxLength={2000} onChange={(e) => setNota(e.target.value)} />
        </div>
        <section className="audio-area" aria-labelledby="audio-titulo">
          <h2 id="audio-titulo">Adicionar áudio da aula</h2>
          <p>Selecione o arquivo de áudio gravado durante sua aula.</p>
          <AudioPicker file={file} onChange={setFile} />
          {progress !== null && <progress value={progress} max={1} aria-label="Envio do áudio" />}
        </section>
        {error && <Banner kind="error">{error}</Banner>}
        <Button type="submit" disabled={!pronto || progress !== null}>Processar aula</Button>
      </form>
    </>
  );
}
```

`frontend/src/pages/AulaPage.tsx`:
```tsx
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api, ApiError, sendAndProcess } from "../api/client";
import type { Aula } from "../api/types";
import { AudioPicker } from "../app/AudioPicker";
import { formatBytes, formatDate, formatDateTime, formatDuration } from "../app/format";
import { JOB_MESSAGE } from "../app/status";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { Dialog } from "../design/components/Dialog";
import { StatusBadge } from "../design/components/StatusBadge";

const PODE_TROCAR = new Set(["DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "ERROR"]);

export function AulaPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [aula, setAula] = useState<Aula | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [confirmarTroca, setConfirmarTroca] = useState(false);
  const [trocando, setTrocando] = useState(false);
  const [confirmarExclusao, setConfirmarExclusao] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setAula(await api<Aula>(`/aulas/${id}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar a aula.");
    }
  }, [id]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  useEffect(() => {
    if (!aula?.job_ativo) return;
    const timer = setInterval(() => void carregar(), 3000);
    return () => clearInterval(timer);
  }, [aula?.job_ativo, carregar]);

  async function enviar() {
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      setAula(await sendAndProcess(id, file, setProgress));
      setFile(null);
      setTrocando(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível enviar o áudio.");
      await carregar();
    } finally {
      setProgress(null);
    }
  }

  async function processar() {
    try {
      setAula(await api<Aula>(`/aulas/${id}/processar`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível processar a aula.");
    }
  }

  async function excluir() {
    await api(`/aulas/${id}`, { method: "DELETE" });
    navigate("/aulas", { replace: true });
  }

  if (!aula) return error ? <Banner kind="error">{error}</Banner> : <p role="status">Carregando…</p>;

  const podeEnviar = !aula.job_ativo && PODE_TROCAR.has(aula.status);
  const mostrarEnvio = podeEnviar && (aula.status === "DRAFT" || aula.status === "ERROR" || trocando);

  return (
    <>
      <div className="page__header">
        <div>
          <h1>Aula de {formatDate(aula.lesson_date)}</h1>
          <p className="meta">{aula.turma.name} · {aula.disciplina.name}</p>
        </div>
        <StatusBadge status={aula.status} />
      </div>

      {aula.alterada_pelo_admin_em && (
        <Banner>Alterada pelo administrador em {formatDateTime(aula.alterada_pelo_admin_em)}.</Banner>
      )}
      {aula.job_ativo && <Banner>{JOB_MESSAGE}</Banner>}
      {aula.status === "ERROR" && aula.error_message && <Banner kind="error">{aula.error_message}</Banner>}
      {error && <Banner kind="error">{error}</Banner>}
      {aula.note && <p>{aula.note}</p>}

      {aula.audio && (
        <section className="audio-area" aria-labelledby="audio-original">
          <h2 id="audio-original">Áudio da aula</h2>
          <audio controls preload="metadata" src={`/api/aulas/${aula.id}/audio`} />
          <p className="meta">
            {aula.audio.original_filename} · <span>{formatDuration(aula.audio.duration_ms)}</span> · {formatBytes(aula.audio.size_bytes)}
          </p>
          {aula.status === "AUDIO_VALIDATED" && <p>A análise das interações estará disponível em breve.</p>}
        </section>
      )}

      {aula.status === "AUDIO_IMPORTED" && !aula.job_ativo && aula.upload_pendente && (
        <section className="audio-area">
          <p>{aula.upload_pendente.original_filename} · {formatBytes(aula.upload_pendente.size_bytes)}</p>
          <Button onClick={() => void processar()}>Processar aula</Button>
        </section>
      )}

      {mostrarEnvio && (
        <section className="audio-area" aria-labelledby="enviar-titulo">
          <h2 id="enviar-titulo">{aula.status === "DRAFT" ? "Adicionar áudio da aula" : "Enviar outro áudio"}</h2>
          <p>Selecione o arquivo de áudio gravado durante sua aula.</p>
          <AudioPicker file={file} onChange={setFile} />
          {progress !== null && <progress value={progress} max={1} aria-label="Envio do áudio" />}
          <Button onClick={() => void enviar()} disabled={!file || progress !== null}>Processar aula</Button>
        </section>
      )}

      <div className="dialog__actions">
        {podeEnviar && aula.status !== "DRAFT" && aula.status !== "ERROR" && !trocando && (
          <Button variant="secondary" onClick={() => setConfirmarTroca(true)}>Substituir áudio</Button>
        )}
        {!aula.job_ativo && <Button variant="tertiary" onClick={() => setConfirmarExclusao(true)}>Excluir aula</Button>}
      </div>

      {confirmarTroca && (
        <Dialog title="Substituir o áudio?" onClose={() => setConfirmarTroca(false)}
          actions={<>
            <Button variant="tertiary" onClick={() => setConfirmarTroca(false)}>Cancelar</Button>
            <Button onClick={() => { setConfirmarTroca(false); setTrocando(true); }}>Escolher novo áudio</Button>
          </>}>
          O arquivo anterior será apagado.
        </Dialog>
      )}
      {confirmarExclusao && (
        <Dialog title="Excluir esta aula?" onClose={() => setConfirmarExclusao(false)}
          actions={<>
            <Button variant="tertiary" onClick={() => setConfirmarExclusao(false)}>Cancelar</Button>
            <Button onClick={() => void excluir()}>Excluir definitivamente</Button>
          </>}>
          O áudio será apagado e não poderá ser recuperado.
        </Dialog>
      )}
    </>
  );
}
```

- [ ] **Step 5: Registrar as rotas em `App.tsx`**

Em `frontend/src/app/App.tsx`, acrescentar os imports:
```tsx
import { AulaPage } from "../pages/AulaPage";
import { Dashboard } from "../pages/Dashboard";
import { NovaAula } from "../pages/NovaAula";
```
e trocar `<Route path="/aulas" element={null} />` por:
```tsx
            <Route path="/aulas" element={<Dashboard />} />
            <Route path="/aulas/nova" element={<NovaAula />} />
            <Route path="/aulas/:id" element={<AulaPage />} />
```

- [ ] **Step 6: Rodar testes, lint e build**

Run (de `frontend/`): `npm test && npm run lint && npm run build`
Expected: PASS; lint limpo; build ok.

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/frontend
git commit -m "feat(web): telas Minhas aulas, Nova Aula com upload e acompanhamento da aula

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 15: Frontend — telas de administração (Contas, Aulas dos professores, Escolas)

**Files:**
- Create: `frontend/src/pages/admin/Contas.tsx`, `frontend/src/pages/admin/AdminAulas.tsx`, `frontend/src/pages/admin/Escolas.tsx`
- Modify: `frontend/src/app/App.tsx` (rotas `/admin/*` com `RequireAdmin`)
- Test: `frontend/src/pages/admin/admin.test.tsx`

**Interfaces:**
- Consumes: `api`, `ApiError`, tipos (Task 12); `useAuth` (Task 13); `RequireAdmin` (Task 13); componentes (Task 12); rotas de admin da API (Tasks 5, 6, 10).
- Produces: páginas `Contas`, `AdminAulas`, `Escolas`.

- [ ] **Step 1: Escrever os testes (falham)**

`frontend/src/pages/admin/admin.test.tsx`:
```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { ADMIN, jsonResponse, mockApi, PROFESSORA, renderApp } from "../../test-utils";

const CONTA = { id: "p1", username: "ana", display_name: "Ana Souza", role: "PROFESSOR", is_active: true,
  must_change_password: false, created_at: "2026-09-22T10:00:00+00:00" };

test("professor não acessa telas de administração", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(PROFESSORA), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/admin/contas");
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
});

test("criar conta mostra a senha provisória uma vez", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([CONTA]),
    "POST /api/admin/contas": () => jsonResponse({ conta: { ...CONTA, id: "p2", username: "bia", display_name: "Bia" },
      senha_provisoria: "Prov-Senha-123" }, 201),
  });
  renderApp("/admin/contas");
  await userEvent.type(await screen.findByLabelText("Nome de usuário"), "bia");
  await userEvent.type(screen.getByLabelText("Nome de exibição"), "Bia");
  await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
  expect(await screen.findByText(/Prov-Senha-123/)).toBeInTheDocument();
  expect(screen.getByText(/não será mostrada de novo/)).toBeInTheDocument();
});

test("excluir conta exige digitar o nome de usuário", async () => {
  let deleted = false;
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse(deleted ? [] : [CONTA]),
    "DELETE /api/admin/contas/p1": (init) => {
      expect(JSON.parse(String(init!.body))).toEqual({ confirmar_username: "ana" });
      deleted = true;
      return jsonResponse(null, 204);
    },
  });
  renderApp("/admin/contas");
  const row = (await screen.findByText("Ana Souza")).closest("tr")!;
  await userEvent.click(within(row).getByRole("button", { name: "Excluir" }));
  const dialog = screen.getByRole("dialog", { name: "Excluir a conta de Ana Souza?" });
  const confirmar = within(dialog).getByRole("button", { name: "Excluir conta" });
  expect(confirmar).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Digite ana para confirmar"), "ana");
  await userEvent.click(confirmar);
  await waitFor(() => expect(screen.queryByText("Ana Souza")).not.toBeInTheDocument());
});

test("agir como professor a partir da lista de aulas", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([CONTA]),
    "GET /api/admin/aulas": () => jsonResponse([{ id: "a1", lesson_date: "2026-09-22", status: "AUDIO_VALIDATED",
      turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" },
      professor: { id: "p1", display_name: "Ana Souza" } }]),
    "POST /api/admin/agir-como": () => jsonResponse({ ...ADMIN, acting_as: { id: "p1", display_name: "Ana Souza" } }),
    "GET /api/aulas/a1": () => jsonResponse({ id: "a1", lesson_date: "2026-09-22", status: "AUDIO_VALIDATED",
      turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null,
      error_message: null, audio: null, upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null }),
  });
  renderApp("/admin/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Agir como Ana Souza" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1"));
  expect(await screen.findByText("Você está agindo como: Ana Souza")).toBeInTheDocument();
});

test("juntar escolas duplicadas", async () => {
  let merged = false;
  const escolas = [
    { id: "e1", name: "Escola São José", municipality: "Mossoró", region: null },
    { id: "e2", name: "E. São José", municipality: "Mossoró", region: null },
  ];
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/escolas": () => jsonResponse(merged ? [escolas[0]] : escolas),
    "POST /api/admin/escolas/e2/juntar": (init) => {
      expect(JSON.parse(String(init!.body))).toEqual({ destino_id: "e1" });
      merged = true;
      return jsonResponse(escolas[0]);
    },
  });
  renderApp("/admin/escolas");
  const row = (await screen.findByText("E. São José")).closest("tr")!;
  await userEvent.selectOptions(within(row).getByLabelText("Juntar com"), "e1");
  await userEvent.click(within(row).getByRole("button", { name: "Juntar" }));
  await waitFor(() => expect(screen.queryByText("E. São José")).not.toBeInTheDocument());
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run (de `frontend/`): `npm test`
Expected: FAIL (páginas de admin ausentes).

- [ ] **Step 3: Implementar as páginas**

`frontend/src/pages/admin/Contas.tsx`:
```tsx
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api/client";
import type { Conta, Role } from "../../api/types";
import { Banner } from "../../design/components/Banner";
import { Button } from "../../design/components/Button";
import { Dialog } from "../../design/components/Dialog";
import { SelectField, TextField } from "../../design/components/Field";

export function Contas() {
  const [contas, setContas] = useState<Conta[]>([]);
  const [form, setForm] = useState({ username: "", display_name: "", role: "PROFESSOR" as Role });
  const [senha, setSenha] = useState<{ nome: string; valor: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [excluindo, setExcluindo] = useState<Conta | null>(null);
  const [confirmacao, setConfirmacao] = useState("");

  const carregar = useCallback(() => api<Conta[]>("/admin/contas").then(setContas), []);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function acao(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await carregar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível concluir a ação.");
    }
  }

  async function criar(e: FormEvent) {
    e.preventDefault();
    await acao(async () => {
      const r = await api<{ conta: Conta; senha_provisoria: string }>("/admin/contas", { method: "POST", json: form });
      setSenha({ nome: r.conta.display_name, valor: r.senha_provisoria });
      setForm({ username: "", display_name: "", role: "PROFESSOR" });
    });
  }

  async function redefinir(c: Conta) {
    await acao(async () => {
      const r = await api<{ senha_provisoria: string }>(`/admin/contas/${c.id}/senha-provisoria`, { method: "POST" });
      setSenha({ nome: c.display_name, valor: r.senha_provisoria });
    });
  }

  async function excluir() {
    const alvo = excluindo!;
    setExcluindo(null);
    setConfirmacao("");
    await acao(() => api(`/admin/contas/${alvo.id}`, { method: "DELETE", json: { confirmar_username: alvo.username } }));
  }

  return (
    <>
      <h1>Contas</h1>
      {senha && (
        <Banner kind="success">
          Senha provisória de {senha.nome}: <strong>{senha.valor}</strong>. Anote e entregue ao professor; ela não será
          mostrada de novo. No primeiro acesso, o professor cria uma senha própria.
        </Banner>
      )}
      {error && <Banner kind="error">{error}</Banner>}
      <form className="audio-area" onSubmit={criar} aria-label="Nova conta">
        <h2>Nova conta</h2>
        <div className="form-grid">
          <TextField label="Nome de usuário" value={form.username} maxLength={64} required
            onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <TextField label="Nome de exibição" value={form.display_name} maxLength={120} required
            onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
          <SelectField label="Perfil" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="PROFESSOR">Professor</option>
            <option value="ADMIN_LOCAL">Administrador</option>
          </SelectField>
        </div>
        <Button type="submit">Criar conta</Button>
      </form>
      <table className="table">
        <thead>
          <tr><th>Nome</th><th>Usuário</th><th>Perfil</th><th>Situação</th><th><span className="visually-hidden">Ações</span></th></tr>
        </thead>
        <tbody>
          {contas.map((c) => (
            <tr key={c.id}>
              <td>{c.display_name}</td>
              <td>{c.username}</td>
              <td>{c.role === "ADMIN_LOCAL" ? "Administrador" : "Professor"}</td>
              <td>{c.is_active ? "Ativa" : "Desativada"}</td>
              <td>
                <Button variant="tertiary" onClick={() => void acao(() => api(`/admin/contas/${c.id}`, { method: "PATCH", json: { is_active: !c.is_active } }))}>
                  {c.is_active ? "Desativar" : "Reativar"}
                </Button>
                <Button variant="tertiary" onClick={() => void redefinir(c)}>Redefinir senha</Button>
                <Button variant="tertiary" onClick={() => setExcluindo(c)}>Excluir</Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {excluindo && (
        <Dialog title={`Excluir a conta de ${excluindo.display_name}?`} onClose={() => setExcluindo(null)}
          actions={<>
            <Button variant="tertiary" onClick={() => setExcluindo(null)}>Cancelar</Button>
            <Button onClick={() => void excluir()} disabled={confirmacao.trim().toLowerCase() !== excluindo.username}>Excluir conta</Button>
          </>}>
          <p>Todos os áudios dessa conta serão apagados e não poderão ser recuperados.</p>
          <TextField label={`Digite ${excluindo.username} para confirmar`} value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)} />
        </Dialog>
      )}
    </>
  );
}
```

`frontend/src/pages/admin/AdminAulas.tsx`:
```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/client";
import type { AulaResumo, Conta, Me } from "../../api/types";
import { useAuth } from "../../app/AuthContext";
import { formatDate } from "../../app/format";
import { Button } from "../../design/components/Button";
import { EmptyState } from "../../design/components/EmptyState";
import { SelectField } from "../../design/components/Field";
import { StatusBadge } from "../../design/components/StatusBadge";

export function AdminAulas() {
  const { setMe } = useAuth();
  const navigate = useNavigate();
  const [contas, setContas] = useState<Conta[]>([]);
  const [filtro, setFiltro] = useState("");
  const [aulas, setAulas] = useState<AulaResumo[]>([]);

  useEffect(() => {
    api<Conta[]>("/admin/contas").then(setContas).catch(() => setContas([]));
  }, []);
  useEffect(() => {
    api<AulaResumo[]>(filtro ? `/admin/aulas?professor_id=${filtro}` : "/admin/aulas").then(setAulas).catch(() => setAulas([]));
  }, [filtro]);

  async function agirComo(aula: AulaResumo) {
    setMe(await api<Me>("/admin/agir-como", { method: "POST", json: { professor_id: aula.professor!.id } }));
    navigate(`/aulas/${aula.id}`);
  }

  return (
    <>
      <h1>Aulas dos professores</h1>
      <SelectField label="Professor" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
        <option value="">Todos</option>
        {contas.map((c) => <option key={c.id} value={c.id}>{c.display_name}</option>)}
      </SelectField>
      {aulas.length === 0 ? (
        <EmptyState title="Nenhuma aula encontrada">Quando os professores adicionarem aulas, elas aparecem aqui.</EmptyState>
      ) : (
        <ul className="list">
          {aulas.map((a) => (
            <li key={a.id} className="list__item">
              <div>
                <strong>{a.professor?.display_name}</strong>
                <p className="meta">{formatDate(a.lesson_date)} · {a.turma.name} · {a.disciplina.name}</p>
              </div>
              <StatusBadge status={a.status} />
              <Button variant="secondary" onClick={() => void agirComo(a)}>Agir como {a.professor?.display_name}</Button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
```

`frontend/src/pages/admin/Escolas.tsx`:
```tsx
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { Escola } from "../../api/types";
import { Banner } from "../../design/components/Banner";
import { Button } from "../../design/components/Button";
import { SelectField, TextField } from "../../design/components/Field";

function LinhaEscola({ escola, outras, onChange }: { escola: Escola; outras: Escola[]; onChange: () => Promise<void> }) {
  const [nome, setNome] = useState(escola.name);
  const [municipio, setMunicipio] = useState(escola.municipality ?? "");
  const [destino, setDestino] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível concluir a ação.");
    }
  }

  return (
    <tr>
      <td>
        <span className="meta">{escola.name}</span>
        <TextField label="Nome" value={nome} onChange={(e) => setNome(e.target.value)} maxLength={200} />
      </td>
      <td><TextField label="Município" value={municipio} onChange={(e) => setMunicipio(e.target.value)} maxLength={120} /></td>
      <td>
        <Button variant="tertiary" onClick={() => void run(() => api(`/admin/escolas/${escola.id}`, { method: "PATCH", json: { name: nome, municipality: municipio || null } }))}>
          Salvar
        </Button>
      </td>
      <td>
        <SelectField label="Juntar com" value={destino} onChange={(e) => setDestino(e.target.value)}>
          <option value="">Escolha a escola que fica</option>
          {outras.map((o) => <option key={o.id} value={o.id}>{o.name}{o.municipality ? ` (${o.municipality})` : ""}</option>)}
        </SelectField>
        <Button variant="tertiary" disabled={!destino}
          onClick={() => void run(() => api(`/admin/escolas/${escola.id}/juntar`, { method: "POST", json: { destino_id: destino } }))}>
          Juntar
        </Button>
        {error && <Banner kind="error">{error}</Banner>}
      </td>
    </tr>
  );
}

export function Escolas() {
  const [escolas, setEscolas] = useState<Escola[]>([]);
  const carregar = useCallback(async () => setEscolas(await api<Escola[]>("/escolas")), []);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <>
      <h1>Escolas</h1>
      <p>Corrija nomes e junte escolas cadastradas em duplicidade. As turmas da escola juntada passam para a escola que fica.</p>
      <table className="table">
        <thead>
          <tr><th>Nome</th><th>Município</th><th><span className="visually-hidden">Salvar</span></th><th>Duplicidade</th></tr>
        </thead>
        <tbody>
          {escolas.map((e) => (
            <LinhaEscola key={e.id} escola={e} outras={escolas.filter((o) => o.id !== e.id)} onChange={carregar} />
          ))}
        </tbody>
      </table>
    </>
  );
}
```

(O `<span>` com o nome atual deixa a linha identificável por leitores de tela e pelos testes; o campo ao lado edita o nome.)

- [ ] **Step 4: Registrar as rotas em `App.tsx`**

Acrescentar os imports:
```tsx
import { AdminAulas } from "../pages/admin/AdminAulas";
import { Contas } from "../pages/admin/Contas";
import { Escolas } from "../pages/admin/Escolas";
import { RequireAdmin, RequireAuth } from "./RequireAuth";
```
(substituindo o import anterior de `RequireAuth`) e, dentro do `<Route element={<RequireAuth><Layout /></RequireAuth>}>`, depois das rotas de aulas:
```tsx
            <Route path="/admin/contas" element={<RequireAdmin><Contas /></RequireAdmin>} />
            <Route path="/admin/aulas" element={<RequireAdmin><AdminAulas /></RequireAdmin>} />
            <Route path="/admin/escolas" element={<RequireAdmin><Escolas /></RequireAdmin>} />
```

- [ ] **Step 5: Rodar testes, lint e build**

Run (de `frontend/`): `npm test && npm run lint && npm run build`
Expected: PASS; lint limpo; build ok.

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/frontend
git commit -m "feat(web): telas de administração de contas, aulas dos professores e escolas

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---
### Task 16: Implantação (Compose, nginx, imagens), teste de aceitação e documentação

**Files:**
- Create: `fias-ed-web/deploy/db.Dockerfile`, `fias-ed-web/deploy/nginx.conf`, `fias-ed-web/deploy/web.Dockerfile`
- Create: `fias-ed-web/docker-compose.yml`
- Modify: `fias-ed-web/backend/app/jobs/worker.py` (arquivo de batimento para o healthcheck)
- Create: `fias-ed-web/scripts/smoke.py`
- Create: `fias-ed-web/README.md`
- Modify: `fias-ed-shared/docs/PRIVACY.md` (seção do Web), `ARCHITECTURE.md` (raiz, seção Web)
- Test: `fias-ed-web/backend/tests/test_worker_heartbeat.py`

**Interfaces:**
- Consumes: imagens/Dockerfile das Tasks 1 e 12; toda a API.
- Produces: `app.jobs.worker.HEARTBEAT_FILE` e `beat() -> None`; `docker compose up -d --build` sobe `db`, `migrate` (executa uma vez), `api`, `worker`, `web`; `python scripts/smoke.py --admin-user U` (teste de aceitação, só biblioteca padrão).

- [ ] **Step 1: Batimento do worker (teste primeiro)**

`backend/tests/test_worker_heartbeat.py`:
```python
import time

from app.jobs import worker


def test_beat_touches_file(tmp_path, monkeypatch):
    target = tmp_path / "hb"
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", target)
    worker.beat()
    assert target.exists() and time.time() - target.stat().st_mtime < 5
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_worker_heartbeat.py`
Expected: FAIL (`AttributeError: ... HEARTBEAT_FILE`).

Em `app/jobs/worker.py`, acrescentar `from pathlib import Path` aos imports e, antes de `run_once`:
```python
HEARTBEAT_FILE = Path("/tmp/fias-ed-worker-heartbeat")  # nosec B108 - lido só pelo healthcheck do container


def beat() -> None:
    HEARTBEAT_FILE.touch()
```
e, em `main()`, chamar `beat()` como primeira linha dentro do `while True:`.

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS.

- [ ] **Step 2: Imagens e nginx**

`fias-ed-web/deploy/db.Dockerfile` (o script de init vai dentro da imagem; nada é montado do Windows):
```dockerfile
FROM postgres:16-alpine
COPY db-init/ /docker-entrypoint-initdb.d/
```

`fias-ed-web/deploy/nginx.conf`:
```nginx
server {
    listen 8080;
    server_name _;
    server_tokens off;
    client_max_body_size 1536m;
    root /usr/share/nginx/html;

    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header X-Frame-Options "DENY" always;

    location /api/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_request_buffering off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /assets/ {
        try_files $uri =404;
        expires 7d;
    }

    location / {
        try_files $uri /index.html;
    }
}
```
(Nenhuma `location` usa `add_header`: no nginx, um `add_header` dentro de `location` anula os cabeçalhos do `server`.)

`fias-ed-web/deploy/web.Dockerfile`:
```dockerfile
# Contexto de build: raiz do monorepo.
FROM node:24-alpine AS build
WORKDIR /build/fias-ed-web/frontend
COPY fias-ed-shared/design-tokens /build/fias-ed-shared/design-tokens
COPY fias-ed-shared/schemas /build/fias-ed-shared/schemas
COPY fias-ed-web/frontend/package.json fias-ed-web/frontend/package-lock.json ./
RUN npm ci
COPY fias-ed-web/frontend ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY fias-ed-web/deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/fias-ed-web/frontend/dist /usr/share/nginx/html
EXPOSE 8080
```

- [ ] **Step 3: `docker-compose.yml`**

```yaml
name: fias-ed

x-hardening: &hardening
  restart: unless-stopped
  security_opt: ["no-new-privileges:true"]
  cap_drop: ["ALL"]

x-api-image: &api-image
  build:
    context: ..
    dockerfile: fias-ed-web/backend/Dockerfile
    target: prod
  image: fias-ed-api:local

services:
  db:
    <<: *hardening
    build:
      context: ./deploy
      dockerfile: db.Dockerfile
    user: "70:70"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?defina POSTGRES_PASSWORD no .env}
      POSTGRES_DB: fias_ed
      FIAS_ED_MIGRATOR_PASSWORD: ${FIAS_ED_MIGRATOR_PASSWORD:?defina no .env}
      FIAS_ED_APP_PASSWORD: ${FIAS_ED_APP_PASSWORD:?defina no .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks: [internal]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d fias_ed"]
      interval: 5s
      timeout: 3s
      retries: 20

  migrate:
    <<: *api-image
    security_opt: ["no-new-privileges:true"]
    cap_drop: ["ALL"]
    restart: "no"
    command: ["alembic", "upgrade", "head"]
    environment:
      MIGRATOR_DATABASE_URL: postgresql+psycopg://fias_ed_migrator:${FIAS_ED_MIGRATOR_PASSWORD}@db:5432/fias_ed
    networks: [internal]
    depends_on:
      db:
        condition: service_healthy

  api:
    <<: [*hardening, *api-image]
    environment: &api-env
      DATABASE_URL: postgresql+psycopg://fias_ed_app:${FIAS_ED_APP_PASSWORD}@db:5432/fias_ed
      DEVICE_ID: ${DEVICE_ID:-fias-ed-web}
      MAX_UPLOAD_BYTES: ${MAX_UPLOAD_BYTES:-1610612736}
      MIN_AUDIO_SECONDS: ${MIN_AUDIO_SECONDS:-60}
      MAX_AUDIO_SECONDS: ${MAX_AUDIO_SECONDS:-9000}
    volumes:
      - audio_store:/data/audio
    networks: [internal, edge]
    depends_on:
      migrate:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 10

  worker:
    <<: [*hardening, *api-image]
    command: ["python", "-m", "app.jobs.worker"]
    environment: *api-env
    volumes:
      - audio_store:/data/audio
    networks: [internal]
    depends_on:
      migrate:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "python", "-c", "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime('/tmp/fias-ed-worker-heartbeat') < 60 else 1)"]
      interval: 15s
      timeout: 5s
      retries: 5

  web:
    <<: *hardening
    build:
      context: ..
      dockerfile: fias-ed-web/deploy/web.Dockerfile
    ports:
      - "127.0.0.1:8080:8080"
    networks: [edge]
    depends_on:
      api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]
      interval: 10s
      timeout: 3s
      retries: 10

networks:
  internal:
    internal: true
  edge: {}

volumes:
  pgdata:
  audio_store:
```

Subir e conferir (de `fias-ed-web/`, com `.env` criado a partir do `.env.example`, senhas só com letras, números, `-` e `_`):
```bash
docker compose up -d --build
docker compose ps
docker compose run --rm api python -m app.cli create-admin --username pesquisador --display-name "Pesquisador"
```
Expected: `db`, `api`, `worker`, `web` com estado `healthy`; `migrate` `exited (0)`; a coluna de portas mostra só `127.0.0.1:8080->8080/tcp` no `web`. Se o `db` não iniciar com `user: "70:70"` (permissão no volume), remover o volume de teste (`docker compose down -v`, só em instalação nova) e subir de novo; se persistir, registrar no relatório e remover a linha `user` (a imagem oficial troca para o usuário `postgres` sozinha).

- [ ] **Step 4: Teste de aceitação `scripts/smoke.py`**

```python
#!/usr/bin/env python3
"""Teste de aceitação de ponta a ponta do FIAS-ED Web (W1) em http://localhost:8080.

Uso (de fias-ed-web/):  python scripts/smoke.py --admin-user pesquisador
A senha do admin é pedida no terminal. O script cria uma conta temporária de
professor, percorre o fluxo completo e exclui a conta no fim. Usa só a
biblioteca padrão (o áudio de teste é gerado com o módulo wave).
"""
import argparse
import getpass
import io
import json
import math
import struct
import sys
import time
import urllib.error
import urllib.request
import wave
from urllib.parse import quote

BASE = "http://localhost:8080"
CABECALHOS = {
    "content-security-policy": "frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=()",
}


class Client:
    """Cliente HTTP com cookies próprios (o cookiejar não envia cookies Secure em http://localhost)."""

    def __init__(self):
        self.cookies: dict[str, str] = {}

    def request(self, method, path, body=None, raw=None, headers=None):
        h = dict(headers or {})
        if self.cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if method != "GET" and "fias_csrf" in self.cookies:
            h["X-CSRF-Token"] = self.cookies["fias_csrf"]
        data = raw
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - URL fixa local
                status, rh, payload = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, rh, payload = e.code, e.headers, e.read()
        for cookie in rh.get_all("Set-Cookie") or []:
            name, _, rest = cookie.partition("=")
            value = rest.split(";", 1)[0]
            if value and value != '""':
                self.cookies[name] = value
            else:
                self.cookies.pop(name, None)
        text = payload.decode("utf-8") if payload else ""
        is_json = (rh.get("Content-Type") or "").startswith("application/json")
        return status, rh, (json.loads(text) if text and is_json else text)


def wav_bytes(seconds=65, rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(seconds * rate)))
    return buf.getvalue()


def check(cond, msg):
    if not cond:
        print(f"FALHOU: {msg}")
        sys.exit(1)
    print(f"ok  {msg}")


def step(resp, status, msg):
    code, _, body = resp
    check(code == status, f"{msg}" if code == status else f"{msg} — HTTP {code}: {body}")
    return body


def wait(client, aula_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        _, _, body = client.request("GET", f"/api/aulas/{aula_id}")
        if not body.get("job_ativo") and body.get("status") in ("AUDIO_VALIDATED", "ERROR"):
            return body
        time.sleep(2)
    check(False, f"aula {aula_id} não terminou em {timeout}s")


def escola(client):
    code, _, body = client.request("POST", "/api/escolas", {"name": "Escola do teste automático"})
    return body["duplicatas"][0]["id"] if code == 409 else step((code, None, body), 201, "escola criada")["id"]


def nova_aula(client, rotulo):
    turma = step(client.request("POST", "/api/turmas", {"name": f"Turma {rotulo}", "escola_id": escola(client)}), 201,
                 f"turma ({rotulo})")
    disc = step(client.request("POST", "/api/disciplinas", {"name": f"Disciplina {rotulo}"}), 201, f"disciplina ({rotulo})")
    return step(client.request("POST", "/api/aulas", {"turma_id": turma["id"], "disciplina_id": disc["id"],
                                                      "lesson_date": "2026-09-22"}), 201, f"aula ({rotulo})")["id"]


def enviar_e_processar(client, aula_id, nome, rotulo):
    step(client.request("PUT", f"/api/aulas/{aula_id}/audio", raw=wav_bytes(),
                        headers={"X-Filename": quote(nome), "Content-Type": "application/octet-stream"}),
         201, f"envio do áudio ({rotulo})")
    step(client.request("POST", f"/api/aulas/{aula_id}/processar"), 202, f"processamento solicitado ({rotulo})")
    return wait(client, aula_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-user", required=True)
    args = ap.parse_args()
    admin_pw = getpass.getpass("Senha do administrador: ")

    code, headers, _ = Client().request("GET", "/")
    check(code == 200, "Home responde em http://localhost:8080")
    for name, fragment in CABECALHOS.items():
        check(fragment in (headers.get(name) or ""), f"cabeçalho {name}")

    admin = Client()
    step(admin.request("POST", "/api/auth/login", {"username": args.admin_user, "password": admin_pw}), 200, "admin entra")
    username = f"smoke{int(time.time())}"
    criada = step(admin.request("POST", "/api/admin/contas", {"username": username, "display_name": "Professora Teste"}),
                  201, "admin cria professor com senha provisória")
    prof_id, provisoria = criada["conta"]["id"], criada["senha_provisoria"]
    prof = Client()
    try:
        step(prof.request("POST", "/api/auth/login", {"username": username, "password": provisoria}), 200,
             "professor entra com a senha provisória")
        step(prof.request("GET", "/api/aulas"), 403, "senha provisória exige troca")
        step(prof.request("POST", "/api/auth/password", {"current_password": provisoria,
                                                          "new_password": "senha-do-smoke-123"}), 200, "professor troca a senha")

        body = enviar_e_processar(prof, nova_aula(prof, "smoke"), "aula teste.wav", "professor")
        check(body["status"] == "AUDIO_VALIDATED", "aula chega a AUDIO_VALIDATED")

        body = enviar_e_processar(prof, nova_aula(prof, "extensão falsa"), "gravacao.mp3", "extensão falsa")
        check(body["status"] == "ERROR" and body["error_code"] == "AUDIO_FORMAT_MISMATCH" and body["error_message"],
              "extensão falsa termina em AUDIO_FORMAT_MISMATCH com mensagem humana")

        step(admin.request("POST", "/api/admin/agir-como", {"professor_id": prof_id}), 200, "admin age como o professor")
        feita = nova_aula(admin, "admin")
        body = enviar_e_processar(admin, feita, "aula do admin.wav", "admin")
        check(body["status"] == "AUDIO_VALIDATED", "aula criada pelo admin chega a AUDIO_VALIDATED")
        step(admin.request("DELETE", "/api/admin/agir-como"), 200, "admin volta à própria conta")
        vista = step(prof.request("GET", f"/api/aulas/{feita}"), 200, "professor vê a aula criada pelo admin")
        check(bool(vista["alterada_pelo_admin_em"]), "aviso 'alterada pelo administrador' presente")
    finally:
        admin.request("DELETE", "/api/admin/agir-como")
        code, _, _ = admin.request("DELETE", f"/api/admin/contas/{prof_id}", {"confirmar_username": username})
        print("ok  conta temporária excluída" if code == 204 else f"ATENÇÃO: excluir a conta {username} manualmente (HTTP {code})")
    print("\nSMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run (de `fias-ed-web/`, com o sistema no ar): `python scripts/smoke.py --admin-user pesquisador`
Expected: todas as linhas `ok` e `SMOKE OK` no fim.

- [ ] **Step 5: `fias-ed-web/README.md`**

Escrever o README com as seções abaixo (texto em pt-BR, comandos exatos):

1. **O que é** — FIAS-ED Web, fatia W1: entrada, contas, aulas, envio e conferência do áudio. Link para o spec `../docs/superpowers/specs/2026-09-22-fias-ed-web-w1-fundacao-design.md`.
2. **Pré-requisitos** — Docker Desktop com Docker Compose v2; Python 3 no Windows só para `scripts/smoke.py`.
3. **Primeira instalação** — `cp .env.example .env`; trocar as três senhas por valores longos usando só letras, números, `-` e `_` (elas vão dentro de URLs de conexão); `docker compose up -d --build`; `docker compose run --rm api python -m app.cli create-admin --username <usuario> --display-name "<Nome>"`; abrir **http://localhost:8080** (usar `localhost`, não o IP).
4. **Uso diário** — `docker compose up -d` / `docker compose stop`; `docker compose logs -f api worker`.
5. **Testes** — backend: `docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q`; frontend: `cd frontend && npm ci && npm test && npm run lint`; aceitação: `python scripts/smoke.py --admin-user <usuario>`.
6. **Auditorias** — comandos `bandit -r app --severity-level high`, `pip-audit --skip-editable` (via `docker compose -f docker-compose.test.yml run --rm api-test ...`), `npm audit --audit-level=high` (em `frontend/`), com a data e o resultado da última execução (preencher com as saídas das Tasks 11 e 18).
7. **Backup e restauração** —
   - Banco: `docker compose exec -T db pg_dump -U postgres -Fc fias_ed > backup-fias-ed.dump`; restauração: `docker compose exec -T db pg_restore -U postgres -d fias_ed --clean < backup-fias-ed.dump`.
   - Áudios: `docker run --rm -v fias-ed_audio_store:/dados:ro -v "$PWD":/backup alpine tar czf /backup/audios.tgz -C /dados .`; restauração: `docker run --rm -v fias-ed_audio_store:/dados -v "$PWD":/backup alpine tar xzf /backup/audios.tgz -C /dados`.
   - Aviso: o backup contém áudios de aulas e dados pessoais; guardar em local protegido.
8. **Segurança** — resumo: porta só em `127.0.0.1:8080`; banco em rede interna sem porta; `fias_ed_app` sem DDL; migrações por serviço `migrate` com `fias_ed_migrator`; containers não-root, `no-new-privileges`, `cap_drop: ALL`; cabeçalhos CSP/nosniff/Referrer-Policy/Permissions-Policy/frame-ancestors.
9. **Dependências** (prompt §68) — tabela com nome, licença e motivo, sem telemetria:

| Dependência | Licença | Motivo |
|---|---|---|
| FastAPI, Starlette | MIT, BSD-3 | API HTTP |
| Uvicorn | BSD-3 | servidor ASGI |
| Pydantic, pydantic-settings | MIT | validação e configuração |
| SQLAlchemy, Alembic | MIT | acesso ao banco e migrações |
| psycopg 3 | LGPL-3.0 | driver PostgreSQL |
| argon2-cffi | MIT | hash de senha Argon2id |
| FFmpeg (ffprobe) | LGPL/GPL (pacote Debian) | leitura dos metadados do áudio |
| PostgreSQL 16 | PostgreSQL License | banco de dados |
| nginx (nginx-unprivileged) | BSD-2 | servidor web e proxy |
| React, React DOM, React Router | MIT | interface |
| Vite, TypeScript, Vitest, Testing Library, ESLint | MIT/Apache-2.0 | build e testes (só desenvolvimento) |

- [ ] **Step 6: Documentação compartilhada**

Em `fias-ed-shared/docs/PRIVACY.md`, acrescentar ao fim:
```markdown
## FIAS-ED Web (fatia W1)

- **Onde ficam os dados:** volumes Docker `pgdata` (banco) e `audio_store`
  (áudios originais) no PC do pesquisador. A única porta publicada é
  `127.0.0.1:8080`; o banco fica numa rede interna sem porta publicada.
  Nenhum dado é enviado a serviços externos.
- **Contas:** professor entra com usuário e senha (hash Argon2id). Senhas
  provisórias, criadas pelo administrador, precisam ser trocadas no primeiro
  acesso.
- **Acesso do pesquisador:** a conta `ADMIN_LOCAL` tem acesso total às aulas
  dos professores (ler, ouvir o áudio, criar, alterar e excluir em nome do
  professor). Toda leitura ou alteração feita em nome de um professor é
  registrada na tabela interna `acesso_admin` (quem, qual professor, qual
  recurso, qual ação, quando), e o professor vê na aula o aviso "Alterada pelo
  administrador em <data>".
- **Escolas:** cadastro comum a todos os professores (nome, município,
  região), sem dado pessoal.
- **Exclusão:** excluir uma aula apaga o arquivo de áudio na hora; os
  registros ficam marcados como excluídos (`deleted_at`) e deixam de aparecer
  em qualquer consulta. Excluir uma conta aplica a mesma regra a todas as
  aulas do professor.
- **Logs:** registram só identificadores, status, duração e códigos de erro;
  nunca senha, token, nomes, nomes de arquivo ou conteúdo das aulas.
```

Em `ARCHITECTURE.md` (raiz), na seção "### Web (subprojeto 2, a construir)": trocar o título por "### Web (subprojeto 2 — fatia W1 implementada)" e acrescentar, depois do parágrafo existente:
```markdown
Na fatia W1, o Compose sobe cinco serviços: `web` (nginx não-root com o React
compilado e os cabeçalhos de segurança; única porta publicada, em
`127.0.0.1:8080`), `api` (FastAPI), `worker` (mesma imagem da API; consome a
tabela `job` do PostgreSQL com `SELECT … FOR UPDATE SKIP LOCKED`), `db`
(PostgreSQL 16 em rede interna, sem porta publicada) e `migrate` (roda o
Alembic uma vez, com o usuário `fias_ed_migrator`). A API e o worker usam o
usuário `fias_ed_app`, sem permissão de DDL. A sessão fica no servidor
(cookie opaco + token CSRF), na mesma origem do frontend, sem CORS. O ciclo da
aula em W1 vai de `DRAFT` a `AUDIO_VALIDATED`; W2 continua a partir daí.
Detalhes: `docs/superpowers/specs/2026-09-22-fias-ed-web-w1-fundacao-design.md`.
```

Run (de `fias-ed-shared/engine-py`): `.venv/Scripts/python -m pytest -q`
Expected: PASS (os testes de documentação do shared verificam a linguagem de `PRIVACY.md` e `ARCHITECTURE.md`; nenhuma palavra da lista proibida fora de crases).

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web ARCHITECTURE.md fias-ed-shared/docs/PRIVACY.md
git commit -m "feat(web): Compose endurecido, nginx com cabeçalhos de segurança, teste de aceitação e documentação

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 17: Revisão visual com Impeccable e critério do §84

**Files:**
- Modify: `frontend/src/design/*.css`, `frontend/src/design/components/*.tsx`, `frontend/src/pages/**/*.tsx` (somente o que a revisão apontar)

**Interfaces:**
- Consumes: telas das Tasks 13–15 rodando em `http://localhost:8080`.
- Produces: telas revisadas; relatório com os achados do Impeccable, as correções e a tabela do §84.

- [x] **Step 1: Pré-requisito**

Confirmar que o Impeccable está disponível na sessão (skill `impeccable` listada). Se não estiver, parar e reportar **BLOCKED — Impeccable não instalado** (o pesquisador instala com `npx impeccable install --global --providers=claude -y`). Não substituir a revisão por outra ferramenta.

- [x] **Step 2: Preparar dados de exemplo**

Gerar um áudio de exemplo (de `fias-ed-web/`):
```bash
python -c "import sys, pathlib; sys.path.insert(0, 'scripts'); import smoke; pathlib.Path('exemplo.wav').write_bytes(smoke.wav_bytes())"
cp exemplo.wav exemplo-falso.mp3
```
Com o sistema no ar (`docker compose up -d --build`), pela interface: entrar como admin, criar uma conta de professor, entrar como professor (trocando a senha provisória) e criar pelo menos três aulas — uma com `exemplo.wav` (fica conferida), uma com `exemplo-falso.mp3` (fica com erro) e uma sem áudio. Criar uma segunda conta sem aulas para ver o estado vazio. Não versionar `exemplo.wav` nem `exemplo-falso.mp3` (apagar ao fim da task).

- [x] **Step 3: Ciclo de revisão (prompt §2)**

Para cada tela — **Home**, **Minhas aulas** (vazia e com aulas), **Nova Aula** (incluindo "Cadastrar nova turma/escola" e o envio com barra de progresso), **Aula** (processando, com erro, conferida), em largura de 360 px e de 1280 px:
1. Rodar a revisão do Impeccable sobre a tela real e os arquivos da tela.
2. Corrigir os achados dentro das regras: só tokens do shared (`tokens.css`), nenhuma cor nova além das semânticas, sem gradiente, glow, glassmorphism, blobs, ícones de estrela/robô/cérebro, sombras só em foco e diálogos, `border-radius` só `--radius-sm`/`--radius-md`, Rokkitt só em títulos (≥ 24 px) e nunca em tabelas, campos ou números, Ubuntu no resto, sem atributo `style`.
3. `cd frontend && npm test && npm run lint && npm run build`.
4. Revisar de novo com o Impeccable até não haver achado relevante.

- [x] **Step 4: Critério visual final (prompt §84)**

Responder no relatório: "Esta interface parece um produto criado especificamente para professores ou parece um template gerado por IA?" e preencher a tabela, com evidência (arquivo/tela) por item: hierarquia; espaçamento; tipografia; contraste; consistência; uso da paleta; uso correto de Ubuntu; uso editorial de Rokkitt; responsividade; densidade; legibilidade; ausência de gradientes; ausência de componentes decorativos desnecessários. Qualquer item reprovado volta ao Step 3.

- [x] **Step 5: Rebuild, aceitação e commit**

Run: `docker compose up -d --build web` e `python scripts/smoke.py --admin-user <usuario>`
Expected: `SMOKE OK`.

```bash
git add fias-ed-web/frontend
git commit -m "style(web): revisão visual com Impeccable e critério do §84 nas telas de W1

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 18: Verificação final da fatia W1

**Files:**
- Modify: `fias-ed-web/README.md` (resultados das auditorias, se mudaram)

**Interfaces:**
- Consumes: tudo.
- Produces: evidência dos 10 critérios de aceite do spec §14, registrada no corpo do commit.

- [ ] **Step 1: Suítes e auditorias**

Run (de `fias-ed-web/`):
```bash
docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q
docker compose -f docker-compose.test.yml run --rm api-test bandit -r app --severity-level high
docker compose -f docker-compose.test.yml run --rm api-test pip-audit --skip-editable
cd frontend && npm ci && npm test && npm run lint && npm run build && npm audit --audit-level=high && cd ..
```
Expected: todos os testes PASS; bandit sem achados altos; pip-audit e npm audit sem vulnerabilidade alta/crítica não tratada (tratamentos registrados no README).

Run (de `fias-ed-shared/engine-py`): `.venv/Scripts/python -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Sistema no ar**

Run (de `fias-ed-web/`):
```bash
docker compose up -d --build
docker compose ps
docker compose ps --format "{{.Service}} {{.Publishers}}"
for s in api worker web db; do echo "$s: $(docker compose exec -T $s id -u)"; done
python scripts/smoke.py --admin-user <usuario>
```
Expected: todos `healthy` (`migrate` saiu com 0); só `web` publica, e só em `127.0.0.1:8080`; nenhum `id -u` igual a `0`; `SMOKE OK`.

- [ ] **Step 3: Fontes somente leitura intactas**

Run (da raiz do monorepo):
```bash
cd fias-ed-shared && engine-py/.venv/Scripts/python scripts/source_snapshot.py verify ../fias-ed-web/.source-snapshot.json
```
Expected: `OK — nenhuma alteração`.

- [ ] **Step 4: Conferir os critérios de aceite do spec §14, um a um**

1. Compose: quatro serviços saudáveis, só `127.0.0.1:8080` publicado (Step 2).
2. Fluxo completo com senha provisória até `AUDIO_VALIDATED`; extensão falsa → `AUDIO_FORMAT_MISMATCH` com mensagem humana (smoke).
3. Admin age como professor; aviso "Alterada pelo administrador"; `acesso_admin` registrado (smoke + `test_admin_act_as_flow.py`).
4. pytest e vitest verdes, incluindo segurança (Step 1).
5. Compatibilidade com os schemas do shared (`test_schema_compat.py`).
6. bandit, pip-audit e npm audit sem HIGH/CRITICAL não tratados (Step 1).
7. Containers não-root, sem `privileged`; `fias_ed_app` sem DDL (Step 2 + `test_db_privileges.py`).
8. Telas revisadas com Impeccable e aprovadas no §84 (Task 17).
9. Cabeçalhos de segurança no nginx (smoke).
10. Fontes científicas intactas (Step 3).

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/README.md
git commit --allow-empty -m "chore(web): verificação final da fatia W1

<registrar aqui o resultado de cada critério 1–10 do spec §14, com o comando/teste que o comprova>

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
