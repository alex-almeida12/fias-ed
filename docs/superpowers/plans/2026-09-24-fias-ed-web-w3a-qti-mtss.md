# FIAS-ED W3a — QTI por importação, triangulação, MTSS e relatórios

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levar uma aula de `FIAS_COMPLETED` a `REPORT_READY`, juntando a percepção dos estudantes (importada), a triangulação e o MTSS Tier 1, e entregar o relatório da aula e o do ciclo.

**Architecture:** O motor científico em `fias-ed-shared` já decide tudo — pontuação do QTI, agregação, triangulação e MTSS. Esta fatia é a camada de produto: um ciclo que sabe qual aula é a primeira e qual é a última, uma porta de importação que recusa arquivo adulterado, persistência do que o motor devolveu, e duas telas.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, React + TypeScript, Vitest, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-24-fias-ed-web-w3-qti-mtss-design.md`

## Global Constraints

- **`fias-ed-shared/` é somente leitura nesta fatia.** Nenhuma exceção. Se uma tarefa parecer exigir mudança lá, pare e relate.
- **Nunca alterar** `artigos selecionados\` nem `avalie-seu-professor\`.
- **"O motor decide, o Web persiste":** nenhuma regra científica reimplementada no backend do Web.
- **Vocabulário proibido em texto visível:** "avaliação", "avaliar", "nota", "desempenho", "ranking". A tela diz "acompanhar".
- **Privacidade:** nenhuma coluna de identidade nas tabelas de resposta. Logs nunca contêm texto de transcrição, nome de arquivo ou nome de pessoa.
- **Segurança:** nada de `shell=True` nem `os.system`. Segredos só em `.env`, que é gitignored.
- **WCAG 2.1 AA**, paleta fechada de 10 cores, sem `style` inline nem `dangerouslySetInnerHTML` (`src/lint.test.ts` pega).
- **Mudança em `fias-ed-shared` só chega ao container de teste após** `docker compose -f docker-compose.test.yml build api-test`. Nesta fatia não deve haver nenhuma, mas o rebuild é necessário se o Dockerfile mudar.
- **Estado marcado pelo passo que o alcança**, nunca por antecipação (lição do `TRANSCRIBING` em W2).
- **Base:** backend 404 testes, motor 243, interface 151. Toda tarefa termina com as suítes que tocou verdes.

## Review Focus

Cinco condições que a especificação implica e que nenhuma tarefa exercita por padrão. Cada uma tem o teste atribuído à tarefa que possui o código.

1. **O mesmo arquivo importado duas vezes** — o professor clica duas vezes, ou reimporta por engano. Esperado: a segunda importação substitui a coleta daquela data, não cria uma duplicada que faria a triangulação escolher arbitrariamente. *Teste na Task 5.*
2. **Ciclo declarado com uma aula só** — a primeira é também a última, e a regra "coleta posterior à penúltima" não tem penúltima. Esperado: uma coleta basta, e o encerramento funciona. *Teste na Task 2.*
3. **Arquivo importado sem nenhuma linha de resposta** — exportação de uma turma que não respondeu. Esperado: recusa clara, não uma coleta com zero respostas que depois divide por zero. *Teste na Task 5.*
4. **Aula que não pertence a ciclo nenhum** — o professor gravou antes de criar o ciclo. Esperado: segue de `FIAS_COMPLETED` a `REPORT_READY` sem QTI, sem travar e sem erro. *Teste na Task 9.*
5. **Duas coletas na mesma data** — importação e, no mesmo dia, outra. Esperado: "a mais recente anterior à aula" é determinística, não depende da ordem de inserção. *Teste na Task 7.*

---

### Task 1: Modelo do ciclo

**Files:**
- Modify: `fias-ed-web/backend/app/models.py`
- Create: `fias-ed-web/backend/alembic/versions/0004_ciclo.py`
- Test: `fias-ed-web/backend/tests/test_ciclo.py`

**Interfaces:**
- Produces: `class Ciclo` com `turma_id`, `disciplina_id`, `professor_id`, `n_aulas_previstas`, `iniciado_em`, `encerrado_em`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_ciclo.py
import datetime as dt
from app.models import Ciclo


def test_ciclo_nasce_aberto_e_com_o_numero_declarado(db, turma, disciplina, professor):
    c = Ciclo(turma_id=turma.id, disciplina_id=disciplina.id, professor_id=professor.id,
              n_aulas_previstas=8, iniciado_em=dt.date(2026, 3, 1))
    db.add(c); db.commit(); db.refresh(c)
    assert c.encerrado_em is None
    assert c.n_aulas_previstas == 8
    assert c.deleted_at is None
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_ciclo.py -q`
Expected: FAIL com `ImportError: cannot import name 'Ciclo'`

- [ ] **Step 2: Implementar o modelo**

Em `backend/app/models.py`, seguindo o padrão de `IndicadorFIAS` (`EntityMixin` dá `id`, `created_at`, `deleted_at`):

```python
class Ciclo(EntityMixin, Base):
    __tablename__ = "ciclo"
    turma_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("turma.id"), index=True, nullable=False)
    disciplina_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disciplina.id"), nullable=False)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    n_aulas_previstas: Mapped[int] = mapped_column(Integer, nullable=False)
    iniciado_em: Mapped[date] = mapped_column(Date, nullable=False)
    encerrado_em: Mapped[date | None] = mapped_column(Date, nullable=True)
```

- [ ] **Step 3: Gerar a migração**

```bash
docker compose run --rm api alembic revision --autogenerate -m "ciclo"
```

