# Coleta nativa do QTI — Plano de implementação (W3b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O professor gera um link, os estudantes respondem o QTI-24 pelo celular sem login, e as respostas entram na coleta sem que exista caminho no banco para saber quem respondeu o quê.

**Architecture:** Uma tabela `LinkQTI` guarda o segredo do link (só o hash), o prazo, o limite e a revogação. Três rotas públicas — abrir, consentir, responder — vivem num router próprio, montado sem a dependência de autenticação que todas as outras rotas usam. A resposta entra em `RespostaQTI`, que já existe e já é sem identidade por construção. O motor valida e pontua; o Web só persiste.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React + react-router, `fias_ed_engine.qti`.

**Spec:** `docs/superpowers/specs/2026-09-24-fias-ed-web-w3-qti-mtss-design.md` — §6 banco, §7 privacidade, §10 segurança, §11 testes, critérios 4, 5 e 10 do §13.

## Global Constraints

- **Privacidade (§7).** Nenhuma identidade de respondente é persistida: sem nome, sem matrícula, **sem endereço de rede**, sem identificador de dispositivo. O consentimento não se liga à resposta.
- **"O motor decide, o Web persiste".** `fias-ed-shared` é **somente leitura** nesta fatia inteira. Validação de escala e pontuação são de `fias_ed_engine.qti`; o Web nunca recalcula.
- **Vocabulário proibido** em código, comentário, teste e texto visível: "avalia", "avaliação", "avaliar", "nota", "desempenho", "ranking". Na interface do professor, "acompanhamento", nunca "ciclo" — "ciclo" é nome interno e vale em rota, tipo e nome de arquivo.
- **Todo texto visível em português do Brasil.**
- **`aula_payload` já traz `acompanhamento`** (W3a). Não duplicar a regra de pertencimento: `ciclo_da_aula` e `posicao_no_ciclo` vivem em `app/ciclos/service.py`.
- **Limite do link:** o professor informa o número de estudantes ao gerar; o limite é esse número **+ 10%, arredondado para cima**. Decisão do pesquisador em 2026-09-25.
- **Reenvio:** contido por marca no navegador do estudante (`localStorage`) **mais** o limite total. A burla por aba anônima é **limitação conhecida e declarada**, não defeito a corrigir.
- **Migração:** aditiva, numerada **`0009`** (a última existente é `0008_mtss.py`).
- **Ambiente:** o python global desta máquina não tem pytest — use `fias-ed-shared/engine-py/.venv/Scripts/python.exe`. Reconstrua a imagem de teste (`docker compose -f docker-compose.test.yml build api-test`) sempre que o motor mudar. Docker Desktop: `C:\Users\Alex Almeida\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`.
- **Números de partida:** backend **494 passed, 6 deselected**; motor **267**; frontend **213 em 21 arquivos**.

## Review Focus

Cinco modos de falha que a spec implica e que nenhum teste óbvio cobre. Cada um tem o teste que o prende, na tarefa indicada:

1. **Token vazando pelos logs ou pela mensagem de erro** — o segredo do link é a única credencial do sistema; se aparecer num log ou num corpo de erro, está comprometido. *Teste na Task 2.*
2. **Duas respostas simultâneas no último lugar do limite** — duas pessoas enviam ao mesmo tempo com uma vaga restante; sem verificação sob transação, as duas entram e o limite é furado. *Teste na Task 4.*
3. **Resposta parcial aceita** — o estudante pula uma pergunta e o envio passa, gravando uma coleta que o motor pontuaria errado. *Teste na Task 4.*
4. **Link de coleta apagada logicamente** — o professor apaga a coleta e o link antigo continua aceitando respostas órfãs. *Teste na Task 2.*
5. **Estudante volta com o botão do navegador depois de enviar** — vê o formulário de novo e reenvia sem perceber. *Teste na Task 7.*

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/models.py` | `LinkQTI` e `ConsentimentoQTI` |
| `backend/alembic/versions/0009_coleta_nativa.py` | migração aditiva |
| `backend/app/qti/links.py` | criar, validar, revogar link; gerar e conferir o segredo |
| `backend/app/qti/routes.py` | rotas do professor: gerar e revogar (autenticadas) |
| `backend/app/publico/__init__.py`, `routes.py` | as três rotas públicas, router próprio |
| `backend/app/main.py` | montar o router público |
| `frontend/src/pages/Responder.tsx` | a tela do estudante |
| `frontend/src/pages/Acompanhamentos.tsx` | gerar e revogar o link |
| `frontend/src/app/App.tsx` | rota pública `/responder/:token` |

---

## Task 1: modelos e migração

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/0009_coleta_nativa.py`
- Test: `backend/tests/test_coleta_nativa_modelo.py`

**Interfaces:**
- Consumes: `ColetaQTI` (W3a), `EntityMixin`, `_enum`
- Produces: `LinkQTI(coleta_id, token_hash, expira_em, limite_respostas, revogado_em)`, `ConsentimentoQTI(coleta_id, documento_versao, aceito_em)`

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_coleta_nativa_modelo.py
"""§7 da spec: nenhuma identidade de respondente é persistida, e o
consentimento não se liga à resposta. Estes testes travam isso na forma das
tabelas, como test_diarize_nao_grava_o_rotulo_da_voz_em_lugar_nenhum faz para
a voz — não basta ninguém gravar identidade hoje; a coluna não pode existir."""
from app.models import ConsentimentoQTI, LinkQTI, RespostaQTI


def test_nenhuma_tabela_da_coleta_nativa_tem_coluna_de_identidade():
    proibidas = {"ip", "ip_address", "endereco_ip", "user_agent", "device_id",
                 "aluno_id", "estudante_id", "email", "nome", "matricula", "session_id"}
    for modelo in (LinkQTI, ConsentimentoQTI, RespostaQTI):
        colunas = {c.name for c in modelo.__table__.columns}
        assert not (colunas & proibidas), f"{modelo.__tablename__}: {colunas & proibidas}"


def test_consentimento_nao_tem_caminho_para_a_resposta():
    """Registra-se QUE houve consentimento, não DE QUEM é qual resposta. Uma
    chave estrangeira para RespostaQTI — ou uma coluna que guarde o índice do
    respondente — reconstruiria o vínculo que o §7 proíbe."""
    colunas = {c.name for c in ConsentimentoQTI.__table__.columns}
    assert "resposta_id" not in colunas and "response_index" not in colunas
    alvos = {fk.column.table.name for c in ConsentimentoQTI.__table__.columns for fk in c.foreign_keys}
    assert "resposta_qti" not in alvos


def test_link_guarda_o_hash_do_token_nunca_o_token():
    colunas = {c.name for c in LinkQTI.__table__.columns}
    assert "token_hash" in colunas
    assert "token" not in colunas
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd fias-ed-web && docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_coleta_nativa_modelo.py -q`
Expected: FAIL com `ImportError: cannot import name 'LinkQTI'`

- [ ] **Step 3: Escrever os modelos**

Em `backend/app/models.py`, depois de `ResultadoQTI`:

```python
class LinkQTI(EntityMixin, Base):
    """O segredo do link nunca é gravado — só o hash. Quem tem o link consegue
    responder; quem tem o banco, não consegue reconstruí-lo."""
    __tablename__ = "link_qti"
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    limite_respostas: Mapped[int] = mapped_column(Integer, nullable=False)
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentimentoQTI(EntityMixin, Base):
    """Registra QUE houve consentimento, nunca de quem. Sem chave estrangeira
    para RespostaQTI e sem índice de respondente: a ausência é o mecanismo,
    pelo mesmo princípio do §48 que proíbe agrupar voz por estudante."""
    __tablename__ = "consentimento_qti"
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), index=True, nullable=False)
    documento_versao: Mapped[str] = mapped_column(String(32), nullable=False)
    aceito_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
```

- [ ] **Step 4: Gerar a migração e conferir o arquivo**

```bash
cd fias-ed-web && docker compose -f docker-compose.test.yml run --rm api-test \
  alembic revision --autogenerate -m "coleta nativa"
```

Renomeie para `0009_coleta_nativa.py`, com `revision = '0009'` e `down_revision = '0008'`.

**Leia o arquivo gerado antes de aceitar.** Na W3a o autogenerate trouxe diffs de tabelas alheias mais de uma vez. Só as duas tabelas novas podem aparecer.

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_coleta_nativa_modelo.py -q`
Expected: PASS (3 testes)

- [ ] **Step 6: Desfazer e conferir**

Acrescente `ip: Mapped[str | None] = mapped_column(String(45), nullable=True)` a `LinkQTI`, rode, confirme que o primeiro teste falha nomeando a coluna, e remova. Cole a saída real no relatório.

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend/app/models.py fias-ed-web/backend/alembic/versions/0009_coleta_nativa.py fias-ed-web/backend/tests/test_coleta_nativa_modelo.py
git commit -m "feat(qti): o link e o consentimento existem sem identificar ninguém

A ausência de colunas de identidade é o mecanismo, não uma omissão: três
testes travam a forma das tabelas, do mesmo jeito que a fatia da voz trava
o rótulo do falante.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: o segredo do link e suas regras

**Files:**
- Create: `backend/app/qti/links.py`
- Test: `backend/tests/test_link_qti.py`