Renomeie o arquivo para `0004_ciclo.py` e confira que ele **só** cria `ciclo` — nenhuma tabela existente pode aparecer no diff.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_ciclo.py tests/test_schema_compat.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend/app/models.py fias-ed-web/backend/alembic/versions/0004_ciclo.py fias-ed-web/backend/tests/test_ciclo.py
git commit -m "feat(ciclo): o sistema precisa saber qual aula é a primeira e qual é a última

O QTI é obrigatório nas pontas do ciclo, e sem o número declarado de aulas não
há como saber onde ficam as pontas.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Criar, consultar e encerrar o ciclo

**Files:**
- Create: `fias-ed-web/backend/app/ciclos/__init__.py`, `fias-ed-web/backend/app/ciclos/routes.py`, `fias-ed-web/backend/app/ciclos/service.py`, `fias-ed-web/backend/app/ciclos/schemas.py`
- Modify: `fias-ed-web/backend/app/main.py` (registrar o router)
- Test: `fias-ed-web/backend/tests/test_ciclo.py`

**Interfaces:**
- Consumes: `Ciclo` (Task 1)
- Produces: `ciclo_da_aula(db, aula) -> Ciclo | None`, `posicao_no_ciclo(db, aula) -> Literal["primeira", "primeira_e_ultima", "meio", "ultima", "fora"]`

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_criar_ciclo_devolve_201_e_o_numero_declarado(client, turma, disciplina):
    r = client.post("/api/ciclos", json={"turma_id": str(turma.id), "disciplina_id": str(disciplina.id),
                                         "n_aulas_previstas": 8, "iniciado_em": "2026-03-01"})
    assert r.status_code == 201 and r.json()["n_aulas_previstas"] == 8


def test_a_primeira_aula_gravada_do_ciclo_e_a_primeira(db, client, ciclo, aula_em, posicao):
    a1 = aula_em(ciclo, "2026-03-02")
    a2 = aula_em(ciclo, "2026-03-09")
    assert posicao(a1) == "primeira"
    assert posicao(a2) == "meio"


def test_ciclo_de_uma_aula_so_tem_a_mesma_aula_como_primeira_e_ultima(db, client, turma, disciplina, aula_em, posicao):
    """Review Focus 2: n_aulas_previstas = 1 não pode quebrar a regra das pontas."""
    r = client.post("/api/ciclos", json={"turma_id": str(turma.id), "disciplina_id": str(disciplina.id),
                                         "n_aulas_previstas": 1, "iniciado_em": "2026-03-01"})
    ciclo_id = r.json()["id"]
    a = aula_em(ciclo_id, "2026-03-02")
    client.post(f"/api/ciclos/{ciclo_id}/encerrar")
    assert posicao(a) == "primeira_e_ultima"


def test_encerrar_define_a_ultima_pela_aula_realmente_gravada(db, client, ciclo, aula_em, posicao):
    """Review Focus: o professor declarou 8 e gravou 3."""
    aula_em(ciclo, "2026-03-02"); aula_em(ciclo, "2026-03-09")
    ultima = aula_em(ciclo, "2026-03-16")
    client.post(f"/api/ciclos/{ciclo.id}/encerrar")
    assert posicao(ultima) == "ultima"