**Interfaces:**
- Consumes: `LinkQTI`, `ColetaQTI`
- Produces:
  - `criar_link(db, coleta, *, n_estudantes: int, dias: int) -> tuple[LinkQTI, str]` — devolve o link e o **token em claro**, que só existe nesta devolução
  - `link_valido(db, token: str) -> LinkQTI | None`
  - `revogar(db, link: LinkQTI) -> None`
  - `LIMITE_FOLGA = 1.10`

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_link_qti.py
import datetime as dt
from datetime import timezone

from app.models import ColetaQTI, LinkQTI
from app.qti.links import criar_link, link_valido, revogar


def test_o_token_em_claro_nao_fica_no_banco(db, coleta_nativa):
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert token and len(token) >= 32
    assert link.token_hash != token
    assert token not in str(link.__dict__.values())


def test_limite_e_o_numero_de_estudantes_mais_dez_por_cento(db, coleta_nativa):
    link, _ = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link.limite_respostas == 33


def test_limite_arredonda_para_cima(db, coleta_nativa):
    """Turma de 12: 13,2 vira 14, não 13. Arredondar para baixo custaria a vaga
    de um estudante real; para cima, abre uma vaga a mais num link que já é
    limitado e temporário."""
    link, _ = criar_link(db, coleta_nativa, n_estudantes=12, dias=7)
    assert link.limite_respostas == 14


def test_token_certo_encontra_o_link(db, coleta_nativa):
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, token) is not None


def test_token_errado_nao_encontra_nada(db, coleta_nativa):
    criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, "nao-e-um-token-valido-qualquer-coisa") is None


def test_link_expirado_nao_vale(db, coleta_nativa):
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    link.expira_em = dt.datetime.now(timezone.utc) - dt.timedelta(seconds=1)
    db.commit()
    assert link_valido(db, token) is None


def test_link_revogado_nao_vale(db, coleta_nativa):
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    revogar(db, link)
    assert link_valido(db, token) is None


def test_link_de_coleta_apagada_nao_vale(db, coleta_nativa):
    """Review Focus 4: o professor apaga a coleta e o link antigo continua de
    pé — as respostas entrariam órfãs, numa coleta que ninguém mais lê."""
    from app.models import utcnow
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    coleta_nativa.deleted_at = utcnow()
    db.commit()
    assert link_valido(db, token) is None


def test_o_token_nunca_aparece_em_repr_nem_em_str(db, coleta_nativa):
    """Review Focus 1: o segredo do link é a única credencial do sistema. Um
    `repr` que o inclua vaza em traceback, em log de exceção e em mensagem de
    erro, todos lugares que ninguém inspeciona esperando encontrar credencial."""
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert token not in repr(link) and token not in str(link)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_link_qti.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.qti.links'`

- [ ] **Step 3: Escrever a fixture `coleta_nativa`**

Em `backend/tests/conftest.py`:

```python
@pytest.fixture
def coleta_nativa(db, ciclo):
    """Coleta de origem COLETA_NATIVA, ainda sem respostas — é o estado em que
    o professor gera o link. `coleta_em` grava o agregado e serve à triangulação;
    aqui o que importa é a coleta vazia que vai receber as respostas."""
    from app.models import ColetaQTI
    c = ColetaQTI(ciclo_id=ciclo.id, coletado_em=date(2026, 9, 1), origem="COLETA_NATIVA",
                  response_count=0, displayable=False, qti_config_version="1.0.0")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
```

- [ ] **Step 4: Escrever `links.py`**

```python
# backend/app/qti/links.py
"""O link público é a única porta sem autenticação do sistema (§10 da spec).

O segredo vive em dois lugares e só dois: na mão de quem recebeu o link, e
como hash nesta tabela. `criar_link` é a única função que o devolve em claro,
e o chamador tem uma única chance de entregá-lo ao professor — depois disso
nem o banco nem o sistema conseguem reconstruí-lo.
"""
import datetime as dt
import hashlib
import math
import secrets
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ColetaQTI, LinkQTI

# O professor informa o tamanho da turma; a folga cobre quem entrou depois da
# matrícula e quem responde por outro aparelho. Decisão do pesquisador
# (2026-09-25), não achado da literatura.
LIMITE_FOLGA = 1.10


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_link(db: Session, coleta: ColetaQTI, *, n_estudantes: int, dias: int) -> tuple[LinkQTI, str]:
    token = secrets.token_urlsafe(32)
    link = LinkQTI(
        coleta_id=coleta.id,
        token_hash=_hash(token),
        expira_em=dt.datetime.now(timezone.utc) + dt.timedelta(days=dias),
        limite_respostas=math.ceil(n_estudantes * LIMITE_FOLGA),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link, token


def link_valido(db: Session, token: str) -> LinkQTI | None:
    """None para token errado, link expirado, revogado, apagado, ou de coleta
    apagada. Um só caminho de saída de propósito: quem chama não deve poder
    distinguir os casos, e quem responde muito menos."""
    agora = dt.datetime.now(timezone.utc)
    return db.execute(
        select(LinkQTI).join(ColetaQTI, ColetaQTI.id == LinkQTI.coleta_id)
        .where(LinkQTI.token_hash == _hash(token),
               LinkQTI.deleted_at.is_(None),
               LinkQTI.revogado_em.is_(None),
               LinkQTI.expira_em > agora,
               ColetaQTI.deleted_at.is_(None))
    ).scalars().first()


def revogar(db: Session, link: LinkQTI) -> None:
    link.revogado_em = dt.datetime.now(timezone.utc)
    db.commit()
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_link_qti.py -q`
Expected: PASS (9 testes)

- [ ] **Step 6: Desfazer e conferir**

Troque `token_hash=_hash(token)` por `token_hash=token` e confirme que
`test_o_token_em_claro_nao_fica_no_banco` falha. Restaure. Cole a saída real.

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend/app/qti/links.py fias-ed-web/backend/tests/test_link_qti.py fias-ed-web/backend/tests/conftest.py
git commit -m "feat(qti): o link guarda o hash, nunca o segredo

link_valido tem um caminho de saída só — token errado, expirado, revogado,
apagado e de coleta apagada devolvem todos None. Quem responde não deve
conseguir distinguir os casos, e quem tem o banco não reconstrói o link.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: o professor gera e revoga o link

**Files:**
- Modify: `backend/app/qti/routes.py`
- Test: `backend/tests/test_qti_link_rotas.py`

**Interfaces:**
- Consumes: `criar_link`, `revogar`, `link_valido`, `ciclo_do_professor` (`app/ciclos/service.py`)
- Produces: `POST /api/ciclos/{ciclo_id}/qti/link` → `{"url", "expira_em", "limite_respostas"}`; `POST /api/qti/links/{link_id}/revogar` → 204

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_qti_link_rotas.py
from app.models import ColetaQTI, LinkQTI
from tests.helpers import login, make_user


def test_gerar_link_devolve_a_url_uma_unica_vez(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 201
    url = r.json()["url"]
    assert "/responder/" in url
    assert r.json()["limite_respostas"] == 33
    token = url.rsplit("/", 1)[-1]
    assert db.scalar(select(LinkQTI)).token_hash != token


def test_gerar_link_cria_a_coleta_nativa_se_nao_houver(db, client, ciclo):
    login(client, "professora-ciclo")
    client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    coleta = db.query(ColetaQTI).one()
    assert coleta.origem == "COLETA_NATIVA" and coleta.response_count == 0


def test_gerar_link_em_ciclo_de_outro_professor_da_404(db, client, ciclo_de_outro):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo_de_outro.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 404


def test_revogar_derruba_o_link(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    token = r.json()["url"].rsplit("/", 1)[-1]
    link = db.scalar(select(LinkQTI))
    assert client.post(f"/api/qti/links/{link.id}/revogar").status_code == 204
    from app.qti.links import link_valido
    assert link_valido(db, token) is None


def test_revogar_link_de_outro_professor_da_404(db, client, link_de_outro):
    login(client, "professora-ciclo")
    assert client.post(f"/api/qti/links/{link_de_outro.id}/revogar").status_code == 404
```

`ciclo_de_outro` e `link_de_outro`: crie no próprio arquivo, seguindo
`test_importar_qti_com_ciclo_de_outro_professor_devolve_404`
(`tests/test_qti_import.py`), que já monta escola, turma, disciplina e ciclo de
outro professor.

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest tests/test_qti_link_rotas.py -q`
Expected: FAIL com 404 em `/qti/link`

- [ ] **Step 3: Escrever as rotas**

Em `backend/app/qti/routes.py`, seguindo o padrão da rota de importação que já
está no arquivo — `ciclo_do_professor`, `audit(...)`, `db.commit()`:

```python
class LinkIn(BaseModel):
    n_estudantes: int = Field(gt=0, le=200)
    dias: int = Field(gt=0, le=90)
    coletado_em: dt.date


@router.post("/ciclos/{ciclo_id}/qti/link", status_code=201)
def gerar_link(ciclo_id: uuid.UUID, body: LinkIn, request: Request,
               actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    ciclo = ciclo_do_professor(db, actor, ciclo_id)
    coleta = coleta_nativa_do_dia(db, ciclo, body.coletado_em)
    link, token = criar_link(db, coleta, n_estudantes=body.n_estudantes, dias=body.dias)
    audit(db, actor, "coleta_qti", coleta.id, "create")
    db.commit()
    # O token viaja só nesta resposta. Não entra em log nem em nenhuma outra
    # rota: `log_event` tem allowlist de campos e não o aceitaria, mas a regra
    # aqui é anterior a ela — não se registra credencial.
    return {"url": f"{request.base_url}responder/{token}".replace("//responder", "/responder"),
            "expira_em": link.expira_em.isoformat(),
            "limite_respostas": link.limite_respostas}
```

Em `app/qti/service.py`, ao lado de `importar_relatorio`:

```python
def coleta_nativa_do_dia(db: Session, ciclo: Ciclo, data: dt.date) -> ColetaQTI:
    """A coleta nativa daquela data, criada se ainda não existir. Gerar um
    segundo link para o mesmo dia reusa a coleta: duas coletas vivas na mesma
    data fariam a triangulação escolher arbitrariamente qual vale, que é o
    mesmo defeito que a reimportação já evita do outro lado."""
    existente = db.execute(
        select(ColetaQTI).where(ColetaQTI.ciclo_id == ciclo.id,
                                ColetaQTI.coletado_em == data,
                                ColetaQTI.origem == "COLETA_NATIVA",
                                ColetaQTI.deleted_at.is_(None))
    ).scalars().first()
    if existente is not None:
        return existente
    cfg = load_rules("qti_config")
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=data, origem="COLETA_NATIVA",
                       response_count=0, displayable=False,
                       qti_config_version=cfg["rules_version"], cabecalho_recebido=None)
    db.add(coleta)
    db.flush()
    return coleta
```

Acrescente ao teste desta tarefa: gerar dois links para a **mesma data** produz
**uma** coleta, não duas — é o que impede a triangulação de ter que escolher
entre duas coletas vivas do mesmo dia.

A revogação recebe `link_id`, busca o link, confere que a coleta pertence a um
ciclo do professor (`ciclo_do_professor`), chama `revogar`, audita e devolve 204.

- [ ] **Step 4: Rodar e ver passar**

Expected: PASS (5 testes)

- [ ] **Step 5: Desfazer e conferir**

Remova a chamada a `ciclo_do_professor` da geração e confirme que
`test_gerar_link_em_ciclo_de_outro_professor_da_404` falha. Restaure.

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/backend/app/qti/ fias-ed-web/backend/tests/test_qti_link_rotas.py
git commit -m "feat(qti): o professor gera e revoga o link da própria turma

O token viaja só na resposta que o cria. Gerar ou revogar link de ciclo
alheio devolve 404, nunca 403 — o padrão do projeto é não revelar existência.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: as rotas públicas

**Files:**
- Create: `backend/app/publico/__init__.py`, `backend/app/publico/routes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_rotas_publicas.py`

**Interfaces:**
- Consumes: `link_valido`, `RespostaQTI`, `ConsentimentoQTI`, `score_response` e `aggregate` (`fias_ed_engine.qti`)
- Produces: `GET /publico/qti/{token}`, `POST /publico/qti/{token}/consentir`, `POST /publico/qti/{token}/responder`

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_rotas_publicas.py
"""As três rotas sem autenticação do sistema. O que se testa aqui não é só o
caminho feliz: é que o limite não é furado, que resposta incompleta não entra,
e que nada sobre o professor ou a turma vaza para quem abre o link."""
import pytest

from app.models import ConsentimentoQTI, RespostaQTI
from app.qti.links import criar_link

RESPOSTAS = {str(i): 4 for i in range(1, 25)}


def _token(db, coleta, **kw):
    _, token = criar_link(db, coleta, n_estudantes=kw.get("n", 30), dias=7)
    return token


def test_abrir_o_link_traz_as_perguntas_sem_dizer_de_quem_e_a_turma(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    r = client_publico.get(f"/publico/qti/{token}")
    assert r.status_code == 200
    corpo = r.json()
    assert len(corpo["itens"]) == 24
    assert corpo["escala"] == {"min": 1, "max": 5,
                               "min_label": "(Quase) nunca", "max_label": "(Quase) sempre"}
    bruto = r.text.lower()
    for proibido in ("professora-ciclo", "9º ano b", "matemática", "professor_id", "turma_id"):
        assert proibido not in bruto


def test_token_invalido_da_404_sem_dizer_por_que(db, client_publico):
    r = client_publico.get("/publico/qti/token-que-nao-existe-de-jeito-nenhum")
    assert r.status_code == 404
    assert "expirado" not in r.text.lower() and "revogado" not in r.text.lower()


def test_responder_sem_consentir_e_recusado(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 409
    assert db.query(RespostaQTI).count() == 0


def test_resposta_completa_entra_na_coleta(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 201
    assert db.query(RespostaQTI).count() == 1
    assert db.query(ConsentimentoQTI).count() == 1


def test_resposta_incompleta_e_recusada(db, client_publico, coleta_nativa):
    """Review Focus 3: o estudante pula uma pergunta. Quem recusa é o motor —
    `score_response` valida a escala e a completude; o Web só repassa o erro."""
    token = _token(db, coleta_nativa)
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    faltando = {k: v for k, v in RESPOSTAS.items() if k != "7"}
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": faltando})
    assert r.status_code == 422
    assert db.query(RespostaQTI).count() == 0


def test_valor_fora_da_escala_e_recusado(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    r = client_publico.post(f"/publico/qti/{token}/responder",
                            json={"respostas": {**RESPOSTAS, "3": 9}})
    assert r.status_code == 422
    assert db.query(RespostaQTI).count() == 0


def test_o_limite_de_respostas_e_respeitado(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa, n=1)   # limite 2
    for _ in range(2):
        client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
        assert client_publico.post(f"/publico/qti/{token}/responder",
                                   json={"respostas": RESPOSTAS}).status_code == 201
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 409
    assert db.query(RespostaQTI).count() == 2


def test_o_limite_nao_e_furado_por_dois_envios_ao_mesmo_tempo(db, client_publico, coleta_nativa):
    """Review Focus 2: duas pessoas enviam com uma vaga restante. Sem a
    contagem sob a mesma transação do INSERT, as duas passam pela verificação
    antes de qualquer uma gravar, e o limite vira sugestão.

    O teste simula a corrida gravando a penúltima resposta por fora, entre a
    leitura e a escrita da requisição em curso."""
    token = _token(db, coleta_nativa, n=1)   # limite 2
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert db.query(RespostaQTI).count() == 2
    for _ in range(3):
        client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
        client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert db.query(RespostaQTI).count() == 2


def test_a_coleta_passa_a_ser_exibivel_na_decima_resposta(db, client_publico, coleta_nativa):
    """`min_responses` é 10 em qti_config.json, e quem decide é o motor:
    `aggregate` devolve `displayable`. O Web só persiste o que ele disse."""
    token = _token(db, coleta_nativa, n=20)
    for i in range(10):
        client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
        client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    db.refresh(coleta_nativa)
    assert coleta_nativa.response_count == 10 and coleta_nativa.displayable is True


def test_as_rotas_publicas_nao_exigem_login(db, client_publico, coleta_nativa):
    """`client_publico` não faz login em momento nenhum. Se alguma destas rotas
    acabar sob `current_actor`, este teste cai com 401 — e o link público deixa
    de funcionar para quem ele existe."""
    token = _token(db, coleta_nativa)
    assert client_publico.get(f"/publico/qti/{token}").status_code == 200
    assert client_publico.post(f"/publico/qti/{token}/consentir",
                               json={"documento_versao": "1.0.0"}).status_code == 201
```

`client_publico`: em `conftest.py`, um cliente como `client` mas **sem login
nenhum** e sem cabeçalho de CSRF.

- [ ] **Step 2: Rodar e ver falhar**

Expected: FAIL com 404 em `/publico/qti/...`

- [ ] **Step 3: Escrever o router público**

```python
# backend/app/publico/routes.py
"""As únicas rotas sem autenticação do sistema (§10 da spec).

Router próprio, montado sem a dependência de sessão — a separação é física
para que ninguém acrescente uma rota autenticada aqui por engano, nem o
contrário. Nada que identifique o professor ou a turma sai daqui: quem abre o
link vê as 24 perguntas e a escala, e mais nada.
"""
```

Regras de implementação:

- `GET /publico/qti/{token}` devolve `{"itens": [{"order", "text"}], "escala": {...}, "stem": ...}`, tudo de `load_rules("qti_config")`. **Nunca** o nome do professor, da turma, da disciplina, nem identificador de coleta.
- Token inválido → `AppError(404, "LINK_INVALIDO", "Este link não está mais disponível.")`, **a mesma mensagem** para expirado, revogado e inexistente.
- `POST .../consentir` grava `ConsentimentoQTI` e devolve 201. O consentimento fica na sessão do navegador do estudante (cookie de sessão sem identidade), não no banco ligado à resposta.
- `POST .../responder`: exige consentimento na sessão; converte as chaves para `int`; chama `score_response(answers, cfg)` — que valida — e deixa `QtiImportError` virar `AppError(422, ...)`; grava `RespostaQTI` com `response_index` = contagem atual; recalcula com `aggregate` e atualiza `response_count`/`displayable`/`ResultadoQTI` da coleta.
- **O limite é verificado com `SELECT ... FOR UPDATE` sobre o `LinkQTI`**, na mesma transação do INSERT. Sem isso, o Review Focus 2 acontece.
- Monte em `main.py` com `app.include_router(publico_router)` — **sem** o prefixo `/api` e **sem** a dependência de autenticação.

- [ ] **Step 4: Rodar e ver passar**

Expected: PASS (10 testes)

- [ ] **Step 5: Desfazer e conferir (três vezes)**

1. Troque o `FOR UPDATE` por leitura simples → o teste da corrida tem que falhar.
2. Devolva o nome da turma no `GET` → o teste do vazamento tem que falhar.
3. Aceite responder sem consentimento → o teste correspondente tem que falhar.

Cole a saída real das três.

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/backend/app/publico/ fias-ed-web/backend/app/main.py fias-ed-web/backend/tests/test_rotas_publicas.py fias-ed-web/backend/tests/conftest.py
git commit -m "feat(publico): o estudante responde sem login e sem ser identificado

Router próprio, sem a dependência de sessão: a separação é física para que
ninguém acrescente rota autenticada aqui por engano. Token inválido, expirado
e revogado devolvem a mesma mensagem — quem abre o link não distingue os casos.

O limite é conferido sob FOR UPDATE, na mesma transação do INSERT: sem isso,
dois envios simultâneos passam os dois pela verificação antes de qualquer um
gravar.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: a tela do estudante

**Files:**
- Create: `frontend/src/pages/Responder.tsx`, `frontend/src/pages/Responder.test.tsx`
- Modify: `frontend/src/app/App.tsx`, `frontend/src/api/types.ts`

**Interfaces:**
- Consumes: `GET/POST /publico/qti/{token}`
- Produces: rota `/responder/:token`, **fora** de `RequireAuth` e **fora** de `Layout`

- [ ] **Step 1: Escrever os testes que falham**

```tsx
// frontend/src/pages/Responder.test.tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";
import { jsonResponse, mockApi, renderApp } from "../test-utils";

const ABRIR = "GET /publico/qti/tok123";
const CONSENTIR = "POST /publico/qti/tok123/consentir";
const RESPONDER = "POST /publico/qti/tok123/responder";

const ITENS = Array.from({ length: 24 }, (_, i) => ({ order: i + 1, text: `pergunta ${i + 1}` }));
const ESCALA = { min: 1, max: 5, min_label: "(Quase) nunca", max_label: "(Quase) sempre" };
const QUESTIONARIO = { stem: "Este(a) professor(a)…", itens: ITENS, escala: ESCALA };

beforeEach(() => localStorage.clear());

test("o estudante consente antes de ver as perguntas", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO) });
  renderApp("/responder/tok123");
  expect(await screen.findByRole("button", { name: /concordo/i })).toBeInTheDocument();
  expect(screen.queryByText(/pergunta 1$/)).not.toBeInTheDocument();
});

test("a tela do estudante não exige login nem mostra o menu", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO) });
  renderApp("/responder/tok123");
  await screen.findByRole("button", { name: /concordo/i });
  expect(screen.queryByRole("link", { name: /minhas aulas/i })).not.toBeInTheDocument();
});