def test_aula_fora_de_ciclo_devolve_fora(db, aula_avulsa, posicao):
    assert posicao(aula_avulsa) == "fora"
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_ciclo.py -q`
Expected: FAIL com 404 na rota

- [ ] **Step 2: Implementar o serviço**

```python
# backend/app/ciclos/service.py
"""O ciclo sabe onde cada aula está. Nenhuma regra científica aqui: posição é
fato de calendário, não de método."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Aula, Ciclo


def ciclo_da_aula(db: Session, aula: Aula) -> Ciclo | None:
    return db.execute(
        select(Ciclo).where(Ciclo.turma_id == aula.turma_id,
                            Ciclo.disciplina_id == aula.disciplina_id,
                            Ciclo.deleted_at.is_(None))
        .order_by(Ciclo.iniciado_em.desc())
    ).scalars().first()


def _aulas_do_ciclo(db: Session, ciclo: Ciclo) -> list[Aula]:
    return list(db.execute(
        select(Aula).where(Aula.turma_id == ciclo.turma_id,
                           Aula.disciplina_id == ciclo.disciplina_id,
                           Aula.lesson_date >= ciclo.iniciado_em,
                           Aula.deleted_at.is_(None))
        .order_by(Aula.lesson_date, Aula.created_at)
    ).scalars())


def posicao_no_ciclo(db: Session, aula: Aula) -> str:
    ciclo = ciclo_da_aula(db, aula)
    if ciclo is None:
        return "fora"
    aulas = _aulas_do_ciclo(db, ciclo)
    if not aulas:
        return "fora"
    primeira = aulas[0].id == aula.id
    # A última só existe depois do encerramento: antes disso, qualquer aula pode
    # ainda ser seguida por outra. Declarar "última" cedo travaria a aula em
    # WAITING_QTI por uma coleta que ainda não precisa existir.
    ultima = ciclo.encerrado_em is not None and aulas[-1].id == aula.id
    if primeira and ultima:
        return "primeira_e_ultima"
    if primeira:
        return "primeira"
    if ultima:
        return "ultima"
    return "meio"
```

- [ ] **Step 3: Implementar as rotas**

```python
# backend/app/ciclos/routes.py
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import Actor, current_professor
from app.ciclos.schemas import CicloIn, ciclo_out
from app.db import get_db
from app.models import Ciclo

router = APIRouter(prefix="/api/ciclos", tags=["ciclos"])


@router.post("", status_code=201)
def criar(body: CicloIn, actor: Actor = Depends(current_professor), db: Session = Depends(get_db)):
    c = Ciclo(turma_id=body.turma_id, disciplina_id=body.disciplina_id,
              professor_id=actor.professor_id, n_aulas_previstas=body.n_aulas_previstas,
              iniciado_em=body.iniciado_em)
    db.add(c); db.commit(); db.refresh(c)
    return ciclo_out(c)


@router.post("/{ciclo_id}/encerrar")
def encerrar(ciclo_id: uuid.UUID, actor: Actor = Depends(current_professor), db: Session = Depends(get_db)):
    c = db.get(Ciclo, ciclo_id)
    c.encerrado_em = dt.date.today()
    db.commit()
    return ciclo_out(c)
```

Registre o router em `main.py` ao lado dos demais.

- [ ] **Step 4: Rodar e confirmar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_ciclo.py -q`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend/app/ciclos fias-ed-web/backend/app/main.py fias-ed-web/backend/tests/test_ciclo.py
git commit -m "feat(ciclo): a última aula só existe depois do encerramento

Declarar 'última' antes de encerrar travaria a aula esperando uma coleta que
ainda não precisa existir — o professor pode gravar mais uma na semana seguinte.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Tela de criar o ciclo

**Files:**
- Create: `fias-ed-web/frontend/src/pages/NovoCiclo.tsx`, `fias-ed-web/frontend/src/pages/NovoCiclo.test.tsx`
- Modify: `fias-ed-web/frontend/src/App.tsx` (rota)

**Interfaces:**
- Consumes: `POST /api/ciclos` (Task 2)

- [ ] **Step 1: Escrever o teste que falha**

```tsx
test("o professor declara quantas aulas vai acompanhar", async () => {
  mockApi({ turmas: [{ id: "t1", name: "9º B" }], disciplinas: [{ id: "d1", name: "História" }] });
  renderApp("/ciclos/novo");
  await userEvent.selectOptions(await screen.findByLabelText(/turma/i), "t1");
  await userEvent.selectOptions(screen.getByLabelText(/disciplina/i), "d1");
  await userEvent.clear(screen.getByLabelText(/quantas aulas/i));
  await userEvent.type(screen.getByLabelText(/quantas aulas/i), "8");
  await userEvent.click(screen.getByRole("button", { name: /começar/i }));
  await waitFor(() => expect(enviado).toMatchObject({ n_aulas_previstas: 8 }));
});

test("a tela não usa vocabulário de avaliação", async () => {
  mockApi({ turmas: [], disciplinas: [] });
  renderApp("/ciclos/novo");
  await screen.findByLabelText(/quantas aulas/i);
  expect(document.body.textContent).not.toMatch(/avalia|nota|desempenho|ranking/i);
});
```

Run: `cd frontend && npx vitest run src/pages/NovoCiclo.test.tsx`
Expected: FAIL

- [ ] **Step 2: Implementar a tela**

Siga o padrão de `NovaAula.tsx`: `<form>` com `label` associado por `htmlFor`, botão primário único, `Banner` para erro. O rótulo do campo é **"Quantas aulas você quer acompanhar?"** — nunca "avaliar".

- [ ] **Step 3: Rodar e confirmar**

Run: `cd frontend && npx vitest run src/pages/NovoCiclo.test.tsx && npm run lint && npm run build`
Expected: PASS, lint limpo, build ok

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/frontend/src/pages/NovoCiclo.tsx fias-ed-web/frontend/src/pages/NovoCiclo.test.tsx fias-ed-web/frontend/src/App.tsx
git commit -m "feat(web): tela de começar um ciclo de acompanhamento

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Modelos da coleta, das respostas e do resultado

**Files:**
- Modify: `fias-ed-web/backend/app/models.py`
- Create: `fias-ed-web/backend/alembic/versions/0005_qti.py`
- Test: `fias-ed-web/backend/tests/test_qti_modelo.py`

**Interfaces:**
- Produces: `ColetaQTI`, `RespostaQTI`, `ResultadoQTI`

- [ ] **Step 1: Escrever o teste que falha — e ele trava a privacidade**

```python
from sqlalchemy import inspect
from app.models import ColetaQTI, RespostaQTI


def test_resposta_nao_tem_nenhuma_coluna_de_identidade(db):
    """A ausência é o mecanismo: sem coluna de identidade, não há como
    reconstruir quem respondeu o quê. Mesmo princípio do §48."""
    cols = {c.name for c in inspect(RespostaQTI).columns}
    proibidas = {"aluno_id", "estudante_id", "student_id", "nome", "email",
                 "matricula", "ip", "ip_address", "user_agent", "device_id", "session_id"}
    assert cols & proibidas == set(), f"coluna de identidade em RespostaQTI: {cols & proibidas}"
    assert "response_index" in cols


def test_coleta_declara_a_origem(db, ciclo):
    c = ColetaQTI(ciclo_id=ciclo.id, coletado_em=dt.date(2026, 3, 1),
                  origem="IMPORTACAO_EXTERNA", response_count=12, displayable=True,
                  qti_config_version="1.0.0")
    db.add(c); db.commit(); db.refresh(c)
    assert c.origem == "IMPORTACAO_EXTERNA"
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_qti_modelo.py -q`
Expected: FAIL com `ImportError`

- [ ] **Step 2: Implementar os modelos**

```python
ORIGEM_QTI = ("COLETA_NATIVA", "IMPORTACAO_EXTERNA")


class ColetaQTI(EntityMixin, Base):
    __tablename__ = "coleta_qti"
    ciclo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ciclo.id"), index=True, nullable=False)
    coletado_em: Mapped[date] = mapped_column(Date, nullable=False)
    origem: Mapped[str] = mapped_column(_enum(ORIGEM_QTI, "origem_qti"), nullable=False)
    response_count: Mapped[int] = mapped_column(Integer, nullable=False)
    displayable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    qti_config_version: Mapped[str] = mapped_column(String, nullable=False)


class RespostaQTI(EntityMixin, Base):
    """Sem identidade, por construção. O respondente é um índice sequencial
    dentro da coleta — é o que o formato de exportação do motor espera."""
    __tablename__ = "resposta_qti"
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), index=True, nullable=False)
    response_index: Mapped[int] = mapped_column(Integer, nullable=False)
    respostas: Mapped[dict] = mapped_column(JSON, nullable=False)  # {"1": 4, "2": 3, ... "24": 5}


class ResultadoQTI(EntityMixin, Base):
    __tablename__ = "resultado_qti"
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), index=True, nullable=False)
    octantes: Mapped[dict] = mapped_column(JSON, nullable=False)
    agency: Mapped[float] = mapped_column(Float, nullable=False)
    communion: Mapped[float] = mapped_column(Float, nullable=False)
```

- [ ] **Step 3: Gerar a migração `0005_qti.py`** e conferir que só cria as três tabelas.

- [ ] **Step 4: Rodar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_qti_modelo.py tests/test_schema_compat.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend/app/models.py fias-ed-web/backend/alembic/versions/0005_qti.py fias-ed-web/backend/tests/test_qti_modelo.py
git commit -m "feat(qti): resposta sem identidade, por construção

A ausência de coluna de identidade é o mecanismo de privacidade, não um
esquecimento — e há teste travando que ela continue ausente.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Importar o relatório do `avalie-seu-professor`

**Files:**
- Create: `fias-ed-web/backend/app/qti/__init__.py`, `fias-ed-web/backend/app/qti/routes.py`, `fias-ed-web/backend/app/qti/service.py`
- Modify: `fias-ed-web/backend/app/main.py`, `fias-ed-web/backend/app/core/messages.py`
- Test: `fias-ed-web/backend/tests/test_qti_import.py`

**Interfaces:**
- Consumes: `ColetaQTI`, `RespostaQTI`, `ResultadoQTI` (Task 4); `parse_export_csv`, `aggregate` do motor
- Produces: `importar_relatorio(db, ciclo, texto, coletado_em) -> ColetaQTI`

- [ ] **Step 1: Escrever os testes que falham**

```python
CABECALHO = "response_id," + ",".join(f"q{i}" for i in range(1, 25))


def _csv(n_linhas, valor=4):
    linhas = [CABECALHO]
    for i in range(n_linhas):
        linhas.append(f"r{i}," + ",".join([str(valor)] * 24))
    return "\n".join(linhas) + "\n"


def test_importa_e_persiste_as_respostas_item_a_item(db, client, ciclo):
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 201
    coleta = db.query(ColetaQTI).one()
    assert coleta.response_count == 12 and coleta.displayable is True
    assert coleta.origem == "IMPORTACAO_EXTERNA"
    assert db.query(RespostaQTI).filter_by(coleta_id=coleta.id).count() == 12


def test_arquivo_sem_nenhuma_resposta_e_recusado(db, client, ciclo):
    """Review Focus 3: exportação de turma que não respondeu."""
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", CABECALHO + "\n", "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 422
    assert "nenhuma resposta" in r.json()["message"].lower()
    assert db.query(ColetaQTI).count() == 0


def test_valor_adulterado_recusa_o_arquivo_inteiro(db, client, ciclo):
    linhas = _csv(12).splitlines()
    linhas[3] = linhas[3].replace(",4,", ",9,", 1)   # fora da escala 1..5
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", "\n".join(linhas), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 422 and "linha 4" in r.json()["message"].lower()
    assert db.query(ColetaQTI).count() == 0


def test_reimportar_na_mesma_data_substitui_em_vez_de_duplicar(db, client, ciclo):
    """Review Focus 1: o professor clica duas vezes."""
    for _ in range(2):
        client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    vivas = db.query(ColetaQTI).filter(ColetaQTI.deleted_at.is_(None)).all()
    assert len(vivas) == 1
    assert db.query(RespostaQTI).filter_by(coleta_id=vivas[0].id).count() == 12


def test_menos_de_dez_respostas_nao_e_erro_mas_nao_e_exibivel(db, client, ciclo):
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(4), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 201
    assert db.query(ColetaQTI).one().displayable is False


def test_arquivo_sem_versao_declarada_e_recusado(db, client, ciclo):
    """Spec §9: sem a versão declarada, uma mudança no avalie-seu-professor
    quebraria a importação em silêncio — o arquivo entraria e os números sairiam
    errados. Recusar alto é o ponto."""
    sem_versao = _csv(12).replace(CABECALHO_COM_VERSAO, CABECALHO)
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", sem_versao, "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 422 and "versão" in r.json()["message"].lower()
    assert db.query(ColetaQTI).count() == 0


def test_versao_desconhecida_e_recusada_nomeando_a_que_veio(db, client, ciclo):
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12, versao="9.9.9"), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 422 and "9.9.9" in r.json()["message"]
```

**Sobre a versão declarada.** O `parse_export_csv` do motor **não** conhece versão — ele valida colunas e recalcula. A declaração de versão é responsabilidade do Web, antes de chamar o motor: leia a primeira linha do arquivo procurando um cabeçalho de versão (`# qti_export_version: X.Y.Z`) ou uma coluna dedicada, conforme o `avalie-seu-professor` exportar hoje — **confira no código dele antes de decidir o formato**, em `src/application/use-cases/exportTeacherDataset.ts`, que é somente leitura. Se ele não declarar versão nenhuma hoje, **pare e relate**: a exigência precisa nascer lá, e isso é decisão do pesquisador, não sua.

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_qti_import.py -q`
Expected: FAIL com 404

- [ ] **Step 2: Implementar o serviço**

```python
# backend/app/qti/service.py
"""Importa o relatório exportado pelo avalie-seu-professor.