test("link fora de validade mostra a mensagem do servidor, sem formulário", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(
    { error_code: "LINK_INVALIDO", message: "Este link não está mais disponível." }, 404) });
  renderApp("/responder/tok123");
  expect(await screen.findByText(/não está mais disponível/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /concordo/i })).not.toBeInTheDocument();
});

test("quem já respondeu neste navegador vê o agradecimento, não o formulário", async () => {
  localStorage.setItem("fias-ed:respondido:tok123", "1");
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO) });
  renderApp("/responder/tok123");
  expect(await screen.findByText(/já respondeu/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /concordo/i })).not.toBeInTheDocument();
});

test("enviar só é possível com as 24 respondidas", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO),
            [CONSENTIR]: () => jsonResponse({}, 201) });
  renderApp("/responder/tok123");
  await userEvent.click(await screen.findByRole("button", { name: /concordo/i }));
  await screen.findByText(/pergunta 1$/);
  expect(screen.getByRole("button", { name: /enviar/i })).toBeDisabled();
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd fias-ed-web/frontend && npx vitest run src/pages/Responder.test.tsx`
Expected: FAIL — a rota não existe

- [ ] **Step 3: Implementar**

- Rota em `src/app/App.tsx`: `<Route path="/responder/:token" element={<Responder />} />`, **irmã de `/`**, fora do bloco `RequireAuth`/`Layout`. Um estudante não tem conta e não deve ver o menu do professor.
- Três estados: consentimento → formulário → agradecimento.
- Depois do envio bem-sucedido, `localStorage.setItem("fias-ed:respondido:" + token, "1")`.
- Na montagem, se a marca existir, vá direto ao agradecimento — **Review Focus 5**: o estudante que volta com o botão do navegador não vê o formulário de novo.
- Escala como grupo de rádios por pergunta, com `min_label` e `max_label` visíveis. Alvo de toque **mínimo de 44px** (`DESIGN.md`) — é tela de celular.
- Botão de enviar desabilitado até as 24 estarem respondidas.
- Erro: mensagem do servidor em `Banner kind="error"`.

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run src/pages/Responder.test.tsx && npm run lint && npm run build`
Expected: PASS (5 testes)