Nenhuma regra científica aqui: parse_export_csv valida e recalcula, aggregate
pontua. Este módulo só persiste o que o motor devolveu.
"""
import datetime as dt

from fias_ed_engine.qti import QtiImportError, aggregate, parse_export_csv
from fias_ed_engine.rules import load_rules
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Ciclo, ColetaQTI, RespostaQTI, ResultadoQTI


def importar_relatorio(db: Session, ciclo: Ciclo, texto: str, coletado_em: dt.date) -> ColetaQTI:
    cfg = load_rules("qti_config")
    try:
        respostas = parse_export_csv(texto, cfg)
    except QtiImportError as exc:
        raise AppError("QTI_IMPORT_INVALIDO", str(exc)) from exc
    if not respostas:
        raise AppError("QTI_SEM_RESPOSTAS",
                       "O arquivo não traz nenhuma resposta. Confira se a turma respondeu antes de exportar.")

    # Reimportar na mesma data substitui: duas coletas na mesma data deixariam a
    # triangulação escolher arbitrariamente qual é "a mais recente".
    anterior = db.execute(select(ColetaQTI).where(
        ColetaQTI.ciclo_id == ciclo.id, ColetaQTI.coletado_em == coletado_em,
        ColetaQTI.deleted_at.is_(None))).scalars().first()
    if anterior is not None:
        _descartar(db, anterior)

    agregado = aggregate(respostas, cfg)
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=coletado_em, origem="IMPORTACAO_EXTERNA",
                       response_count=agregado["response_count"], displayable=agregado["displayable"],
                       qti_config_version=cfg["rules_version"])
    db.add(coleta); db.flush()
    for i, r in enumerate(respostas):
        db.add(RespostaQTI(coleta_id=coleta.id, response_index=i,
                           respostas={str(k): v for k, v in r.items()}))
    db.add(ResultadoQTI(coleta_id=coleta.id, octantes=agregado["octants"],
                        agency=agregado["agency"], communion=agregado["communion"]))
    db.commit()
    return coleta
```

- [ ] **Step 3: Implementar a rota** (`POST /api/ciclos/{ciclo_id}/qti/importar`, multipart com `arquivo` e `coletado_em`), mapeando `AppError` para 422 com a mensagem humana, como `messages.py` já faz para os outros códigos.

- [ ] **Step 4: Rodar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_qti_import.py -q`
Expected: PASS (5 testes)

- [ ] **Step 5: Desfazer e conferir que os testes mordem**

Remova o bloco `if anterior is not None` e confirme que `test_reimportar_na_mesma_data_substitui_em_vez_de_duplicar` falha com `assert 2 == 1`. Restaure.

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/backend/app/qti fias-ed-web/backend/app/main.py fias-ed-web/backend/app/core/messages.py fias-ed-web/backend/tests/test_qti_import.py
git commit -m "feat(qti): importar o relatório, recusando o arquivo inteiro se um valor divergir

Reimportar na mesma data substitui: duas coletas na mesma data deixariam a
triangulação escolher arbitrariamente qual é a mais recente.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Tela de importar o relatório

**Files:**
- Create: `fias-ed-web/frontend/src/pages/ImportarQTI.tsx`, `fias-ed-web/frontend/src/pages/ImportarQTI.test.tsx`
- Modify: `fias-ed-web/frontend/src/App.tsx`

- [ ] **Step 1: Escrever os testes que falham**

```tsx
test("importar um relatório válido mostra quantas respostas entraram", async () => {
  mockApi({ importar: { response_count: 12, displayable: true } });
  renderApp("/ciclos/c1/qti");
  await userEvent.upload(await screen.findByLabelText(/relatório/i), arquivoCsv());
  await userEvent.click(screen.getByRole("button", { name: /enviar/i }));
  expect(await screen.findByText(/12 respostas/i)).toBeInTheDocument();
});

test("arquivo recusado mostra a mensagem humana e mantém a saída", async () => {
  mockApi({ importarErro: { message: "Linha 4: item 3 fora da escala 1–5." } });
  renderApp("/ciclos/c1/qti");
  await userEvent.upload(await screen.findByLabelText(/relatório/i), arquivoCsv());
  await userEvent.click(screen.getByRole("button", { name: /enviar/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/linha 4/i);
  expect(screen.getByLabelText(/relatório/i)).toBeInTheDocument();
});

test("menos de dez respostas avisa sem tratar como erro", async () => {
  mockApi({ importar: { response_count: 4, displayable: false } });
  renderApp("/ciclos/c1/qti");
  await userEvent.upload(await screen.findByLabelText(/relatório/i), arquivoCsv());
  await userEvent.click(screen.getByRole("button", { name: /enviar/i }));
  expect(await screen.findByText(/pelo menos 10/i)).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Implementar a tela.** Padrão de `NovaAula.tsx` para o campo de arquivo. Erro em `Banner kind="error"` (que é `role="alert"`), aviso de poucas respostas em `Banner kind="info"` — **não** é erro.

- [ ] **Step 3: Rodar**

Run: `cd frontend && npx vitest run src/pages/ImportarQTI.test.tsx && npm run lint && npm run build`

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/frontend/src/pages/ImportarQTI.tsx fias-ed-web/frontend/src/pages/ImportarQTI.test.tsx fias-ed-web/frontend/src/App.tsx
git commit -m "feat(web): tela de importar a percepção dos estudantes

Poucas respostas não é erro: o resultado não é exibível, mas a coleta existe.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Triangulação

**Files:**
- Create: `fias-ed-web/backend/app/triangulacao/__init__.py`, `fias-ed-web/backend/app/triangulacao/service.py`
- Modify: `fias-ed-web/backend/app/models.py`, `fias-ed-web/backend/alembic/versions/0006_triangulacao.py`
- Test: `fias-ed-web/backend/tests/test_triangulacao.py`

**Interfaces:**
- Consumes: `ColetaQTI`/`ResultadoQTI` (Task 4), `IndicadorFIAS` (W2)
- Produces: `coleta_vigente(db, aula) -> ColetaQTI | None`, `triangular(db, aula) -> list[dict]`

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_usa_a_coleta_mais_recente_anterior_a_aula(db, ciclo, aula_em, coleta_em):
    coleta_em(ciclo, "2026-03-01")
    marco = coleta_em(ciclo, "2026-04-01")
    coleta_em(ciclo, "2026-06-01")          # posterior à aula: não pode ser escolhida
    aula = aula_em(ciclo, "2026-05-10")
    assert coleta_vigente(db, aula).id == marco.id


def test_duas_coletas_na_mesma_data_escolhem_sempre_a_criada_por_ultimo(db, ciclo, aula_em, coleta_em):
    """Review Focus 5: determinismo. A importação na mesma data substitui (Task 5),
    então duas coletas vivas na mesma data só aparecem por caminho excepcional —
    mas quando aparecem, a escolha não pode depender da ordem de varredura do banco."""
    coleta_em(ciclo, "2026-03-01")
    ultima = coleta_em(ciclo, "2026-03-01")
    aula = aula_em(ciclo, "2026-04-01")
    for _ in range(5):
        assert coleta_vigente(db, aula).id == ultima.id


def test_sem_coleta_a_triangulacao_traz_a_pergunta_sem_os_valores(db, aula_classificada):
    pares = triangular(db, aula_classificada)
    assert len(pares) == 4
    assert all(p["qti_available"] is False for p in pares)
    assert all(p["reflection_question"] for p in pares)
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_triangulacao.py -q`
Expected: FAIL

- [ ] **Step 2: Implementar**

```python
# backend/app/triangulacao/service.py
"""Justaposição FIAS × QTI. O motor decide; este módulo escolhe qual coleta
vale e persiste o que ele devolveu."""
from fias_ed_engine.rules import load_rules
from fias_ed_engine.triangulation import triangulate
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ciclos.service import ciclo_da_aula
from app.models import Aula, ColetaQTI, ResultadoQTI


def coleta_vigente(db: Session, aula: Aula) -> ColetaQTI | None:
    """A mais recente ANTERIOR à aula. Triangular uma aula de março contra uma
    percepção de junho seria compará-la com uma opinião que ainda não existia.
    Desempate por created_at e depois por id: duas coletas na mesma data
    precisam produzir sempre a mesma escolha."""
    ciclo = ciclo_da_aula(db, aula)
    if ciclo is None:
        return None
    return db.execute(
        select(ColetaQTI).where(ColetaQTI.ciclo_id == ciclo.id,
                                ColetaQTI.coletado_em <= aula.lesson_date,
                                ColetaQTI.deleted_at.is_(None))
        .order_by(ColetaQTI.coletado_em.desc(), ColetaQTI.created_at.desc(), ColetaQTI.id.desc())
    ).scalars().first()
```

O resultado do QTI vai a `triangulate` no formato que ele espera
(`{"octants": …, "displayable": …}`); quando não há coleta, passa
`{"displayable": False, "octants": {}}`, que é o caminho que o motor já trata.

- [ ] **Step 3: Persistir o resultado** numa tabela `triangulacao` (aula_id, pair_id, fias_kind, fias_ref, fias_value, qti_available, qti_values, reflection_question, source_reference, validation_status), migração `0006`.

- [ ] **Step 4: Rodar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_triangulacao.py -q`
Expected: PASS

- [ ] **Step 5: Desfazer e conferir**

Troque `<= aula.lesson_date` por `>=` e confirme que `test_usa_a_coleta_mais_recente_anterior_a_aula` falha apontando a coleta de junho. Restaure.

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/backend/app/triangulacao fias-ed-web/backend/app/models.py fias-ed-web/backend/alembic/versions/0006_triangulacao.py fias-ed-web/backend/tests/test_triangulacao.py
git commit -m "feat(triangulação): cada aula usa a coleta mais recente anterior a ela

Triangular uma aula de março contra uma percepção medida em junho seria
compará-la com uma opinião que ainda não existia.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: MTSS Tier 1

**Files:**
- Create: `fias-ed-web/backend/app/mtss/__init__.py`, `fias-ed-web/backend/app/mtss/service.py`
- Modify: `fias-ed-web/backend/app/models.py`, `fias-ed-web/backend/alembic/versions/0007_mtss.py`
- Test: `fias-ed-web/backend/tests/test_mtss.py`

**Interfaces:**
- Consumes: `IndicadorFIAS` e `ClassificacaoFIAS` (W2)
- Produces: `interpretar(db, aula) -> tuple[list[dict], list[dict]]` (regras disparadas, recomendações)

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_regras_disparadas_viram_recomendacoes_sem_duplicar(db, aula_expositiva):
    disparadas, recs = interpretar(db, aula_expositiva)
    assert disparadas, "nenhuma regra disparou numa aula fortemente expositiva"
    ids = [r["recommendation_id"] for r in recs]
    assert len(ids) == len(set(ids))


def test_nenhuma_recomendacao_afirma_erro_do_professor(db, aula_expositiva):
    _, recs = interpretar(db, aula_expositiva)
    textos = " ".join(r["text"] for r in recs).lower()
    assert not re.search(r"\berrou\b|\bincorret|\bdeveria ter\b|\bfalhou\b", textos)


def test_as_regras_vem_enquadradas_como_reflexao(db, aula_expositiva):
    disparadas, _ = interpretar(db, aula_expositiva)
    assert all(d["framing"] == "reflection" for d in disparadas)
```

- [ ] **Step 2: Implementar**

```python
# backend/app/mtss/service.py
from fias_ed_engine.mtss import build_facts, evaluate, recommendations
from fias_ed_engine.rules import load_rules


def interpretar(db, aula):
    intervals = _intervalos_da_aula(db, aula)          # os mesmos que a faixa usa
    indices = _indices_da_aula(db, aula)               # de IndicadorFIAS
    fatos = build_facts(intervals, indices)
    disparadas = evaluate(fatos, load_rules("mtss_rules"))
    recs = recommendations(disparadas, load_rules("pedagogical_rules"))
    return disparadas, recs
```

Persista em `interpretacao_mtss` (aula_id, rule_id, tier1_dimension, framing, interpretation, evidence, source_reference, validation_status, rules_version) e `recomendacao_mtss` (aula_id, recommendation_id, rule_id, text, validation_status, source_reference), migração `0007`.

- [ ] **Step 3: Rodar e confirmar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_mtss.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/backend/app/mtss fias-ed-web/backend/app/models.py fias-ed-web/backend/alembic/versions/0007_mtss.py fias-ed-web/backend/tests/test_mtss.py
git commit -m "feat(mtss): Tier 1 enquadrado como reflexão, nunca como correção

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Encadear os estados até `REPORT_READY`

**Files:**
- Modify: `fias-ed-web/backend/app/jobs/handlers.py`, `fias-ed-web/backend/app/fias/service.py`
- Test: `fias-ed-web/backend/tests/test_estados_w3.py`

**Interfaces:**
- Consumes: `posicao_no_ciclo` (Task 2), `triangular` (Task 7), `interpretar` (Task 8)

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_primeira_aula_sem_coleta_para_em_waiting_qti(db, ciclo, aula_classificada_em):
    a = aula_classificada_em(ciclo, "2026-03-02")
    avancar(db, a)
    assert _status(db, a) == "WAITING_QTI"


def test_aula_do_meio_vai_direto_a_report_ready(db, ciclo, aula_classificada_em):
    aula_classificada_em(ciclo, "2026-03-02")
    meio = aula_classificada_em(ciclo, "2026-03-09")
    avancar(db, meio)
    assert _status(db, meio) == "REPORT_READY"


def test_aula_fora_de_ciclo_vai_direto_a_report_ready(db, aula_avulsa_classificada):
    """Review Focus 4: o professor gravou antes de criar o ciclo."""
    avancar(db, aula_avulsa_classificada)
    assert _status(db, aula_avulsa_classificada) == "REPORT_READY"


def test_cada_estado_e_marcado_pelo_passo_que_o_alcanca(db, ciclo, aula_classificada_em, espiao):
    """Lição do TRANSCRIBING em W2: nenhum estado marcado por antecipação."""
    meio = aula_classificada_em(ciclo, "2026-03-09")
    vistos = espiao(meio, avancar)
    assert vistos == ["TRIANGULATED", "MTSS_INTERPRETED", "REPORT_READY"]
```

- [ ] **Step 2: Implementar o avanço**, marcando cada estado no passo que o alcança, tudo na mesma transação que o dado que ele descreve.

- [ ] **Step 3: Rodar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_estados_w3.py -q`
Expected: PASS (4 testes)

- [ ] **Step 4: Desfazer e conferir**

Marque `TRIANGULATED` antes de chamar `triangular` e confirme que o teste-espião falha. Restaure.

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend/app/jobs/handlers.py fias-ed-web/backend/app/fias/service.py fias-ed-web/backend/tests/test_estados_w3.py
git commit -m "feat(w3): a aula do meio não espera o questionário

Só a primeira e a última do ciclo param em WAITING_QTI. Aula fora de ciclo
segue direto — o professor pode ter gravado antes de declarar o ciclo.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: API do relatório da aula

**Files:**
- Create: `fias-ed-web/backend/app/relatorios/__init__.py`, `fias-ed-web/backend/app/relatorios/routes.py`
- Test: `fias-ed-web/backend/tests/test_relatorio_aula.py`

- [ ] **Step 1: Teste que falha**

```python
def test_relatorio_traz_observacao_triangulacao_e_reflexoes(client, aula_report_ready):
    r = client.get(f"/api/aulas/{aula_report_ready.id}/relatorio")
    assert r.status_code == 200
    b = r.json()
    assert b["indices"] and len(b["triangulacao"]) == 4 and "recomendacoes" in b


def test_relatorio_recusa_aula_que_ainda_nao_chegou(client, aula_classificada):
    assert client.get(f"/api/aulas/{aula_classificada.id}/relatorio").status_code == 409
```

- [ ] **Step 2: Implementar a rota** — só lê, nunca recalcula, no mesmo padrão de `fias/routes.py`.
- [ ] **Step 3: Rodar.** Expected: PASS
- [ ] **Step 4: Commit**

---

### Task 11: Tela do relatório da aula

**Files:**
- Create: `fias-ed-web/frontend/src/pages/RelatorioAula.tsx` e seu teste
- Modify: `fias-ed-web/frontend/src/App.tsx`, `fias-ed-web/frontend/src/pages/AulaPage.tsx` (link quando `REPORT_READY`)

- [ ] **Step 1: Testes que falham**

```tsx
test("o relatório mostra a pergunta de reflexão mesmo sem a percepção coletada", async () => {
  mockApi({ relatorio: { triangulacao: pares({ qti_available: false }) } });
  renderApp("/aulas/a1/relatorio");
  expect(await screen.findByText(/percepção dos estudantes não foi coletada/i)).toBeInTheDocument();
  expect(screen.getAllByText(/observe/i).length).toBeGreaterThan(0);
});

test("nenhum texto do relatório usa vocabulário de avaliação", async () => {
  mockApi({ relatorio: relatorioCompleto() });
  renderApp("/aulas/a1/relatorio");
  await screen.findByRole("heading", { name: /relatório/i });
  expect(document.body.textContent).not.toMatch(/avalia|nota do professor|desempenho|ranking/i);
});
```

- [ ] **Step 2: Implementar.** Seguir `PadroesInteracao.tsx`.
- [ ] **Step 3: Rodar** `npx vitest run`, `npm run lint`, `npm run build`
- [ ] **Step 4: Commit**

---

### Task 12: API do relatório do ciclo

**Files:**
- Modify: `fias-ed-web/backend/app/relatorios/routes.py`
- Test: `fias-ed-web/backend/tests/test_relatorio_ciclo.py`

- [ ] **Step 1: Testes que falham**

```python
def test_trajetoria_traz_os_indices_de_todas_as_aulas_na_ordem(client, ciclo_com_tres_aulas):
    b = client.get(f"/api/ciclos/{ciclo_com_tres_aulas.id}/relatorio").json()
    datas = [p["lesson_date"] for p in b["trajetoria"]]
    assert datas == sorted(datas)


def test_relatorio_do_ciclo_declara_previstas_e_realizadas(client, ciclo_com_tres_aulas):
    b = client.get(f"/api/ciclos/{ciclo_com_tres_aulas.id}/relatorio").json()
    assert b["n_aulas_previstas"] == 8 and b["n_aulas_realizadas"] == 3


def test_o_relatorio_nao_contem_nenhum_veredito(client, ciclo_com_tres_aulas):
    """§2.7: o sistema não calcula melhora."""
    bruto = client.get(f"/api/ciclos/{ciclo_com_tres_aulas.id}/relatorio").text.lower()
    assert not re.search(r"melhor|pior|evolu|progress|regred", bruto)
```

- [ ] **Step 2: Implementar.** Devolve a trajetória (uma entrada por aula, com data e índices) e as coletas de QTI na ordem. **Nenhum campo derivado que compare começo e fim.**
- [ ] **Step 3: Rodar.** Expected: PASS
- [ ] **Step 4: Commit**

---

### Task 13: Tela do relatório do ciclo

**Files:**
- Create: `fias-ed-web/frontend/src/pages/RelatorioCiclo.tsx` e seu teste

- [ ] **Step 1: Testes que falham** — a trajetória aparece na ordem; as duas coletas aparecem; nenhum texto afirma melhora.
- [ ] **Step 2: Implementar.** O gráfico de trajetória segue as regras do `DESIGN.md`: paleta fechada, contraste ≥ 3:1 entre elementos adjacentes, alternativa textual com os valores exatos — as lições da faixa de tempo da W2 valem aqui.
- [ ] **Step 3: Rodar**
- [ ] **Step 4: Commit**

---

### Task 14: Ligar a exportação

**Files:**
- Modify: `fias-ed-web/backend/app/relatorios/routes.py` ou o módulo que monta o dataset
- Test: `fias-ed-web/backend/tests/test_export_w3.py`

- [ ] **Step 1: Teste que falha**

```python
def test_dataset_traz_as_nove_tabelas_preenchidas(db, ciclo_completo):
    ds = montar_dataset(db, [ciclo_completo])
    for t in ("lessons", "segments", "intervals", "matrix", "indices",
              "qti_responses", "qti_results", "mtss", "recommendations", "triangulation"):
        assert ds[t], f"tabela vazia: {t}"


def test_a_origem_do_qti_viaja_ate_o_dataset(db, ciclo_completo):
    ds = montar_dataset(db, [ciclo_completo])
    assert {r["origem"] for r in ds["qti_results"]} == {"IMPORTACAO_EXTERNA"}
```

- [ ] **Step 2: Implementar** o adaptador que alimenta `build_dataset` com `qti_responses` e o resto. `build_dataset` já espera `item["qti_responses"]`.
- [ ] **Step 3: Rodar.** Expected: PASS
- [ ] **Step 4: Commit**

---

### Task 15: Revisão visual

**Files:**
- Modify: só o que a revisão apontar

- [ ] **Step 1:** `impeccable detect` **está quebrado nesta máquina** — devolve vazio para tudo. Se for usar medidor, valide-o primeiro contra uma entrada sabidamente ruim; um "zero achados" não conferido não vale.
- [ ] **Step 2:** Capturar as quatro telas novas em 360 px e 1280 px, medindo contraste nos **estilos computados**, com Playwright e Chrome real (`chromium.launch({channel:'chrome'})`).
- [ ] **Step 3:** Corrigir dentro das regras: só tokens do shared, sem gradiente, raio só `--radius-sm`/`--radius-md`, Rokkitt só em título ≥ 24 px.
- [ ] **Step 4:** `npm test -- --run && npm run lint && npm run build`
- [ ] **Step 5:** Commit com a tabela do §84 no corpo.

---

### Task 16: Verificação final da W3a

- [ ] **Step 1:** Suítes e auditorias: backend, motor, interface, `bandit -r app --severity-level high`, `pip-audit --skip-editable`, `npm audit --audit-level=high`.
- [ ] **Step 2:** Subir o sistema e percorrer pela interface: criar ciclo → gravar aula → importar relatório → relatório da aula → encerrar ciclo → relatório do ciclo. **Sem tocar no banco.**
- [ ] **Step 3:** Conferir os 13 critérios de aceite do §13 da spec, um a um, registrando o comando que comprova cada um.
- [ ] **Step 4:** **Se um teste falhar de forma intermitente, não repita até passar.** Rode o arquivo cinco vezes e conte. Um teste que falha em 1 de 5 é defeito de teste e se conserta aqui.
- [ ] **Step 5:** Commit com o resultado de cada critério no corpo.