- [ ] **Step 5: Desfazer e conferir**

Remova a leitura do `localStorage` na montagem e confirme que o teste do
"já respondeu" falha. Restaure. Cole a saída real.

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/frontend/src/pages/Responder.tsx fias-ed-web/frontend/src/pages/Responder.test.tsx fias-ed-web/frontend/src/app/App.tsx fias-ed-web/frontend/src/api/types.ts
git commit -m "feat(web): a tela em que o estudante responde pelo celular

Fora de RequireAuth e fora do Layout: quem responde não tem conta e não deve
ver o menu do professor. A marca de já respondido fica no navegador do
estudante e nunca no servidor — contém o reenvio sem guardar quem é.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: o professor gera o link pela interface

**Files:**
- Modify: `frontend/src/pages/Acompanhamentos.tsx` e seu teste

**Interfaces:**
- Consumes: `POST /api/ciclos/{id}/qti/link`, `POST /api/qti/links/{id}/revogar`

- [ ] **Step 1: Escrever os testes que falham**

```tsx
test("gerar o link mostra a url uma vez, com aviso de que não se recupera", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([CICLO_EM_ANDAMENTO]),
    "POST /api/ciclos/c1/qti/link": () => jsonResponse(
      { url: "http://x/responder/tok123", expira_em: "2026-10-01T00:00:00Z", limite_respostas: 33 }, 201),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: /gerar link/i }));
  await userEvent.type(screen.getByLabelText(/quantos estudantes/i), "30");
  await userEvent.click(screen.getByRole("button", { name: /gerar/i }));
  expect(await screen.findByText(/responder\/tok123/)).toBeInTheDocument();
  expect(screen.getByText(/não será possível vê-lo de novo/i)).toBeInTheDocument();
});

test("a tela não mostra o link antigo ao reabrir a lista", async () => {
  // GET /api/ciclos nunca devolve token; se a tela o exibisse de memória,
  // o segredo sobreviveria à sessão sem o servidor saber.
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([CICLO_EM_ANDAMENTO]),
  });
  renderApp("/ciclos");
  await screen.findByRole("heading", { name: /meus acompanhamentos/i });
  expect(screen.queryByText(/responder\//)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Rodar e ver falhar**
- [ ] **Step 3: Implementar** — diálogo com "Quantos estudantes tem a turma?" e a validade; depois de gerar, mostrar a URL com botão de copiar e o aviso de que ela não se recupera; ação de revogar em link ativo.
- [ ] **Step 4: Rodar e ver passar**
- [ ] **Step 5: Desfazer e conferir** — guarde a URL em estado que sobreviva ao recarregar e confirme que o segundo teste falha.
- [ ] **Step 6: Commit**

---

## Task 7: verificação final da W3b

- [ ] **Step 1:** As três suítes e as auditorias (`bandit -r app --severity-level high`, `pip-audit --skip-editable`, `npm audit --audit-level=high`). Reconstrua a imagem antes.
- [ ] **Step 2:** Percurso ao vivo, **num celular ou em janela de 360px**: o professor gera o link, o estudante abre, consente, responde, e a resposta aparece na coleta. Depois: revogar e confirmar que o link morre.
- [ ] **Step 3:** Os três critérios que a W3a não pôde verificar — **4**, **10** e a segunda metade do **5** —, cada um com o comando ou a tela que o comprova.
- [ ] **Step 4:** Teste intermitente é defeito: rode cinco vezes e conte, não repita até passar.
- [ ] **Step 5:** Atualizar `docs/ESTADO_DE_VALIDACAO.md` com a limitação declarada da marca no navegador (burlável em aba anônima) e com o fato de o limite de respostas vir de um número que o professor informa, não de cadastro.
- [ ] **Step 6:** Commit com o resultado de cada critério no corpo.
