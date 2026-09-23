# FIAS-ED Web — W2 Pipeline: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levar a aula de `AUDIO_VALIDATED` a `FIAS_COMPLETED`: normalização e chunks, transcrição, diarização, a tela "qual destas vozes é você?", a revisão da transcrição, a classificação FIAS e a tela de padrões de interação.

**Architecture:** Quatro jobs novos na fila que já existe (`prepare_audio`, `transcribe`, `diarize`, `classify_fias`), consumidos pelo worker da W1. Os três modelos de ML entram atrás de protocolos finos (`ASR`, `Diarizador`, `Classificador`) e são substituídos por implementações falsas nos testes, de modo que a suíte inteira roda sem GPU e sem peso de modelo. Nenhuma regra científica é implementada aqui: o backend orquestra e persiste, e `fias_ed_engine` do shared decide.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3; `faster-whisper`, `pyannote.audio`, `transformers` + `torch` (CPU/CUDA), `ffmpeg`; React, TypeScript, Vite, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-22-fias-ed-web-w2-pipeline-design.md` (requisitos originais em `docs/PROMPT_MESTRE.md`; decomposição das fatias no spec da W1).

## Global Constraints

Valem para todas as tasks. Copiadas do spec e do plano da W1.

- Tudo em `fias-ed-web/`. **Não alterar** `artigos selecionados\` nem `avalie-seu-professor\`. `fias-ed-shared/` é somente leitura nesta fatia, com uma exceção: a Task 2 pode acrescentar entradas a `scientific-config/models.json` para o ASR e a diarização, seguindo o formato que já existe.
- Nenhuma regra científica é implementada no backend Web. FIAS sai de `fias_ed_engine` (`constrain_by_role`, `segments_to_intervals`, `transition_matrix`, `compute_indices`). A matemática do FIAS **não é retestada** aqui.
- A categoria FIAS sai de `fias_rules.json` → `classifier.logit_index_offset`. **Nenhum código lê `id2label` do checkpoint** (`ANALISE_MODELOS_EXISTENTES.md` §2.2: o `config.json` grava só `LABEL_0..LABEL_9`).
- Entrada do classificador é **par de turnos**: `tokenizer(text_a, text_b)`, WordPiece cased, `max_length=256`, truncation `LongestFirst` à direita, padding `"max_length"`, sem lowercasing e sem prefixo de falante no texto.
- Nenhum peso de modelo no Git. Os artefatos são conferidos contra `fias-ed-shared/scientific-config/models.json` (SHA-256 por artefato) e a carga é recusada se algum `forbidden_files` (`training_args.bin`, `optimizer.pt`, `rng_state.pth`, `scaler.pt`, `scheduler.pt`) estiver no diretório.
- Execução offline: `HF_HUB_OFFLINE=1` e `TRANSFORMERS_OFFLINE=1` nos containers `api` e `worker`. Nenhuma chamada de rede em tempo de execução. O download do `pyannote` acontece uma vez, no setup, fora do fluxo do produto.
- ASR com idioma fixado e decodificação determinística (`temperature=0`), porque o §44 exige que a mesma aula reprocessada dê o mesmo texto. Atenção aos dois valores: o `faster-whisper` recebe `language="pt"` (código que ele conhece), enquanto a coluna `Transcricao.language` guarda `"pt-BR"`, o único valor que o enum do shared aceita.
- Diarização separa **professor do resto**. Não existe `ALUNO_1`/`ALUNO_2` em lugar nenhum, nem no banco. Nenhum embedding de voz é persistido (§48).
- Todo `Segmento` tem `text_pseudonymized` com nomes próprios trocados por `[NOME]`, inclusive depois de o professor editar o texto (`PRIVACY.md`).
- Original nunca modificado (§17). Cópia de trabalho e chunks são apagados ao fim do estágio que os consome.
- Erros da API sempre `{"error_code": "...", "message": "..."}`, mensagens em português, nunca stack trace. Mensagens de progresso são as do §36.
- Logs só pelo helper `log_event`, cuja lista `ALLOWED_FIELDS` é **validada em tempo de execução**: um campo fora dela levanta erro, não passa silenciosamente. Ao acrescentar um campo novo (contagens como `n_segmentos` e `n_vozes` são aceitáveis), estenda `ALLOWED_FIELDS` em `app/core/logging.py` na mesma task. **Nunca** texto de transcrição, nome de arquivo, nome de professor, turma ou estudante.
- Recurso de outro professor → 404. Rotas de admin chamadas por PROFESSOR → 403. "Professor efetivo" segue a regra da W1 (`sessao.acting_as_professor_id`), e o admin agindo como professor grava `acesso_admin`.
- Frontend: sem `dangerouslySetInnerHTML` (regra de lint já existente — a transcrição é o primeiro texto longo editável que o produto renderiza de volta), sem atributo `style`, sem biblioteca de componentes, sem fonte de CDN.
- Interface em pt-BR com o vocabulário do `PRODUCT.md`: nunca "avaliação", "avaliar", "nota", "desempenho", "ranking". O sistema **analisa** e devolve padrões.
- Visual: só tokens de `tokens.css`; nenhuma cor nova; `border-radius` só `--radius-sm`/`--radius-md`; Rokkitt só em título ≥ 24 px; sombra só no diálogo. `DESIGN.md` é a autoridade.
- Acessibilidade WCAG 2.1 AA: foco visível, rótulo associado a todo campo, estado nunca só por cor, navegação por teclado.
- Toda mensagem de commit termina com a linha `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

## Decisões do plano

1. **Os protocolos de ML vêm antes de qualquer modelo real.** A Task 3 define `ASR`, `Diarizador` e `Classificador` com implementações falsas; os jobs são escritos e testados contra os falsos, e os modelos reais entram depois, atrás da mesma interface. Sem isso, nenhum job é testável sem GPU.
2. **`Falante` guarda papel, não voz.** A tabela tem `papel` (`PROFESSOR`/`ALUNO`) e nenhuma coluna de agrupamento por voz. Os rótulos do `pyannote` vivem só na memória do job de diarização e no payload da tela de escolha; depois da escolha, somem.
3. **O alinhamento é função pura.** `align_segments_to_turns(segmentos, turnos)` não toca banco nem modelo, e é onde mora a lógica que mais erra. Testado sozinho, com casos construídos à mão.
4. **A revisão salva por segmento, com `updated_at` otimista.** Duas abas editando o mesmo segmento: a segunda escrita recebe 409 e a tela recarrega aquele segmento, em vez de sobrescrever em silêncio.
5. **A pseudonimização usa NER local unido a uma heurística conservadora.** O detector primário é um modelo de NER de português pequeno e de CPU (`pt_core_news_sm` do spaCy ou equivalente de licença aberta), na ordem de dezenas de MB — irrelevante ao lado dos 435 MB do BERTimbau que o registro já traz, e sem disputar VRAM. A heurística de maiúscula continua rodando **em união** com ele: qualquer um dos dois que aponte um nome, pseudonimiza. NER em fala transcrita rende menos que em texto limpo, e é por isso que a heurística fica — não para substituí-lo, para cobrir o que ele perde. O viés é deliberadamente conservador: um falso positivo troca uma palavra comum por `[NOME]` na versão exportada; um falso negativo vaza o nome de um estudante.
   (O §33 veda LLM externo para pontuação e recomendação — não alcança um NER local usado para privacidade.)
6. **A tela de padrões mostra tudo na mesma página**, por decisão registrada no spec §2.5. A matriz vai como tabela de números.

## Como rodar (referência para todas as tasks)

Todos os comandos a partir de `fias-ed-web/` (Git Bash):

- Testes do backend: `docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q`
  (um teste: `... run --rm api-test pytest -q tests/test_x.py::test_y`; `--build` só quando mudar dependências ou o Dockerfile).
- Testes do frontend: `cd frontend && npm test` e `npm run lint`.
- Sistema completo: `docker compose up -d --build` → `http://localhost:8080`.
- Testes lentos (com modelo real, fora da suíte padrão): `... run --rm api-test pytest -q -m lento`.

## Mapa de arquivos

Novos e modificados nesta fatia. Cada arquivo tem uma responsabilidade.

```
fias-ed-web/
  .env.example                              + FIAS_ED_MODELS_DIR, FIAS_ED_ASR_SIZE, HF_HUB_OFFLINE
  docker-compose.yml                        + volume de modelos em api e worker
  README.md                                 + setup dos modelos, token do HF, tabela de medição
  scripts/setup_models.py                   baixa/valida os artefatos contra models.json
  backend/
    pyproject.toml                          + faster-whisper, pyannote.audio, transformers, torch
    alembic/versions/0002_w2_pipeline.py    tabelas novas
    app/models.py                           + Transcricao, Segmento, Falante, ClassificacaoFIAS,
                                              IndicadorFIAS, ModeloIA
    app/core/config.py                      + caminhos e parâmetros dos modelos
    app/ml/registry.py                      lê models.json, confere SHA-256 e forbidden_files
    app/ml/protocols.py                     ASR, Diarizador, Classificador (Protocol)
    app/ml/fakes.py                         implementações falsas, usadas só em teste
    app/ml/asr_whisper.py                   faster-whisper atrás do protocolo
    app/ml/diar_pyannote.py                 pyannote atrás do protocolo
    app/ml/clf_bertimbau.py                 BERTimbau atrás do protocolo (par de turnos)
    app/ml/loader.py                        escolhe real ou falso conforme a configuração
    app/audio/prepare.py                    cópia de trabalho, normalização, plano de chunks
    app/pipeline/align.py                   alinhamento ASR × diarização (puro)
    app/pipeline/pseudonymize.py            nomes próprios → [NOME] (puro)
    app/transcricao/service.py              persistência e revisão incremental
    app/transcricao/routes.py               API da revisão e da escolha de voz
    app/fias/service.py                     chama o motor do shared, persiste indicadores
    app/fias/routes.py                      leitura dos padrões de interação
    app/jobs/handlers.py                    + prepare_audio, transcribe, diarize, classify_fias
    tests/…                                 um arquivo por área
  frontend/src/
    api/types.ts                            + Transcricao, Segmento, GrupoDeVoz, PadroesFIAS
    app/status.ts                           (já cobre os 18 status; sem mudança)
    pages/EscolhaVoz.tsx                    "qual destas vozes é você?"
    pages/RevisaoTranscricao.tsx            a maior tela da fatia
    pages/PadroesInteracao.tsx              faixa de tempo, observações, matriz, índices
    design/components/FaixaDeTempo.tsx      barra de quem falou quando
    design/components.css                   + classes das telas novas
```

## Review Focus

Cinco classes de entrada que o spec implica, que nenhum teste óbvio cobre, e que quebram na mão de quem usa. Cada uma tem o teste que a fixa na task que é dona do código.

1. **Áudio de 90 minutos, último chunk incompleto** — um erro de um chunk na soma de deslocamentos produz um segmento com horário maior que a duração do arquivo, e a faixa de tempo estoura. Teste em **Task 4**.
2. **Segmento do ASR que cruza a fronteira de dois turnos de diarização** (alguém interrompe o professor no meio da frase) — o alinhamento precisa decidir por maior sobreposição, não empatar nem descartar o segmento. Teste em **Task 7**.
3. **Professor digita `<`, `>`, aspas ou emoji na transcrição** — o texto volta para a tela e, na W3, para o relatório. Precisa aparecer literal, sem escapar duas vezes e sem executar. Teste em **Task 9**.
4. **Nome próprio homônimo de substantivo comum** ("Vitória", "Bela", "Paz") no meio da frase — a pseudonimização precisa de comportamento definido e conservador, não de acaso. Teste em **Task 6**.
5. **Duas abas editando o mesmo segmento** — a segunda escrita não pode sobrescrever a primeira em silêncio. Teste em **Task 9**.

---
### Task 1: Tabelas da W2 e migração

> **As seis entidades já estão especificadas** em `fias-ed-shared/schemas/entities/`.
> Este é o modelo lógico de dados do projeto, compartilhado com o Android, e é a
> autoridade: os nomes de campo, os tipos, os enums e a nulidade saem de lá,
> literalmente. `test_schema_compat.py` compara coluna a coluna e reprova por
> campo ausente, tipo diferente, enum diferente, `maxLength` diferente ou
> nulidade diferente. Não invente campo nem renomeie nada.

**Files:**
- Modify: `backend/app/models.py`, `backend/tests/test_schema_compat.py`
- Create: `backend/alembic/versions/0002_w2_pipeline.py` (gerado)
- Test: `backend/tests/test_models_w2.py`

**Interfaces:**
- Consumes: `EntityMixin`, `Base`, `_enum`, `TRANSCRIPT_SOURCES` de `app/models.py` (W1).
- Produces: `Transcricao`, `Falante`, `Segmento`, `ClassificacaoFIAS`, `IndicadorFIAS`, `ModeloIA`.

**Decisão de privacidade que governa o uso destas tabelas** (não é coluna, é
como elas são preenchidas): entre a diarização e a escolha da voz existe **uma
linha `Falante` por voz detectada**, todas com `role="UNASSIGNED"` e o
`diarization_label` do diarizador. Na escolha, essas linhas colapsam em
**exatamente duas**: um `PROFESSOR` com o `diarization_label` da voz escolhida e
um `ALUNO` com `diarization_label = "merged"`. Nenhum agrupamento de voz por
estudante sobrevive à escolha (§48). A Task 8 implementa esse colapso; aqui só
existe a tabela que o permite.

- [x] **Step 1: Escrever o teste que falha**

Cria `backend/tests/test_models_w2.py`.

```python
from sqlalchemy import inspect

from app.models import (ClassificacaoFIAS, Falante, IndicadorFIAS, ModeloIA, Segmento,
                        Transcricao)


def _colunas(modelo):
    return {c.name: c for c in inspect(modelo).columns}


def test_falante_tem_os_tres_papeis_do_shared():
    col = _colunas(Falante)["role"]
    assert set(col.type.enums) == {"PROFESSOR", "ALUNO", "UNASSIGNED"}


def test_falante_liga_a_transcricao_e_nao_a_aula():
    colunas = _colunas(Falante)
    assert "transcricao_id" in colunas
    assert "aula_id" not in colunas


def test_segmento_usa_os_nomes_de_tempo_do_shared():
    colunas = _colunas(Segmento)
    assert {"start_ms", "end_ms"} <= set(colunas)
    assert "inicio_ms" not in colunas


def test_segmento_exige_falante_e_aceita_pseudonimizado_nulo():
    colunas = _colunas(Segmento)
    # O schema do shared resolve "ainda não se sabe quem falou" com
    # role=UNASSIGNED, não com FK nula.
    assert colunas["falante_id"].nullable is False
    assert colunas["text_pseudonymized"].nullable is True
    assert colunas["texto_revisado"].nullable is True
    assert colunas["revisado"].nullable is False


def test_classificacao_guarda_a_predicao_crua_e_a_restrita_por_papel():
    colunas = _colunas(ClassificacaoFIAS)
    assert {"pred_raw", "pred_role_constrained", "confidence_raw", "confidence",
            "uncertain"} <= set(colunas)
    # Liga ao segmento, não à aula.
    assert "segmento_id" in colunas and "aula_id" not in colunas


def test_indicador_guarda_a_evidencia_estruturada():
    colunas = _colunas(IndicadorFIAS)
    assert {"index_id", "value", "reason", "numerator_count", "denominator_count",
            "n_intervals", "validation_status"} <= set(colunas)
    assert colunas["value"].nullable is True  # sem dado suficiente


def test_modelo_ia_guarda_licenca_e_procedencia():
    colunas = _colunas(ModeloIA)
    assert {"model_id", "name", "model_version", "task", "format", "sha256",
            "size_bytes", "source", "license", "parameters"} <= set(colunas)


def test_transcricao_fixa_o_idioma_do_produto():
    col = _colunas(Transcricao)["language"]
    assert set(col.type.enums) == {"pt-BR"}
```

- [x] **Step 2: Rodar o teste e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_models_w2.py`
Expected: FAIL com `ImportError: cannot import name 'Transcricao' from 'app.models'`

- [x] **Step 3: Acrescentar as tabelas em `app/models.py`**

Depois de `class Audio`, no estilo das tabelas da W1. Os valores abaixo saem dos
schemas do shared, literalmente.

```python
FALANTE_ROLES = ("PROFESSOR", "ALUNO", "UNASSIGNED")
LANGUAGES = ("pt-BR",)
MODEL_FORMATS = ("safetensors", "onnx", "ggml", "other")
INDICADOR_REASONS = ("insufficient_data",)
VALIDATION_STATUS = ("validated", "PENDING_SCIENTIFIC_VALIDATION", "engineering_decision",
                     "draft_pending_researcher_review")


class Transcricao(EntityMixin, Base):
    __tablename__ = "transcricao"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    audio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audio.id"), nullable=False)
    language: Mapped[str] = mapped_column(_enum(LANGUAGES, "transcricao_language"),
                                          default="pt-BR", nullable=False)
    asr_model_id: Mapped[str] = mapped_column(String, nullable=False)


class Falante(EntityMixin, Base):
    """Uma linha por voz enquanto role=UNASSIGNED; exatamente duas depois da
    escolha do professor (PROFESSOR e ALUNO). Nenhum agrupamento de voz por
    estudante sobrevive à escolha (§48)."""
    __tablename__ = "falante"
    transcricao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcricao.id"), index=True,
                                                      nullable=False)
    diarization_label: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(_enum(FALANTE_ROLES, "falante_role"),
                                      default="UNASSIGNED", nullable=False)


class Segmento(EntityMixin, Base):
    __tablename__ = "segmento"
    transcricao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcricao.id"), index=True,
                                                      nullable=False)
    falante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("falante.id"), nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    texto_original_asr: Mapped[str] = mapped_column(String(10000), nullable=False)
    texto_revisado: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    revisado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    asr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_pseudonymized: Mapped[str | None] = mapped_column(String(10000), nullable=True)


class ClassificacaoFIAS(EntityMixin, Base):
    __tablename__ = "classificacao_fias"
    segmento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("segmento.id"), index=True,
                                                   nullable=False)
    transcript_source: Mapped[str] = mapped_column(
        _enum(TRANSCRIPT_SOURCES, "classificacao_transcript_source"), nullable=False)
    pred_raw: Mapped[int] = mapped_column(Integer, nullable=False)
    pred_role_constrained: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_raw: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)


class IndicadorFIAS(EntityMixin, Base):
    __tablename__ = "indicador_fias"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    index_id: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(_enum(INDICADOR_REASONS, "indicador_reason"),
                                               nullable=True)
    numerator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    n_intervals: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        _enum(VALIDATION_STATUS, "indicador_validation_status"), nullable=False)
    mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class ModeloIA(EntityMixin, Base):
    __tablename__ = "modelo_ia"
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    task: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(_enum(MODEL_FORMATS, "modelo_format"), nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    license: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

Acrescentar `Boolean` e `Float` aos imports do SQLAlchemy, se faltarem.

Conferir cada `maxLength` do schema contra o `String(n)` escrito acima antes de
rodar: o teste de compatibilidade compara o comprimento exato.

- [x] **Step 4: Rodar o teste e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_models_w2.py`
Expected: PASS (8 testes)

- [x] **Step 5: Estender o teste de compatibilidade com o shared**

Em `backend/tests/test_schema_compat.py`, acrescentar as seis entidades à lista:

```python
ENTITY_TABLES = ["professor", "escola", "turma", "disciplina", "aula", "audio", "processamento",
                 "transcricao", "falante", "segmento", "classificacao_fias", "indicador_fias",
                 "modelo_ia"]
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_schema_compat.py`
Expected: PASS (13 parametrizações)

Se alguma reprovar, **a tabela é que está errada**, não o schema: o shared é a
autoridade. Corrija a coluna.

- [x] **Step 6: Gerar e conferir a migração**

Run: `docker compose -f docker-compose.test.yml run --rm api-test alembic revision --autogenerate -m "w2 pipeline"`

Abrir o arquivo gerado em `alembic/versions/` e conferir que ele **só cria as
seis tabelas novas** — nenhum `drop` de tabela da W1, nenhuma alteração em
`processamento`. Renomear para `0002_w2_pipeline.py` e ajustar `down_revision`
para a revisão da W1.

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_schema_compat.py::test_migrations_match_models`
Expected: PASS

- [x] **Step 7: Rodar a suíte inteira**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS, sem regressão da W1

- [x] **Step 8: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): tabelas da W2, iguais aos schemas do shared

As seis entidades saem de fias-ed-shared/schemas/entities/ literalmente — nomes,
tipos, enums, maxLength e nulidade —, porque o shared é o modelo lógico de dados
do projeto e o contrato com o Android. test_schema_compat.py passa a cobrir as
treze tabelas.

Falante tem role UNASSIGNED, que é como o shared resolve o segmento existir
antes de se saber quem falou; a FK do segmento continua NOT NULL.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Registro de modelos — SHA-256 e arquivos proibidos

**Files:**
- Create: `backend/app/ml/__init__.py`, `backend/app/ml/registry.py`
- Modify: `backend/app/core/config.py`, `fias-ed-web/.env.example`
- Test: `backend/tests/test_ml_registry.py`

**Interfaces:**
- Consumes: `fias-ed-shared/scientific-config/models.json` (campo `models[]` com `model_id`, `artifacts[].{role,relative_path,sha256,size_bytes}`, `forbidden_files`, `label_map`, `registry_version`).
- Produces:
  - `carregar_registro() -> dict` — o JSON inteiro, validado.
  - `entrada(model_id: str) -> dict` — a entrada de um modelo.
  - `verificar_artefatos(model_id: str, base: Path) -> None` — levanta `ModeloInvalido` se um SHA-256 divergir, um artefato faltar, ou um `forbidden_files` estiver presente.
  - `class ModeloInvalido(Exception)` com atributo `code: str`.

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_ml_registry.py`. Os casos usam arquivos temporários, nunca os pesos reais.

```python
import hashlib
import json
from pathlib import Path

import pytest

from app.ml.registry import ModeloInvalido, entrada, verificar_artefatos


def _escrever(caminho: Path, conteudo: bytes) -> str:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    return hashlib.sha256(conteudo).hexdigest()


@pytest.fixture()
def base_falsa(tmp_path, monkeypatch):  # noqa: PT004 - yield fixture com limpeza
    """Monta um diretório que casa com uma entrada de registro inventada."""
    conteudo = b"pesos-de-mentira"
    sha = _escrever(tmp_path / "m" / "model.safetensors", conteudo)
    registro = {
        "registry_version": "1.0.0",
        "models": [{
            "model_id": "teste", "task": "fias_utterance_classification",
            "artifacts": [{"role": "weights", "relative_path": "m/model.safetensors",
                           "sha256": sha, "size_bytes": len(conteudo)}],
            "forbidden_files": ["optimizer.pt"],
            "label_map": "fias_category = argmax(logits) + 1",
        }],
    }
    (tmp_path / "scientific-config").mkdir()
    (tmp_path / "scientific-config" / "models.json").write_text(json.dumps(registro), encoding="utf-8")
    # Aponta o Settings para este diretório e limpa os dois caches, senão um
    # teste herda o registro do anterior e passa por coincidência.
    get_settings.cache_clear()
    _ler.cache_clear()
    monkeypatch.setenv("SHARED_DIR", str(tmp_path))
    yield tmp_path
    get_settings.cache_clear()
    _ler.cache_clear()


def test_artefatos_integros_passam(base_falsa):
    verificar_artefatos("teste", base_falsa)  # não levanta


def test_sha256_divergente_recusa(base_falsa):
    (base_falsa / "m" / "model.safetensors").write_bytes(b"outra-coisa")
    with pytest.raises(ModeloInvalido) as exc:
        verificar_artefatos("teste", base_falsa)
    assert exc.value.code == "MODELO_SHA256_DIVERGENTE"


def test_artefato_ausente_recusa(base_falsa):
    (base_falsa / "m" / "model.safetensors").unlink()
    with pytest.raises(ModeloInvalido) as exc:
        verificar_artefatos("teste", base_falsa)
    assert exc.value.code == "MODELO_ARTEFATO_AUSENTE"


def test_arquivo_proibido_recusa(base_falsa):
    # §67: restos de treino não podem ser distribuídos junto com os pesos.
    (base_falsa / "m" / "optimizer.pt").write_bytes(b"x")
    with pytest.raises(ModeloInvalido) as exc:
        verificar_artefatos("teste", base_falsa)
    assert exc.value.code == "MODELO_ARQUIVO_PROIBIDO"


def test_entrada_desconhecida_recusa(base_falsa):
    with pytest.raises(ModeloInvalido) as exc:
        entrada("nao-existe")
    assert exc.value.code == "MODELO_NAO_REGISTRADO"
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_ml_registry.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.ml'`

- [ ] **Step 3: Implementar `app/ml/registry.py`**

```python
"""Lê o registro de modelos do fias-ed-shared e confere integridade (§66, §67).

A lista de hashes é do shared, não daqui: manter uma cópia local criaria duas
fontes de verdade que divergem em silêncio.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


class ModeloInvalido(Exception):
    def __init__(self, code: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.code = code


def _caminho_registro() -> Path:
    s = get_settings()
    return s.shared_dir / s.models_registry_rel


@lru_cache(maxsize=None)
def _ler(caminho: Path) -> dict:
    """Cacheado por caminho: um caminho diferente relê do disco. Cachear sem
    chave faria um teste herdar o registro de outro e passar por coincidência."""
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModeloInvalido("MODELO_REGISTRO_ILEGIVEL", f"registro ilegível: {caminho}") from exc


def carregar_registro() -> dict:
    return _ler(_caminho_registro())


def entrada(model_id: str) -> dict:
    for m in carregar_registro().get("models", []):
        if m.get("model_id") == model_id:
            return m
    raise ModeloInvalido("MODELO_NAO_REGISTRADO", f"modelo fora do registro: {model_id}")


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def verificar_artefatos(model_id: str, base: Path) -> None:
    m = entrada(model_id)
    for proibido in m.get("forbidden_files", []):
        if any(base.rglob(proibido)):
            raise ModeloInvalido("MODELO_ARQUIVO_PROIBIDO", f"arquivo proibido presente: {proibido}")
    for art in m.get("artifacts", []):
        caminho = base / art["relative_path"]
        if not caminho.is_file():
            raise ModeloInvalido("MODELO_ARTEFATO_AUSENTE", f"artefato ausente: {art['relative_path']}")
        if _sha256(caminho) != art["sha256"]:
            raise ModeloInvalido("MODELO_SHA256_DIVERGENTE", f"sha256 divergente: {art['relative_path']}")
```

Criar `backend/app/ml/__init__.py` vazio.

- [ ] **Step 4: Acrescentar a configuração**

Em `app/core/config.py`, dentro de `Settings`:

```python
    models_dir: str = "/models"
    # Derivado de shared_dir, que já é a resposta do projeto para "onde o shared
    # está montado". Duas bases independentes divergiriam no deploy.
    models_registry_rel: str = "scientific-config/models.json"
    asr_size: str = "small"
    asr_model_id: str = "faster-whisper-small"
    diar_model_id: str = "pyannote-speaker-diarization-3.1"
    clf_model_id: str = "fias-bertimbau-ptbr-frente3"
    usar_modelos_falsos: bool = False
```

Em `.env.example`. **Atenção ao nome das variáveis:** `Settings` não define
`env_prefix`, então pydantic-settings mapeia cada campo para a env var de mesmo
nome em maiúsculas, sem prefixo — é o padrão que `DEVICE_ID` e
`MAX_UPLOAD_BYTES` já seguem. Escrever `FIAS_ED_MODELS_DIR` faria a
configuração ser ignorada em silêncio.

```
# Diretório dos pesos (fora do Git). Populado por scripts/setup_models.py.
MODELS_DIR=/models
# Tamanho do modelo de ASR: tiny, base ou small (ver a tabela de medição no README).
ASR_SIZE=small
# Execução offline: nenhuma chamada de rede em tempo de execução.
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_ml_registry.py`
Expected: PASS (5 testes)

- [ ] **Step 6: Commit**

```bash
git add fias-ed-web/backend fias-ed-web/.env.example
git commit -m "feat(web): registro de modelos com conferência de SHA-256 e arquivos proibidos

Os hashes vêm de fias-ed-shared/scientific-config/models.json; manter cópia
local criaria duas fontes de verdade. Restos de treino (optimizer.pt e afins)
recusam a carga (§67).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---
### Task 3: Protocolos de ML e implementações falsas

Sem esta task nenhum job é testável sem GPU. Ela não carrega modelo nenhum.

**Files:**
- Create: `backend/app/ml/protocols.py`, `backend/app/ml/fakes.py`, `backend/app/ml/loader.py`
- Test: `backend/tests/test_ml_fakes.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) SegmentoASR(inicio_ms: int, fim_ms: int, texto: str)`
  - `@dataclass(frozen=True) TurnoDiar(inicio_ms: int, fim_ms: int, rotulo: str)`
  - `class ASR(Protocol)` com `transcrever(caminho: Path, deslocamento_ms: int) -> list[SegmentoASR]`
  - `class Diarizador(Protocol)` com `turnos(caminho: Path) -> list[TurnoDiar]`
  - `class Classificador(Protocol)` com `logits(pares: list[tuple[str, str]]) -> list[list[float]]`
  - `obter_asr()`, `obter_diarizador()`, `obter_classificador()` em `loader.py`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_ml_fakes.py`:

```python
from pathlib import Path

from app.ml.fakes import ASRFalso, ClassificadorFalso, DiarizadorFalso
from app.ml.protocols import SegmentoASR, TurnoDiar


def test_asr_falso_respeita_o_deslocamento():
    asr = ASRFalso([SegmentoASR(0, 1000, "olá"), SegmentoASR(1000, 2000, "turma")])
    saida = asr.transcrever(Path("qualquer.wav"), deslocamento_ms=60_000)
    assert [(s.inicio_ms, s.fim_ms) for s in saida] == [(60_000, 61_000), (61_000, 62_000)]
    assert [s.texto for s in saida] == ["olá", "turma"]


def test_diarizador_falso_devolve_os_turnos_configurados():
    turnos = [TurnoDiar(0, 5_000, "SPEAKER_00"), TurnoDiar(5_000, 9_000, "SPEAKER_01")]
    assert DiarizadorFalso(turnos).turnos(Path("x.wav")) == turnos


def test_classificador_falso_devolve_um_vetor_por_par():
    clf = ClassificadorFalso(categoria_fixa=4)
    saida = clf.logits([("a", "b"), ("c", "d")])
    assert len(saida) == 2
    assert all(len(v) == 10 for v in saida)
    # categoria 4 → índice 3, por causa do logit_index_offset = 1
    assert all(max(range(10), key=v.__getitem__) == 3 for v in saida)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_ml_fakes.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.ml.fakes'`

- [ ] **Step 3: Implementar `app/ml/protocols.py`**

```python
"""Interfaces finas dos três modelos.

Os jobs dependem destes protocolos, nunca de faster-whisper, pyannote ou
transformers diretamente. É o que permite a suíte rodar sem GPU e sem pesos.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SegmentoASR:
    inicio_ms: int
    fim_ms: int
    texto: str


@dataclass(frozen=True)
class TurnoDiar:
    inicio_ms: int
    fim_ms: int
    rotulo: str  # rótulo do diarizador; vive só em memória, nunca vai para o banco (§48)


class ASR(Protocol):
    def transcrever(self, caminho: Path, deslocamento_ms: int) -> list[SegmentoASR]:
        """Transcreve um chunk. Os tempos devolvidos já são globais."""


class Diarizador(Protocol):
    def turnos(self, caminho: Path) -> list[TurnoDiar]:
        """Turnos de fala do arquivo inteiro, agrupados por voz."""


class Classificador(Protocol):
    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        """Um vetor de 10 logits por par de turnos (text_a, text_b)."""
```

- [ ] **Step 4: Implementar `app/ml/fakes.py`**

```python
"""Implementações falsas, usadas só em teste. Nunca importadas em produção
fora do loader, que só as escolhe com usar_modelos_falsos = True.
"""
from dataclasses import replace
from pathlib import Path

from app.ml.protocols import SegmentoASR, TurnoDiar


class ASRFalso:
    def __init__(self, segmentos: list[SegmentoASR]) -> None:
        self._segmentos = segmentos

    def transcrever(self, caminho: Path, deslocamento_ms: int) -> list[SegmentoASR]:
        return [replace(s, inicio_ms=s.inicio_ms + deslocamento_ms, fim_ms=s.fim_ms + deslocamento_ms)
                for s in self._segmentos]


class DiarizadorFalso:
    def __init__(self, turnos: list[TurnoDiar]) -> None:
        self._turnos = turnos

    def turnos(self, caminho: Path) -> list[TurnoDiar]:
        return list(self._turnos)


class ClassificadorFalso:
    def __init__(self, categoria_fixa: int = 1) -> None:
        self._indice = categoria_fixa - 1  # logit_index_offset = 1

    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        vetor = [0.0] * 10
        vetor[self._indice] = 10.0
        return [list(vetor) for _ in pares]
```

- [ ] **Step 5: Implementar `app/ml/loader.py`**

Os construtores reais só são importados quando de fato usados, para a suíte não precisar de `torch` instalado.

```python
from app.core.config import get_settings
from app.ml.protocols import ASR, Classificador, Diarizador


def obter_asr() -> ASR:
    if get_settings().usar_modelos_falsos:
        from app.ml.fakes import ASRFalso
        return ASRFalso([])
    from app.ml.asr_whisper import WhisperASR
    return WhisperASR()


def obter_diarizador() -> Diarizador:
    if get_settings().usar_modelos_falsos:
        from app.ml.fakes import DiarizadorFalso
        return DiarizadorFalso([])
    from app.ml.diar_pyannote import PyannoteDiarizador
    return PyannoteDiarizador()


def obter_classificador() -> Classificador:
    if get_settings().usar_modelos_falsos:
        from app.ml.fakes import ClassificadorFalso
        return ClassificadorFalso()
    from app.ml.clf_bertimbau import BertimbauClassificador
    return BertimbauClassificador()
```

- [ ] **Step 6: Rodar o teste e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_ml_fakes.py`
Expected: PASS (3 testes)

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): protocolos dos três modelos e implementações falsas

Os jobs dependem dos protocolos, nunca de faster-whisper, pyannote ou
transformers diretamente. É o que permite a suíte inteira rodar sem GPU e sem
peso de modelo.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Preparo do áudio — cópia, normalização e plano de chunks

**Files:**
- Create: `backend/app/audio/prepare.py`
- Modify: `backend/app/jobs/handlers.py`
- Test: `backend/tests/test_audio_prepare.py`

**Interfaces:**
- Consumes: `abs_path`, `delete_file` de `app/audio/storage.py` (W1); `finish_job`, `fail_job` de `app/jobs/queue.py`.
- Produces:
  - `@dataclass(frozen=True) Chunk(indice: int, inicio_ms: int, duracao_ms: int, caminho: Path)`
  - `planejar_chunks(duracao_ms: int, janela_ms: int) -> list[tuple[int, int]]` — pares `(inicio_ms, duracao_ms)`
  - `normalizar(origem: Path, destino: Path) -> None` — 16 kHz, mono, PCM 16 bits
  - `cortar(origem: Path, plano: list[tuple[int, int]], dir_destino: Path) -> list[Chunk]`
  - `work_path(aula_id: uuid.UUID) -> Path` — caminho da cópia de trabalho
  - `chunks_dir(aula_id: uuid.UUID) -> Path` — diretório dos chunks
  - `limpar_chunks(dir_destino: Path) -> None` — apaga os chunks depois do uso
  - `audio_original(db, aula_id) -> Audio | None` — o áudio `is_original` da aula
  - `handle_prepare_audio(db, job)` em `handlers.py`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_audio_prepare.py`. O primeiro teste é o item 1 do Review Focus: **aula de 90 minutos com último chunk incompleto**.

```python
import pytest

from app.audio.prepare import planejar_chunks

JANELA = 600_000  # 10 min


def test_aula_de_90_minutos_cobre_tudo_sem_passar_do_fim():
    duracao = 90 * 60 * 1000
    plano = planejar_chunks(duracao, JANELA)
    assert plano[0][0] == 0
    # nenhum chunk começa depois do fim do arquivo
    assert all(inicio < duracao for inicio, _ in plano)
    # a soma cobre exatamente a duração, sem sobra e sem buraco
    assert sum(d for _, d in plano) == duracao
    # o último chunk termina exatamente no fim
    ultimo_inicio, ultima_duracao = plano[-1]
    assert ultimo_inicio + ultima_duracao == duracao


def test_ultimo_chunk_incompleto_tem_a_duracao_que_sobra():
    duracao = 65 * 60 * 1000  # 65 min = 6 janelas de 10 + 5 min
    plano = planejar_chunks(duracao, JANELA)
    assert len(plano) == 7
    assert plano[-1] == (60 * 60 * 1000, 5 * 60 * 1000)


def test_aula_menor_que_a_janela_vira_um_chunk_so():
    assert planejar_chunks(7 * 60 * 1000, JANELA) == [(0, 7 * 60 * 1000)]


def test_duracao_multipla_exata_nao_cria_chunk_vazio():
    plano = planejar_chunks(3 * JANELA, JANELA)
    assert len(plano) == 3
    assert all(d > 0 for _, d in plano)


def test_duracao_invalida_recusa():
    with pytest.raises(ValueError):
        planejar_chunks(0, JANELA)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_audio_prepare.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.audio.prepare'`

- [ ] **Step 3: Implementar `planejar_chunks`**

```python
"""Cópia de trabalho, normalização e corte em chunks.

O original nunca é tocado (§17). Os chunks existem só para o ASR; a diarização
recebe o arquivo normalizado inteiro, porque é na fronteira entre chunks que a
troca de falante se perde.
"""
import subprocess  # nosec B404 - lista de argumentos, sem shell (§57)
from dataclasses import dataclass
from pathlib import Path

JANELA_PADRAO_MS = 600_000


@dataclass(frozen=True)
class Chunk:
    indice: int
    inicio_ms: int
    duracao_ms: int
    caminho: Path


def planejar_chunks(duracao_ms: int, janela_ms: int = JANELA_PADRAO_MS) -> list[tuple[int, int]]:
    if duracao_ms <= 0:
        raise ValueError("duração precisa ser positiva")
    plano: list[tuple[int, int]] = []
    inicio = 0
    while inicio < duracao_ms:
        plano.append((inicio, min(janela_ms, duracao_ms - inicio)))
        inicio += janela_ms
    return plano
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_audio_prepare.py`
Expected: PASS (5 testes)

- [ ] **Step 5: Implementar `normalizar` e `cortar`**

No mesmo arquivo. `ffmpeg` sempre com lista de argumentos, seguindo o padrão de `app/audio/probe.py`.

```python
def _rodar(args: list[str]) -> None:
    subprocess.run(  # nosec B603 B607 - lista de argumentos, sem shell
        args, check=True, capture_output=True, timeout=3600)


def normalizar(origem: Path, destino: Path) -> None:
    """Cópia de trabalho em 16 kHz, mono, PCM 16 bits — o que os dois modelos esperam."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    _rodar(["ffmpeg", "-nostdin", "-y", "-i", str(origem),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destino)])


def cortar(origem: Path, plano: list[tuple[int, int]], dir_destino: Path) -> list[Chunk]:
    dir_destino.mkdir(parents=True, exist_ok=True)
    chunks: list[Chunk] = []
    for indice, (inicio_ms, duracao_ms) in enumerate(plano):
        caminho = dir_destino / f"chunk_{indice:04d}.wav"
        _rodar(["ffmpeg", "-nostdin", "-y", "-i", str(origem),
                "-ss", f"{inicio_ms / 1000:.3f}", "-t", f"{duracao_ms / 1000:.3f}",
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(caminho)])
        chunks.append(Chunk(indice, inicio_ms, duracao_ms, caminho))
    return chunks
```

- [ ] **Step 6: Escrever o teste do job e vê-lo falhar**

Acrescentar a `tests/test_audio_prepare.py`, usando o WAV sintético que `scripts/smoke.py` já sabe gerar:

```python
from app.jobs.handlers import HANDLERS


def test_prepare_audio_leva_a_preprocessing_e_nao_toca_o_original(db, aula_validada, wav_sintetico):
    original_antes = wav_sintetico.read_bytes()
    job = enqueue(db, aula_validada.id, "prepare_audio")
    HANDLERS["prepare_audio"](db, job)
    db.refresh(aula_validada)
    assert aula_validada.status == "TRANSCRIBING"
    assert wav_sintetico.read_bytes() == original_antes


def test_prepare_audio_de_audio_ilegivel_vira_erro_com_mensagem_humana(db, aula_com_audio_quebrado):
    job = enqueue(db, aula_com_audio_quebrado.id, "prepare_audio")
    HANDLERS["prepare_audio"](db, job)
    db.refresh(aula_com_audio_quebrado)
    assert aula_com_audio_quebrado.status == "ERROR"
    assert aula_com_audio_quebrado.error_code == "AUDIO_PREPARO_FALHOU"


def test_prepare_audio_nao_deixa_arquivo_de_trabalho_orfao_ao_falhar(db, aula_com_audio_quebrado):
    """fail_job é terminal. Um .wav parcial de 170 MB ficaria no disco para sempre."""
    job = enqueue(db, aula_com_audio_quebrado.id, "prepare_audio")
    HANDLERS["prepare_audio"](db, job)
    assert not work_path(aula_com_audio_quebrado.id).exists()


def test_cortar_produz_pedacos_com_a_duracao_planejada(tmp_path, wav_sintetico):
    """Mede a duração real de cada .wav com ffprobe, em vez de ecoar o plano de
    entrada: é a única forma de um erro em -ss/-t aparecer no teste."""
    from app.audio.probe import probe
    plano = [(0, 2_000), (2_000, 2_000), (4_000, 1_000)]
    chunks = cortar(wav_sintetico, plano, tmp_path)
    reais = [probe(c.caminho).duration_ms for c in chunks]
    for real, (_, planejado) in zip(reais, plano):
        assert abs(real - planejado) <= 50  # tolerância de um quadro
    assert abs(sum(reais) - sum(d for _, d in plano)) <= 50
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_audio_prepare.py`
Expected: FAIL com `KeyError: 'prepare_audio'`

- [ ] **Step 7: Implementar `handle_prepare_audio`**

Em `app/jobs/handlers.py`, seguindo o estilo de `handle_validate_audio`:

```python
def handle_prepare_audio(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    audio = audio_original(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or audio is None:
        finish_job(db, job)
        db.commit()
        return
    # O professor precisa ver "Preparando sua aula…" durante a normalização, que
    # numa aula de 90 min é o estágio mais demorado. Sem isto, PREPROCESSING não
    # é usado por ninguém e a tela fica parada no status anterior.
    aula.status = "PREPROCESSING"
    db.commit()
    trabalho = work_path(aula.id)
    try:
        normalizar(abs_path(audio.path), trabalho)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        # fail_job é terminal: não há retry. Uma saída parcial do ffmpeg ficaria
        # órfã para sempre — mais de 170 MB numa aula de 90 min. handle_validate_audio
        # já faz a limpeza equivalente no seu caminho de erro.
        trabalho.unlink(missing_ok=True)
        # fail_job já marca aula.status=ERROR e o error_code; não reatribuir.
        fail_job(db, job, "AUDIO_PREPARO_FALHOU")
        db.commit()
        log_event("audio_prepare_failed", aula_id=aula.id, job_id=job.id)
        return
    aula.status, aula.error_code = "TRANSCRIBING", None
    enqueue(db, aula.id, "transcribe")
    finish_job(db, job)
    db.commit()
    log_event("audio_prepared", aula_id=aula.id, job_id=job.id)


HANDLERS = {
    "validate_audio": handle_validate_audio,
    "prepare_audio": handle_prepare_audio,
}
```

Acrescentar `AUDIO_PREPARO_FALHOU` a `app/core/messages.py`:

```python
    "AUDIO_PREPARO_FALHOU": "Não conseguimos preparar este áudio para análise. Tente enviar o arquivo de novo.",
```

- [ ] **Step 8: Rodar os testes e confirmar que passam**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_audio_prepare.py`
Expected: PASS (7 testes)

- [ ] **Step 9: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): preparo do áudio — cópia de trabalho, normalização e plano de chunks

O original nunca é tocado; a cópia sai em 16 kHz mono PCM. O plano de chunks
cobre a duração exata, sem sobra e sem buraco: testado com 90 min e com último
chunk incompleto, que é onde um erro de deslocamento produziria segmentos com
horário além do fim do arquivo.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Job de transcrição

**Files:**
- Create: `backend/app/transcricao/__init__.py`, `backend/app/transcricao/service.py`
- Modify: `backend/app/jobs/handlers.py`
- Test: `backend/tests/test_job_transcribe.py`

> **Ordem de execução:** esta task roda **depois da Task 6**. `Segmento.text_pseudonymized`
> é `NOT NULL`, então `gravar_segmentos` já precisa de `pseudonimizar` na primeira
> gravação — escrever o texto cru nessa coluna "por enquanto" seria um vazamento
> silencioso se a Task 6 escorregasse.

**Interfaces:**
- Consumes: `Chunk`, `cortar`, `planejar_chunks` (Task 4); `obter_asr()` (Task 3); `SegmentoASR` (Task 3); `pseudonimizar` (Task 6).
- Produces:
  - `criar_transcricao(db, aula, audio, asr_model_id) -> Transcricao`
  - `falante_provisorio(db, transcricao) -> Falante` — cria a linha `role="UNASSIGNED"`,
    `diarization_label="pendente"`, à qual todos os segmentos são ligados até a diarização
  - `gravar_segmentos(db, transcricao, segmentos: list[SegmentoASR], falante: Falante) -> None`
  - `transcricao_da_aula(db, aula_id) -> Transcricao | None`
  - `segmentos_asr(db, transcricao) -> list[SegmentoASR]` — relê do banco no formato do protocolo
  - `texto_efetivo(segmento) -> str` — `texto_revisado` quando houver, senão `texto_original_asr`
  - `handle_transcribe(db, job)`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_job_transcribe.py`:

```python
from app.jobs.handlers import HANDLERS
from app.models import Segmento, Transcricao


def test_transcricao_soma_o_deslocamento_de_cada_chunk(db, aula_preparada, asr_falso_por_chunk):
    """Cada chunk devolve tempos locais; o que é gravado tem de ser global."""
    job = enqueue(db, aula_preparada.id, "transcribe")
    HANDLERS["transcribe"](db, job)
    t = db.query(Transcricao).filter_by(aula_id=aula_preparada.id).one()
    segmentos = db.query(Segmento).filter_by(transcricao_id=t.id).order_by(Segmento.ordem).all()
    assert [s.start_ms for s in segmentos] == [0, 1_000, 600_000, 601_000]
    assert all(s.end_ms <= duracao_do_audio(db, t) for s in segmentos)


def test_segmentos_nascem_ligados_a_um_falante_nao_atribuido(db, aula_preparada, asr_falso_por_chunk):
    """falante_id é NOT NULL; antes da diarização todos apontam para a mesma
    linha com role=UNASSIGNED."""
    job = enqueue(db, aula_preparada.id, "transcribe")
    HANDLERS["transcribe"](db, job)
    t = db.query(Transcricao).filter_by(aula_id=aula_preparada.id).one()
    segmentos = db.query(Segmento).filter_by(transcricao_id=t.id).all()
    assert all(s.falante_id is not None for s in segmentos)
    assert len({s.falante_id for s in segmentos}) == 1
    assert db.query(Falante).filter_by(transcricao_id=t.id).one().role == "UNASSIGNED"


def test_transcricao_leva_a_diarizing(db, aula_preparada, asr_falso_por_chunk):
    job = enqueue(db, aula_preparada.id, "transcribe")
    HANDLERS["transcribe"](db, job)
    db.refresh(aula_preparada)
    assert aula_preparada.status == "DIARIZING"


def test_audio_sem_fala_vira_erro_com_mensagem_humana(db, aula_preparada, asr_falso_vazio):
    job = enqueue(db, aula_preparada.id, "transcribe")
    HANDLERS["transcribe"](db, job)
    db.refresh(aula_preparada)
    assert aula_preparada.status == "ERROR"
    assert aula_preparada.error_code == "AUDIO_SEM_FALA"


def test_chunks_sao_apagados_ao_fim(db, aula_preparada, asr_falso_por_chunk, dir_chunks):
    job = enqueue(db, aula_preparada.id, "transcribe")
    HANDLERS["transcribe"](db, job)
    assert list(dir_chunks.glob("chunk_*.wav")) == []


def test_chunks_sao_apagados_quando_o_asr_levanta(db, aula_preparada, dir_chunks, monkeypatch):
    """A exceção sobe até o worker, que faz rollback e retry. Sem finally, os
    pedaços já cortados ficariam no disco — centenas de MB numa aula de 90 min."""
    class ASRQueFalha:
        def transcrever(self, caminho, deslocamento_ms):
            raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(handlers, "obter_asr", lambda: ASRQueFalha())
    job = enqueue(db, aula_preparada.id, "transcribe")
    with pytest.raises(RuntimeError):
        HANDLERS["transcribe"](db, job)
    assert list(dir_chunks.glob("chunk_*.wav")) == []
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_transcribe.py`
Expected: FAIL com `KeyError: 'transcribe'`

- [ ] **Step 3: Implementar `handle_transcribe`**

```python
def handle_transcribe(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    audio = audio_original(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or audio is None:
        finish_job(db, job)
        db.commit()
        return
    trabalho, dir_chunks = work_path(aula.id), chunks_dir(aula.id)
    # try/finally: se cortar() ou transcrever() levantar, a exceção sobe até o
    # worker, que faz rollback e retry — mas os pedaços já cortados ficariam no
    # disco para sempre. Numa aula de 90 min são centenas de MB por falha.
    try:
        plano = planejar_chunks(audio.duration_ms)
        chunks = cortar(trabalho, plano, dir_chunks)
        asr = obter_asr()
        segmentos: list[SegmentoASR] = []
        for chunk in chunks:
            segmentos.extend(asr.transcrever(chunk.caminho, chunk.inicio_ms))
    finally:
        limpar_chunks(dir_chunks)
    if not segmentos:
        # fail_job já marca aula.status=ERROR e o error_code; não reatribuir.
        fail_job(db, job, "AUDIO_SEM_FALA")
        db.commit()
        log_event("transcricao_sem_fala", aula_id=aula.id, job_id=job.id)
        return
    transcricao = criar_transcricao(db, aula, audio, get_settings().asr_model_id)
    # Segmento.falante_id é NOT NULL: o schema do shared resolve "ainda não se
    # sabe quem falou" com role=UNASSIGNED, não com FK nula. A diarização (Task 7)
    # troca este falante provisório pelos falantes por voz.
    gravar_segmentos(db, transcricao, segmentos, falante_provisorio(db, transcricao))
    aula.status, aula.error_code = "DIARIZING", None
    enqueue(db, aula.id, "diarize")
    finish_job(db, job)
    db.commit()
    log_event("transcricao_pronta", aula_id=aula.id, job_id=job.id, n_segmentos=len(segmentos))
```

Registrar em `HANDLERS` e acrescentar a mensagem em `app/core/messages.py`:

```python
    "AUDIO_SEM_FALA": "Não conseguimos identificar fala neste áudio. Confira se o arquivo é mesmo o da aula.",
```

Acrescentar `n_segmentos` a `ALLOWED_FIELDS` em `app/core/logging.py` (é contagem, não conteúdo).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_transcribe.py`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): job de transcrição com tempos globais

Cada chunk devolve tempos locais e o job soma o deslocamento antes de gravar,
de modo que nenhuma camada acima sabe que houve corte (§18). Áudio sem fala
reconhecível termina em ERROR com mensagem humana, não em transcrição vazia.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Pseudonimização de nomes próprios

Item 4 do Review Focus. Um falso negativo aqui vaza o nome de um estudante para a exportação.

**Files:**
- Create: `backend/app/pipeline/__init__.py`, `backend/app/pipeline/pseudonymize.py`
- Modify: `backend/app/transcricao/service.py`
- Test: `backend/tests/test_pseudonymize.py`

**Interfaces:**
- Produces:
  - `pseudonimizar(texto: str) -> str` — troca nomes próprios por `[NOME]`; união de NER e heurística
  - `nomes_por_ner(texto: str) -> set[str]` — spans marcados como pessoa pelo modelo
  - `nomes_por_heuristica(texto: str) -> set[str]` — a regra de maiúscula, mantida como rede

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_pseudonymize.py`. A regra é conservadora por decisão: na dúvida, pseudonimiza.

```python
import pytest

from app.pipeline.pseudonymize import pseudonimizar


@pytest.mark.parametrize("entrada,esperado", [
    ("Maria, responde pra gente", "[NOME], responde pra gente"),
    ("o João e a Ana conversaram", "o [NOME] e a [NOME] conversaram"),
    ("boa tarde, turma", "boa tarde, turma"),
])
def test_casos_diretos(entrada, esperado):
    assert pseudonimizar(entrada) == esperado


def test_primeira_palavra_da_frase_nao_e_nome_so_por_ser_maiuscula():
    # "Vamos" abre a frase; maiúscula ali não indica nome próprio.
    assert pseudonimizar("Vamos começar a aula") == "Vamos começar a aula"


@pytest.mark.parametrize("entrada", [
    "a Vitória veio ao quadro",
    "chama a Bela aqui",
    "fala, Paz",
])
def test_homonimo_de_substantivo_comum_e_pseudonimizado(entrada):
    """Review Focus 4: na dúvida, pseudonimiza. Um falso positivo troca uma
    palavra comum por [NOME] na versão exportada; um falso negativo vaza o nome
    de um estudante, que é o dano que o §48 existe para impedir."""
    assert "[NOME]" in pseudonimizar(entrada)


def test_nome_no_meio_de_frase_com_pontuacao():
    assert pseudonimizar("então, Pedro, o que você acha?") == "então, [NOME], o que você acha?"


def test_sigla_em_caixa_alta_nao_vira_nome():
    assert pseudonimizar("a prova do ENEM") == "a prova do ENEM"


def test_ner_pega_nome_que_a_heuristica_perde(monkeypatch):
    # Nome no começo da frase: a heurística se cala de propósito, o NER não.
    monkeypatch.setattr("app.pipeline.pseudonymize.nomes_por_ner", lambda t: {"Rafael"})
    assert pseudonimizar("Rafael, vem ao quadro") == "[NOME], vem ao quadro"


def test_sem_modelo_de_ner_a_heuristica_ainda_protege(monkeypatch):
    """O modelo pode faltar no diretório; isso não pode virar vazamento silencioso.

    Substitui o CARREGADOR, não `nomes_por_ner`: trocar a função pública prova
    um caminho vizinho ("se vier vazio, a heurística cobre"), não o caminho que
    a docstring promete ("se o modelo faltar, o carregador trata e não quebra").
    """
    monkeypatch.setattr("app.pipeline.pseudonymize._modelo", lambda: None)
    assert nomes_por_ner("chamei a Ana no quadro") == set()
    assert "[NOME]" in pseudonimizar("chamei a Ana no quadro")


def test_nome_que_e_prefixo_de_outra_palavra_nao_corta_a_palavra(monkeypatch):
    """A substituição final precisa de fronteira de palavra. Sem ela, um nome
    detectado que seja prefixo de outra palavra NÃO detectada corrompe o texto:
    "Anapolis" viraria "[NOME]polis".

    Os dois detectores são isolados de propósito. Com a heurística rodando de
    verdade ela marca "Anapolis" sozinha (maiúscula no meio da frase, a mesma
    regra que pega "Vitória" e "Paz") — o que é correto e conservador, mas faria
    o teste medir cobertura de detector em vez da propriedade de substituição,
    e passar com ou sem a fronteira.
    """
    monkeypatch.setattr("app.pipeline.pseudonymize.nomes_por_ner", lambda t: {"Ana"})
    monkeypatch.setattr("app.pipeline.pseudonymize.nomes_por_heuristica", lambda t: {"Ana"})
    assert pseudonimizar("Fomos ao Anapolis") == "Fomos ao Anapolis"


def test_texto_vazio():
    assert pseudonimizar("") == ""
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_pseudonymize.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.pipeline'`

- [ ] **Step 3: Implementar**

```python
"""Troca nomes próprios por [NOME] (PRIVACY.md, §48).

União de dois detectores: um NER local de português (CPU, dezenas de MB) e uma
heurística de maiúscula. Qualquer um dos dois que aponte, pseudonimiza — NER em
fala transcrita perde casos que a heurística pega, e vice-versa. O viés é
deliberadamente conservador: um falso positivo troca uma palavra comum por
[NOME] na versão exportada; um falso negativo vaza o nome de um estudante.
"""
import re

MARCADOR = "[NOME]"

# Palavras que começam com maiúscula por razão gramatical, não por serem nome.
NAO_SAO_NOMES = {
    "A", "As", "O", "Os", "Um", "Uma", "Ele", "Ela", "Eles", "Elas", "Eu", "Nós", "Você", "Vocês",
    "Vamos", "Vem", "Vai", "Então", "Mas", "Quando", "Quem", "Que", "Qual", "Como", "Onde", "Por",
    "Bom", "Boa", "Olha", "Agora", "Hoje", "Ontem", "Amanhã", "Sim", "Não", "Certo", "Pronto",
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
    "Outubro", "Novembro", "Dezembro",
}

_PALAVRA = re.compile(r"\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+)\b")


def nomes_por_ner(texto: str) -> set[str]:
    """Spans marcados como pessoa pelo modelo. Carregado uma vez, em CPU."""
    nlp = _modelo()
    if nlp is None:  # modelo ausente: a heurística sozinha ainda protege
        return set()
    return {ent.text for ent in nlp(texto).ents if ent.label_ in ("PER", "PERSON")}


def pseudonimizar(texto: str) -> str:
    if not texto:
        return texto
    for nome in sorted(nomes_por_ner(texto), key=len, reverse=True):
        texto = texto.replace(nome, MARCADOR)

    def troca(m: re.Match) -> str:
        palavra = m.group(1)
        if palavra in NAO_SAO_NOMES:
            return palavra
        # Primeira palavra da frase: maiúscula é regra de escrita, não indício de nome.
        anterior = texto[: m.start()].rstrip()
        if not anterior or anterior.endswith((".", "!", "?")):
            return palavra
        return MARCADOR

    return _PALAVRA.sub(troca, texto)
```

Siglas em caixa alta não casam com `_PALAVRA` (que exige minúsculas depois da primeira letra), então passam intactas.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_pseudonymize.py`
Expected: PASS (11 testes)

> A verificação de ponta a ponta — um segmento nascer pseudonimizado ao fim do job
> de transcrição — pertence à Task 5, que é executada depois desta.

- [ ] **Step 6: Excluir a aula passa a apagar transcrição e segmentos**

O `PRIVACY.md` exige exclusão real (remoção física, não `soft delete`) para o
material sensível, e a W2 cria dois tipos novos: transcrição e segmentos.

Teste, em `tests/test_revisao.py`:

```python
def test_excluir_aula_apaga_transcricao_e_segmentos(cliente, db, aula_com_transcricao):
    aula_id = aula_com_transcricao.id
    r = cliente.delete(f"/api/aulas/{aula_id}")
    assert r.status_code == 204
    assert db.query(Transcricao).filter_by(aula_id=aula_id).count() == 0
    assert segmentos_da_aula(db, aula_id) == []


def test_excluir_conta_apaga_transcricoes_das_aulas(cliente_admin, db, professor_com_aula_transcrita):
    cliente_admin.request("DELETE", f"/api/admin/contas/{professor_com_aula_transcrita.id}",
                          json={"confirmar_username": professor_com_aula_transcrita.username})
    assert db.query(Transcricao).count() == 0
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_revisao.py`
Expected: FAIL — a exclusão da W1 não conhece as tabelas novas

Estender `soft_delete_aula` em `app/aulas/service.py` respeitando a fronteira que
o `PRIVACY.md` define: **exclusão física é para áudio e transcrição**; as demais
entidades usam `deleted_at`, "preservando o histórico necessário à
reprodutibilidade científica".

- **Apagar fisicamente:** `Transcricao`, `Segmento`, `Falante` e
  `ClassificacaoFIAS` — as três primeiras são a transcrição, e a quarta vai junto
  por necessidade estrutural (`segmento_id` é NOT NULL).
- **Soft delete:** `IndicadorFIAS`, que é índice agregado sem texto e sem nome,
  ao lado de `Processamento`, que já seguia essa regra.

Apagar na ordem das chaves estrangeiras, e devolver os caminhos de arquivo como
já faz. `delete_conta` em `app/admin/routes.py` já chama `soft_delete_aula` por
aula, então herda o comportamento.

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_revisao.py tests/test_aulas.py`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): pseudonimização de nomes próprios e exclusão real da transcrição

PRIVACY.md já promete Segmento.text_pseudonymized com nomes trocados por
[NOME]; isto implementa. Heurística conservadora e sem modelo: na dúvida,
pseudonimiza, porque um falso negativo vaza o nome de um estudante e um falso
positivo só troca uma palavra comum na versão exportada.

Excluir uma aula passa a apagar transcrição e segmentos de verdade, não por
soft delete, como o PRIVACY.md já exige para áudio.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---
### Task 7: Alinhamento ASR × diarização e job de diarização

Item 2 do Review Focus. O alinhamento é função pura e é onde a lógica mais erra.

**Files:**
- Create: `backend/app/pipeline/align.py`
- Modify: `backend/app/jobs/handlers.py`
- Test: `backend/tests/test_align.py`, `backend/tests/test_job_diarize.py`

**Interfaces:**
- Consumes: `SegmentoASR`, `TurnoDiar` (Task 3).
- Produces:
  - `alinhar(segmentos: list[SegmentoASR], turnos: list[TurnoDiar]) -> list[str | None]` — um rótulo de voz por segmento, na mesma ordem; `None` quando não há sobreposição alguma.
  - `resumo_por_voz(segmentos, rotulos) -> list[GrupoDeVoz]`
  - `@dataclass(frozen=True) GrupoDeVoz(rotulo: str, tempo_total_ms: int, n_segmentos: int, amostras: list[tuple[int, int]])`
  - `criar_falantes_provisorios(db, transcricao, linhas: list[Segmento], rotulos: list[str | None]) -> None` —
    cria um `Falante` por voz com `role="UNASSIGNED"` e o `diarization_label` do
    diarizador, **repointa cada segmento** para o falante da sua voz, e apaga o
    falante provisório `"pendente"` que a Task 5 criou. Segmento sem rótulo
    (nenhuma sobreposição com turno algum) fica no provisório, que por isso só é
    apagado quando ficar sem segmentos.

    **Recebe as linhas do banco, não refaz a consulta.** Casar duas consultas
    independentes por posição — ambas `ORDER BY start_ms`, sem chave de
    desempate — deixa dois trechos com `start_ms` idêntico trocarem de voz em
    silêncio. Uma consulta só, e a mesma lista percorre o alinhamento e o
    repontamento.
  - `handle_diarize(db, job)`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_align.py`:

```python
from app.ml.protocols import SegmentoASR, TurnoDiar
from app.pipeline.align import alinhar, resumo_por_voz


def test_segmento_inteiramente_dentro_de_um_turno():
    segs = [SegmentoASR(1_000, 2_000, "olá")]
    turnos = [TurnoDiar(0, 5_000, "A")]
    assert alinhar(segs, turnos) == ["A"]


def test_segmento_que_cruza_a_fronteira_fica_com_a_maior_sobreposicao():
    """Review Focus 2: alguém interrompe no meio da frase. O segmento não pode
    ser descartado nem empatar — fica com quem falou mais tempo dentro dele."""
    segs = [SegmentoASR(4_000, 6_000, "espera aí")]
    turnos = [TurnoDiar(0, 4_500, "A"), TurnoDiar(4_500, 9_000, "B")]
    # 500 ms em A, 1500 ms em B
    assert alinhar(segs, turnos) == ["B"]


def test_empate_exato_escolhe_o_turno_que_comeca_antes():
    segs = [SegmentoASR(4_000, 6_000, "meio a meio")]
    turnos = [TurnoDiar(0, 5_000, "A"), TurnoDiar(5_000, 9_000, "B")]
    assert alinhar(segs, turnos) == ["A"]


def test_segmento_sem_sobreposicao_nenhuma_fica_sem_rotulo():
    segs = [SegmentoASR(10_000, 11_000, "eco")]
    turnos = [TurnoDiar(0, 5_000, "A")]
    assert alinhar(segs, turnos) == [None]


def test_sem_turnos_todos_ficam_sem_rotulo():
    segs = [SegmentoASR(0, 1_000, "x"), SegmentoASR(1_000, 2_000, "y")]
    assert alinhar(segs, []) == [None, None]


def test_resumo_agrega_tempo_e_contagem_por_voz():
    segs = [SegmentoASR(0, 2_000, "a"), SegmentoASR(2_000, 3_000, "b"), SegmentoASR(3_000, 9_000, "c")]
    grupos = resumo_por_voz(segs, ["A", "B", "A"])
    por_rotulo = {g.rotulo: g for g in grupos}
    assert por_rotulo["A"].tempo_total_ms == 8_000
    assert por_rotulo["A"].n_segmentos == 2
    assert por_rotulo["B"].tempo_total_ms == 1_000
    # ordenado do que mais falou para o que menos falou
    assert [g.rotulo for g in grupos] == ["A", "B"]


def test_segmento_que_contem_o_turno_inteiro():
    """O inverso do caso anterior: turno curto dentro de um trecho longo. A
    sobreposição é a duração do turno."""
    segs = [SegmentoASR(0, 10_000, "fala longa")]
    turnos = [TurnoDiar(3_000, 4_000, "A")]
    assert alinhar(segs, turnos) == ["A"]


def test_segmentos_com_start_ms_identico_nao_trocam_de_voz(db, aula_transcrita):
    """Dois trechos começando no mesmo milissegundo. Se o repontamento casar por
    posição entre consultas independentes, um recebe a voz do outro."""
    linhas = segmentos_ordenados(db, transcricao_da(db, aula_transcrita))
    linhas[0].start_ms = linhas[1].start_ms = 5_000
    db.commit()
    rotulos = ["A", "B"] + [None] * (len(linhas) - 2)
    criar_falantes_provisorios(db, transcricao_da(db, aula_transcrita), linhas, rotulos)
    db.refresh(linhas[0]); db.refresh(linhas[1])
    rotulo_de = {f.id: f.diarization_label for f in falantes_da(db, aula_transcrita)}
    assert rotulo_de[linhas[0].falante_id] == "A"
    assert rotulo_de[linhas[1].falante_id] == "B"


def test_resumo_traz_no_maximo_tres_amostras_por_voz():
    segs = [SegmentoASR(i * 1_000, i * 1_000 + 900, "x") for i in range(10)]
    grupos = resumo_por_voz(segs, ["A"] * 10)
    assert len(grupos[0].amostras) == 3
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_align.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.pipeline.align'`

- [ ] **Step 3: Implementar `app/pipeline/align.py`**

```python
"""Cruza os segmentos do ASR com os turnos do diarizador.

Função pura: não toca banco nem modelo. É aqui que mora a decisão de o que
fazer quando um segmento cruza a fronteira de dois turnos, que é o caso comum
de alguém interromper o professor no meio da frase.
"""
from dataclasses import dataclass

from app.ml.protocols import SegmentoASR, TurnoDiar

MAX_AMOSTRAS = 3


@dataclass(frozen=True)
class GrupoDeVoz:
    rotulo: str
    tempo_total_ms: int
    n_segmentos: int
    amostras: list[tuple[int, int]]


def _sobreposicao(a_ini: int, a_fim: int, b_ini: int, b_fim: int) -> int:
    return max(0, min(a_fim, b_fim) - max(a_ini, b_ini))


def alinhar(segmentos: list[SegmentoASR], turnos: list[TurnoDiar]) -> list[str | None]:
    rotulos: list[str | None] = []
    for seg in segmentos:
        melhor, melhor_ms = None, 0
        for turno in turnos:  # ordem de entrada decide o empate: quem começa antes vence
            ms = _sobreposicao(seg.inicio_ms, seg.fim_ms, turno.inicio_ms, turno.fim_ms)
            if ms > melhor_ms:
                melhor, melhor_ms = turno.rotulo, ms
        rotulos.append(melhor)
    return rotulos


def resumo_por_voz(segmentos: list[SegmentoASR], rotulos: list[str | None]) -> list[GrupoDeVoz]:
    acumulado: dict[str, dict] = {}
    for seg, rotulo in zip(segmentos, rotulos):
        if rotulo is None:
            continue
        item = acumulado.setdefault(rotulo, {"ms": 0, "n": 0, "amostras": []})
        item["ms"] += seg.fim_ms - seg.inicio_ms
        item["n"] += 1
        if len(item["amostras"]) < MAX_AMOSTRAS:
            item["amostras"].append((seg.inicio_ms, seg.fim_ms))
    grupos = [GrupoDeVoz(r, v["ms"], v["n"], v["amostras"]) for r, v in acumulado.items()]
    return sorted(grupos, key=lambda g: g.tempo_total_ms, reverse=True)
```

Os turnos chegam ordenados por tempo de início, então o empate cai naturalmente
no que começa antes — que é o que o teste fixa.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_align.py`
Expected: PASS (7 testes)

- [ ] **Step 5: Escrever o teste do job e vê-lo falhar**

`backend/tests/test_job_diarize.py`:

```python
from app.jobs.handlers import HANDLERS
from app.models import Falante


def test_diarize_leva_a_escolha_de_voz(db, aula_transcrita, diarizador_falso_duas_vozes):
    job = enqueue(db, aula_transcrita.id, "diarize")
    HANDLERS["diarize"](db, job)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"


def test_diarize_nao_grava_agrupamento_de_voz_no_banco(db, aula_transcrita, diarizador_falso_duas_vozes):
    """§48: os rótulos do diarizador vivem só em memória e no payload da tela."""
    job = enqueue(db, aula_transcrita.id, "diarize")
    HANDLERS["diarize"](db, job)
    falantes = db.query(Falante).join(Transcricao).filter(Transcricao.aula_id == aula_transcrita.id).all()
    assert {f.role for f in falantes} <= {"PROFESSOR", "ALUNO", "UNASSIGNED"}


def test_uma_voz_so_nao_e_erro(db, aula_transcrita, diarizador_falso_uma_voz):
    job = enqueue(db, aula_transcrita.id, "diarize")
    HANDLERS["diarize"](db, job)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"


def test_falha_da_diarizacao_vira_erro_com_mensagem_humana(db, aula_transcrita, diarizador_que_falha):
    job = enqueue(db, aula_transcrita.id, "diarize")
    HANDLERS["diarize"](db, job)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "ERROR"
    assert aula_transcrita.error_code == "DIARIZACAO_FALHOU"
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_diarize.py`
Expected: FAIL com `KeyError: 'diarize'`

- [ ] **Step 6: Implementar `handle_diarize`**

O resultado do alinhamento é guardado em `Falante` com `role="UNASSIGNED"` para a tela de escolha consumir, e é apagado quando a escolha é feita. A tabela `job` da W1 não tem coluna de resultado e não ganha uma.

```python
def handle_diarize(db: Session, job: Job) -> None:
    aula = db.get(Aula, job.aula_id)
    transcricao = transcricao_da_aula(db, job.aula_id) if aula is not None else None
    if aula is None or aula.deleted_at is not None or transcricao is None:
        finish_job(db, job)
        db.commit()
        return
    try:
        turnos = obter_diarizador().turnos(work_path(aula.id))
    except Exception:  # noqa: BLE001 - qualquer falha do modelo vira erro de produto
        # fail_job já marca aula.status=ERROR e o error_code; não reatribuir.
        fail_job(db, job, "DIARIZACAO_FALHOU")
        db.commit()
        log_event("diarizacao_falhou", aula_id=aula.id, job_id=job.id)
        return
    # Uma consulta só: as mesmas linhas alimentam o alinhamento e o repontamento.
    linhas = segmentos_ordenados(db, transcricao)
    rotulos = alinhar([para_protocolo(l) for l in linhas], turnos)
    criar_falantes_provisorios(db, transcricao, linhas, rotulos)
    aula.status, aula.error_code = "READY_FOR_SPEAKER_REVIEW", None
    finish_job(db, job)
    db.commit()
    log_event("diarizacao_pronta", aula_id=aula.id, job_id=job.id, n_vozes=len(set(filter(None, rotulos))))
```

Mensagem em `app/core/messages.py`:

```python
    "DIARIZACAO_FALHOU": "Não conseguimos separar as vozes deste áudio. Tente enviar uma gravação com menos ruído.",
```

- [ ] **Step 7: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_diarize.py tests/test_align.py`
Expected: PASS (11 testes)

- [ ] **Step 8: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): alinhamento ASR x diarização e job de diarização

O alinhamento é função pura e decide por maior sobreposição, com empate para o
turno que começa antes — o caso de alguém interromper no meio da frase tem
comportamento definido, não acaso. Os rótulos do diarizador não chegam ao
banco: Falante guarda papel (§48).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: "Qual destas vozes é você?" — API e tela

**Files:**
- Create: `backend/app/transcricao/routes.py`, `frontend/src/pages/EscolhaVoz.tsx`
- Modify: `backend/app/main.py`, `frontend/src/app/App.tsx`, `frontend/src/api/types.ts`, `frontend/src/design/components.css`
- Test: `backend/tests/test_escolha_voz.py`, `frontend/src/pages/EscolhaVoz.test.tsx`

**Interfaces:**
- Consumes: `GrupoDeVoz`, `resumo_por_voz` (Task 7).
- Produces:
  - `GET /api/aulas/{id}/vozes` → `{"vozes": [{"rotulo": "voz-1", "tempo_total_ms": 0, "n_segmentos": 0, "amostras": [{"inicio_ms": 0, "fim_ms": 0}]}]}`
  - `POST /api/aulas/{id}/vozes/escolher` com `{"rotulo": "voz-1"}` → detalhe da aula
  - `GET /api/aulas/{id}/audio?inicio_ms=&fim_ms=` — trecho para ouvir
  - `vozes_da_aula(db, aula) -> list[GrupoDeVoz]` — lê os rótulos provisórios e resume
  - `atribuir_papeis(db, aula, rotulo: str) -> None` — cria os dois `Falante`, liga cada segmento
    ao papel certo e apaga os rótulos provisórios; levanta `VozDesconhecida`

- [ ] **Step 1: Escrever o teste de backend que falha**

`backend/tests/test_escolha_voz.py`:

```python
def test_vozes_sao_numeradas_e_nunca_chamadas_de_aluno(cliente, aula_diarizada):
    r = cliente.get(f"/api/aulas/{aula_diarizada.id}/vozes")
    assert r.status_code == 200
    rotulos = [v["rotulo"] for v in r.json()["vozes"]]
    assert rotulos == ["voz-1", "voz-2"]
    assert not any("aluno" in x.lower() or "speaker" in x.lower() for x in rotulos)


def test_escolher_voz_atribui_o_resto_a_aluno(cliente, db, aula_diarizada):
    r = cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    assert r.status_code == 200
    papeis = [s.falante.role for s in segmentos_da(db, aula_diarizada)]
    assert set(papeis) == {"PROFESSOR", "ALUNO"}


def test_escolher_voz_apaga_os_rotulos_do_diarizador(cliente, db, aula_diarizada):
    """§48: o agrupamento por voz existe só entre a diarização e a escolha.
    Depois disso não pode sobrar nada dele no banco."""
    cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    papeis = {f.role for f in falantes_da(db, aula_diarizada)}
    assert papeis == {"PROFESSOR", "ALUNO"}
    assert "UNASSIGNED" not in papeis


def test_escolher_voz_leva_a_revisao_da_transcricao(cliente, db, aula_diarizada):
    cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    db.refresh(aula_diarizada)
    assert aula_diarizada.status == "READY_FOR_TRANSCRIPT_REVIEW"


def test_rotulo_inexistente_recusa(cliente, aula_diarizada):
    r = cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-99"})
    assert r.status_code == 422
    assert r.json()["error_code"] == "VOZ_INVALIDA"


def test_aula_de_outro_professor_da_404(cliente_outro_professor, aula_diarizada):
    r = cliente_outro_professor.get(f"/api/aulas/{aula_diarizada.id}/vozes")
    assert r.status_code == 404
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_escolha_voz.py`
Expected: FAIL com 404 em todas as rotas

- [ ] **Step 2: Implementar as rotas**

`app/transcricao/routes.py`, seguindo o estilo de `app/aulas/routes.py`. O rótulo interno do diarizador (`SPEAKER_00`) nunca vaza para a API: a rota numera as vozes por ordem de tempo falado.

```python
class EscolhaIn(BaseModel):
    rotulo: str


@router.get("/aulas/{aula_id}/vozes")
def listar_vozes(aula_id: uuid.UUID, actor: Actor = Depends(current_actor),
                 db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    grupos = vozes_da_aula(db, aula)
    return {"vozes": [{"rotulo": f"voz-{i + 1}", "tempo_total_ms": g.tempo_total_ms,
                       "n_segmentos": g.n_segmentos,
                       "amostras": [{"inicio_ms": a, "fim_ms": b} for a, b in g.amostras]}
                      for i, g in enumerate(grupos)]}


@router.post("/aulas/{aula_id}/vozes/escolher")
def escolher_voz(aula_id: uuid.UUID, body: EscolhaIn, actor: Actor = Depends(current_actor),
                 db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if aula.status != "READY_FOR_SPEAKER_REVIEW":
        raise AppError(409, "AULA_STATE", "Esta aula não está esperando a escolha da voz.")
    try:
        atribuir_papeis(db, aula, body.rotulo)
    except VozDesconhecida:
        raise AppError(422, "VOZ_INVALIDA", "Escolha uma das vozes da lista.") from None
    aula.status = "READY_FOR_TRANSCRIPT_REVIEW"
    audit(db, actor, "aula", aula.id, "update")
    db.commit()
    log_event("voz_escolhida", aula_id=aula.id)
    return aula_payload(db, aula)
```

`atribuir_papeis` cria dois `Falante` (PROFESSOR e ALUNO), liga cada segmento ao
papel certo e **apaga os rótulos provisórios** do diarizador.

- [ ] **Step 3: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_escolha_voz.py`
Expected: PASS (5 testes)

- [ ] **Step 4: Escrever o teste de frontend que falha**

`frontend/src/pages/EscolhaVoz.test.tsx`:

```tsx
test("lista as vozes com tempo e quantidade de momentos", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...AULA, status: "READY_FOR_SPEAKER_REVIEW" }),
    "GET /api/aulas/a1/vozes": () => jsonResponse({ vozes: [
      { rotulo: "voz-1", tempo_total_ms: 1_680_000, n_segmentos: 142, amostras: [{ inicio_ms: 0, fim_ms: 4000 }] },
      { rotulo: "voz-2", tempo_total_ms: 420_000, n_segmentos: 58, amostras: [] },
    ] }),
  });
  renderApp("/aulas/a1/vozes");
  expect(await screen.findByText("Voz 1")).toBeInTheDocument();
  expect(screen.getByText(/28 min de fala/)).toBeInTheDocument();
  expect(screen.getByText(/142 momentos/)).toBeInTheDocument();
});

test("a tela nunca chama as vozes de aluno", async () => {
  // O vocabulário importa: rotular como "Aluno 2" antes de o professor escolher
  // inventa uma identidade que o produto promete não criar (§48).
  mockApi({ /* como acima */ });
  renderApp("/aulas/a1/vozes");
  await screen.findByText("Voz 1");
  expect(screen.queryByText(/aluno/i)).not.toBeInTheDocument();
});

test("escolher uma voz manda o rótulo e navega para a revisão", async () => {
  const spy = mockApi({ /* como acima */, "POST /api/aulas/a1/vozes/escolher": () => jsonResponse(AULA) });
  renderApp("/aulas/a1/vozes");
  await userEvent.click(await screen.findByRole("button", { name: /esta voz é a minha/i }));
  const post = spy.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(post![1]!.body))).toEqual({ rotulo: "voz-1" });
});
```

Run: `cd frontend && npx vitest run src/pages/EscolhaVoz.test.tsx`
Expected: FAIL — a rota não existe

- [ ] **Step 5: Implementar a tela**

`frontend/src/pages/EscolhaVoz.tsx`. Lista com divisória de 1px, não grade de cards (`DESIGN.md`). Cada voz tem um `<audio>` por amostra, com nome acessível.

```tsx
export function EscolhaVoz() {
  const { id } = useParams();
  const [vozes, setVozes] = useState<Voz[] | null>(null);
  // … carrega de /vozes
  return (
    <>
      <h1>Qual destas vozes é você?</h1>
      <p>Ouça os trechos e aponte qual voz é a sua. As outras vozes da aula ficam como ALUNO.</p>
      <ul className="list">
        {vozes?.map((v, i) => (
          <li key={v.rotulo} className="list__item">
            <div>
              <h2>Voz {i + 1}</h2>
              <p className="meta">{formatDuration(v.tempo_total_ms)} de fala · {v.n_segmentos} momentos</p>
              {v.amostras.map((a) => (
                <audio key={a.inicio_ms} controls preload="none"
                  aria-label={`Trecho da voz ${i + 1} em ${formatTimestamp(a.inicio_ms)}`}
                  src={`/api/aulas/${id}/audio?inicio_ms=${a.inicio_ms}&fim_ms=${a.fim_ms}`} />
              ))}
            </div>
            <Button onClick={() => void escolher(v.rotulo)}>Esta voz é a minha</Button>
          </li>
        ))}
      </ul>
    </>
  );
}
```

Registrar a rota `/aulas/:id/vozes` em `App.tsx` e mandar a página da aula levar
para lá quando o status for `READY_FOR_SPEAKER_REVIEW`.

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd frontend && npm test && npm run lint`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend fias-ed-web/frontend
git commit -m "feat(web): tela 'qual destas vozes é você?'

As vozes são numeradas (Voz 1, Voz 2) e nunca chamadas de aluno: rotular antes
de o professor escolher inventaria uma identidade que o produto promete não
criar. Depois da escolha, o resto vira ALUNO e os rótulos do diarizador somem.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: API da revisão da transcrição

Itens 3 e 5 do Review Focus.

**Files:**
- Modify: `backend/app/transcricao/routes.py`, `backend/app/transcricao/service.py`
- Test: `backend/tests/test_revisao.py`

**Interfaces:**
- Produces:
  - `GET /api/aulas/{id}/transcricao?bloco=N` → `{"bloco": N, "blocos": M, "segmentos": [...]}`, blocos de 5 min
  - `PATCH /api/segmentos/{id}` com `{"texto": "...", "papel": "PROFESSOR"|"ALUNO", "version": N}` → segmento atualizado
  - `POST /api/aulas/{id}/transcricao/concluir` → detalhe da aula, status `READY_FOR_FIAS`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_revisao.py`:

```python
def test_transcricao_vem_paginada_em_blocos_de_cinco_minutos(cliente, aula_com_transcricao_longa):
    r = cliente.get(f"/api/aulas/{aula_com_transcricao_longa.id}/transcricao?bloco=0")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["bloco"] == 0
    assert corpo["blocos"] == 10  # 50 min
    assert all(s["start_ms"] < 300_000 for s in corpo["segmentos"])


def test_editar_texto_regrava_a_versao_pseudonimizada(cliente, db, segmento_qualquer):
    r = cliente.patch(f"/api/segmentos/{segmento_qualquer.id}",
                      json={"texto": "a Maria respondeu", "version": segmento_qualquer.version})
    assert r.status_code == 200
    db.refresh(segmento_qualquer)
    assert segmento_qualquer.texto_revisado == "a Maria respondeu"
    assert "Maria" not in segmento_qualquer.text_pseudonymized
    assert "[NOME]" in segmento_qualquer.text_pseudonymized


def test_texto_com_caracteres_especiais_volta_literal(cliente, segmento_qualquer):
    """Review Focus 3: o texto vai para a tela e, na W3, para o relatório."""
    texto = 'ele disse "3 < 5" e riu 😄'
    r = cliente.patch(f"/api/segmentos/{segmento_qualquer.id}",
                      json={"texto": texto, "version": segmento_qualquer.version})
    assert r.status_code == 200
    assert r.json()["texto"] == texto


def test_segunda_aba_nao_sobrescreve_a_primeira_em_silencio(cliente, segmento_qualquer):
    """Review Focus 5: duas abas editando o mesmo segmento."""
    versao = segmento_qualquer.version
    primeira = cliente.patch(f"/api/segmentos/{segmento_qualquer.id}",
                             json={"texto": "primeira", "version": versao})
    assert primeira.status_code == 200
    segunda = cliente.patch(f"/api/segmentos/{segmento_qualquer.id}",
                            json={"texto": "segunda", "version": versao})
    assert segunda.status_code == 409
    assert segunda.json()["error_code"] == "SEGMENTO_DESATUALIZADO"


def test_trocar_papel_de_um_segmento(cliente, db, segmento_qualquer):
    r = cliente.patch(f"/api/segmentos/{segmento_qualquer.id}",
                      json={"papel": "ALUNO", "version": segmento_qualquer.version})
    assert r.status_code == 200
    db.refresh(segmento_qualquer)
    assert segmento_qualquer.falante.role == "ALUNO"


def test_concluir_a_revisao_leva_a_ready_for_fias(cliente, db, aula_em_revisao):
    r = cliente.post(f"/api/aulas/{aula_em_revisao.id}/transcricao/concluir")
    assert r.status_code == 200
    db.refresh(aula_em_revisao)
    assert aula_em_revisao.status == "READY_FOR_FIAS"


def test_segmento_de_outro_professor_da_404(cliente_outro_professor, segmento_qualquer):
    r = cliente_outro_professor.patch(f"/api/segmentos/{segmento_qualquer.id}",
                                      json={"texto": "x", "version": 1})
    assert r.status_code == 404
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_revisao.py`
Expected: FAIL com 404

- [ ] **Step 2: Implementar as rotas**

`version` vem da coluna que o `EntityMixin` da W1 já traz. O `PATCH` compara e
incrementa numa só instrução, para duas abas simultâneas não passarem as duas.

```python
BLOCO_MS = 300_000


class SegmentoPatch(BaseModel):
    texto: str | None = Field(default=None, max_length=4000)
    papel: Literal["PROFESSOR", "ALUNO"] | None = None
    version: int


@router.patch("/segmentos/{segmento_id}")
def editar_segmento(segmento_id: uuid.UUID, body: SegmentoPatch,
                    actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    seg = segmento_do_professor(db, actor, segmento_id)  # 404 se não for dele
    if seg.version != body.version:
        raise AppError(409, "SEGMENTO_DESATUALIZADO",
                       "Este trecho foi alterado em outra aba. Recarregue para ver a versão atual.")
    if body.texto is not None:
        seg.texto_revisado = body.texto
        seg.text_pseudonymized = pseudonimizar(body.texto)
        seg.origem = "REVISADO"
    if body.papel is not None:
        seg.falante_id = falante_do_papel(db, seg, body.papel).id
    seg.version += 1
    audit(db, actor, "segmento", seg.id, "update")
    db.commit()
    return segmento_payload(seg)
```

Mensagem em `app/core/messages.py` para `SEGMENTO_DESATUALIZADO`.

- [ ] **Step 3: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_revisao.py`
Expected: PASS (7 testes)

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): API da revisão da transcrição, com salvamento por segmento

Bloco de cinco minutos por requisição e PATCH por segmento com version
otimista: duas abas editando o mesmo trecho recebem 409 em vez de a segunda
sobrescrever a primeira em silêncio. Editar o texto regrava a versão
pseudonimizada, para uma correção não reintroduzir um nome em claro.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Tela de revisão da transcrição

A maior tela da fatia.

**Files:**
- Create: `frontend/src/pages/RevisaoTranscricao.tsx`
- Modify: `frontend/src/app/App.tsx`, `frontend/src/api/types.ts`, `frontend/src/design/components.css`
- Test: `frontend/src/pages/RevisaoTranscricao.test.tsx`

**Interfaces:**
- Consumes: as três rotas da Task 9.

- [ ] **Step 1: Escrever o teste que falha**

`frontend/src/pages/RevisaoTranscricao.test.tsx`:

```tsx
test("mostra os segmentos do bloco com horário, falante e texto", async () => {
  mockApi({ /* me, aula, transcricao bloco 0 */ });
  renderApp("/aulas/a1/transcricao");
  expect(await screen.findByDisplayValue("bom dia, turma")).toBeInTheDocument();
  expect(screen.getByText("00:00")).toBeInTheDocument();
});

test("salva ao sair do campo, não a cada tecla", async () => {
  const spy = mockApi({ /* … */ });
  renderApp("/aulas/a1/transcricao");
  const campo = await screen.findByDisplayValue("bom dia, turma");
  await userEvent.clear(campo);
  await userEvent.type(campo, "bom dia, pessoal");
  expect(spy.mock.calls.filter(([, i]) => i?.method === "PATCH")).toHaveLength(0);
  await userEvent.tab();
  await waitFor(() => expect(spy.mock.calls.filter(([, i]) => i?.method === "PATCH")).toHaveLength(1));
});

test("conflito de versão mostra aviso e não perde o que o professor digitou", async () => {
  mockApi({ /* PATCH → 409 SEGMENTO_DESATUALIZADO */ });
  renderApp("/aulas/a1/transcricao");
  const campo = await screen.findByDisplayValue("bom dia, turma");
  await userEvent.clear(campo);
  await userEvent.type(campo, "texto novo");
  await userEvent.tab();
  expect(await screen.findByRole("alert")).toHaveTextContent(/alterado em outra aba/i);
  expect(screen.getByDisplayValue("texto novo")).toBeInTheDocument();
});

test("trocar o falante de um segmento", async () => {
  const spy = mockApi({ /* … */ });
  renderApp("/aulas/a1/transcricao");
  await userEvent.click(await screen.findByRole("button", { name: /marcar como aluno/i }));
  const patch = spy.mock.calls.find(([, i]) => i?.method === "PATCH");
  expect(JSON.parse(String(patch![1]!.body))).toMatchObject({ papel: "ALUNO" });
});

test("navega entre blocos de cinco minutos", async () => {
  mockApi({ /* blocos: 10 */ });
  renderApp("/aulas/a1/transcricao");
  await userEvent.click(await screen.findByRole("button", { name: /próximos 5 minutos/i }));
  expect(await screen.findByText(/bloco 2 de 10/i)).toBeInTheDocument();
});

test("dá para seguir sem revisar nada", async () => {
  const spy = mockApi({ /* … */ });
  renderApp("/aulas/a1/transcricao");
  await userEvent.click(await screen.findByRole("button", { name: /está bom assim/i }));
  expect(spy.mock.calls.some(([u, i]) => String(u).endsWith("/concluir") && i?.method === "POST")).toBe(true);
});

test("cada segmento é um grupo rotulado com o horário", async () => {
  mockApi({ /* … */ });
  renderApp("/aulas/a1/transcricao");
  expect(await screen.findByRole("group", { name: /trecho de 00:00/i })).toBeInTheDocument();
});
```

Run: `cd frontend && npx vitest run src/pages/RevisaoTranscricao.test.tsx`
Expected: FAIL — a rota não existe

- [ ] **Step 2: Implementar a tela**

Estrutura: um `<section>` por segmento, com `role="group"` e `aria-label` com o
horário; alternância de falante como botão de dois estados com texto; `onBlur`
dispara o `PATCH`; falha de versão mostra `Banner` e mantém o texto digitado.

```tsx
function SegmentoLinha({ seg, onSalvo }: { seg: Segmento; onSalvo: (s: Segmento) => void }) {
  const [texto, setTexto] = useState(seg.texto);
  const [erro, setErro] = useState<string | null>(null);
  async function salvar(campos: Partial<{ texto: string; papel: Papel }>) {
    setErro(null);
    try {
      onSalvo(await api<Segmento>(`/segmentos/${seg.id}`, {
        method: "PATCH", json: { ...campos, version: seg.version },
      }));
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível salvar este trecho.");
    }
  }
  return (
    <section className="segmento" role="group" aria-label={`Trecho de ${formatTimestamp(seg.inicio_ms)}`}>
      <p className="meta">{formatTimestamp(seg.inicio_ms)}</p>
      <Button variant="secondary" onClick={() => void salvar({ papel: seg.papel === "PROFESSOR" ? "ALUNO" : "PROFESSOR" })}>
        {seg.papel === "PROFESSOR" ? "Você — marcar como ALUNO" : "ALUNO — marcar como você"}
      </Button>
      <TextAreaField label={`Texto do trecho de ${formatTimestamp(seg.inicio_ms)}`} value={texto}
        onChange={(e) => setTexto(e.target.value)} onBlur={() => texto !== seg.texto && void salvar({ texto })} />
      {erro && <Banner kind="error">{erro}</Banner>}
    </section>
  );
}
```

O rótulo do `TextAreaField` é visível só para leitor de tela (`visually-hidden`),
porque o horário já aparece ao lado — mas existe, como a `DESIGN.md` exige.

- [ ] **Step 3: Rodar e confirmar que passa**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/frontend
git commit -m "feat(web): tela de revisão da transcrição

Salva ao sair do campo, um segmento por vez, em blocos de cinco minutos — um
formulário único de 50 minutos se perderia inteiro se o navegador fechasse no
meio. Conflito de versão mostra aviso e mantém o que o professor digitou.
Cada trecho é um grupo rotulado pelo horário, para leitor de tela.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---
### Task 11: Adaptador do BERTimbau

**Files:**
- Create: `backend/app/ml/clf_bertimbau.py`
- Test: `backend/tests/test_clf_bertimbau.py`

**Interfaces:**
- Consumes: `verificar_artefatos`, `entrada` (Task 2); `Classificador` (Task 3).
- Produces:
  - `class BertimbauClassificador` implementando `Classificador`
  - `categoria_de(logits: list[float], offset: int) -> int`
  - `montar_pares(textos: list[str]) -> list[tuple[str, str]]` — o turno anterior e o atual

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_clf_bertimbau.py`. Os dois primeiros testes são restrições globais, não detalhes: eles reprovam se alguém voltar a confiar no checkpoint.

```python
from pathlib import Path

import pytest

from app.ml.clf_bertimbau import categoria_de, montar_pares


def test_categoria_usa_o_offset_do_fias_rules():
    # logit_index_offset = 1 → índice 0 é a categoria 1
    logits = [9.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert categoria_de(logits, offset=1) == 1
    logits = [0.0] * 10
    logits[6] = 9.0
    assert categoria_de(logits, offset=1) == 7


def test_nenhum_codigo_le_id2label_do_checkpoint():
    """ANALISE_MODELOS_EXISTENTES §2.2: o config.json grava só LABEL_0..LABEL_9.
    Um mapa trocado não falha visivelmente — produz uma aula inteira
    classificada errado com aparência normal."""
    fonte = Path("app/ml/clf_bertimbau.py").read_text(encoding="utf-8")
    assert "id2label" not in fonte
    assert "label2id" not in fonte


def test_pares_usam_o_turno_anterior_como_contexto():
    # ANALISE_MODELOS_EXISTENTES §2.4: entrada = par (text_a, text_b)
    assert montar_pares(["um", "dois", "três"]) == [("", "um"), ("um", "dois"), ("dois", "três")]


def test_pares_de_lista_vazia():
    assert montar_pares([]) == []


def test_offset_invalido_recusa():
    with pytest.raises(ValueError):
        categoria_de([0.0] * 10, offset=0)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_clf_bertimbau.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.ml.clf_bertimbau'`

- [ ] **Step 3: Implementar**

```python
"""BERTimbau atrás do protocolo Classificador.

O mapa índice→categoria NÃO sai do checkpoint: o config.json grava só
LABEL_0..LABEL_9 (ANALISE_MODELOS_EXISTENTES §2.2). A categoria vem do
logit_index_offset declarado em fias_rules.json.
"""
from pathlib import Path

from app.core.config import get_settings
from app.ml.registry import entrada, verificar_artefatos

MAX_LENGTH = 256


def categoria_de(logits: list[float], offset: int) -> int:
    if offset < 1:
        raise ValueError("logit_index_offset precisa ser >= 1")
    return max(range(len(logits)), key=logits.__getitem__) + offset


def montar_pares(textos: list[str]) -> list[tuple[str, str]]:
    """Par de turnos: o anterior como contexto, o atual como alvo."""
    return [("" if i == 0 else textos[i - 1], t) for i, t in enumerate(textos)]


class BertimbauClassificador:
    def __init__(self) -> None:
        s = get_settings()
        base = Path(s.models_dir)
        verificar_artefatos(s.clf_model_id, base)
        art = {a["role"]: a["relative_path"] for a in entrada(s.clf_model_id)["artifacts"]}
        diretorio = (base / art["weights"]).parent
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self._tok = AutoTokenizer.from_pretrained(diretorio, local_files_only=True)
        self._modelo = AutoModelForSequenceClassification.from_pretrained(diretorio, local_files_only=True)
        self._modelo.eval()

    def logits(self, pares: list[tuple[str, str]]) -> list[list[float]]:
        if not pares:
            return []
        import torch
        a, b = [p[0] for p in pares], [p[1] for p in pares]
        entradas = self._tok(a, b, padding="max_length", truncation="longest_first",
                             max_length=MAX_LENGTH, return_tensors="pt")
        with torch.no_grad():
            saida = self._modelo(**entradas).logits
        return saida.tolist()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_clf_bertimbau.py`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): adaptador do BERTimbau com o mapa de categorias do shared

A categoria sai do logit_index_offset do fias_rules.json, nunca do id2label do
checkpoint, que o ANALISE_MODELOS_EXISTENTES registra como não confiável — um
mapa trocado classificaria a aula inteira errado com aparência normal. Há teste
que reprova se o código voltar a ler id2label.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Job de classificação FIAS

**Files:**
- Create: `backend/app/fias/__init__.py`, `backend/app/fias/service.py`
- Modify: `backend/app/jobs/handlers.py`
- Test: `backend/tests/test_job_fias.py`

**Interfaces:**
- Consumes: `fias_ed_engine` (`constrain_by_role`, `segments_to_intervals`, `transition_matrix`, `compute_indices`, `load_rules`); `obter_classificador()`, `categoria_de`, `montar_pares`.
- Produces:
  - `classificar_aula(db, aula) -> None`
  - `handle_classify_fias(db, job)`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_job_fias.py`:

```python
from app.jobs.handlers import HANDLERS
from app.models import ClassificacaoFIAS, IndicadorFIAS


def test_classificacao_grava_uma_linha_por_segmento(db, aula_revisada, classificador_falso):
    job = enqueue(db, aula_revisada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    n_segmentos = contar_segmentos(db, aula_revisada)
    assert db.query(ClassificacaoFIAS).filter_by(aula_id=aula_revisada.id).count() == n_segmentos


def test_indices_sao_gravados_com_evidencia_e_rules_version(db, aula_revisada, classificador_falso):
    job = enqueue(db, aula_revisada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    indicadores = db.query(IndicadorFIAS).filter_by(aula_id=aula_revisada.id).all()
    assert indicadores
    # A evidência do shared é estruturada, não um JSONB livre.
    assert all(i.numerator_count is not None for i in indicadores)
    assert all(i.denominator_count is not None for i in indicadores)
    assert all(i.n_intervals > 0 for i in indicadores)
    assert all(i.validation_status for i in indicadores)
    assert all(i.rules_version for i in indicadores)


def test_classificacao_leva_a_fias_completed(db, aula_revisada, classificador_falso):
    job = enqueue(db, aula_revisada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    db.refresh(aula_revisada)
    assert aula_revisada.status == "FIAS_COMPLETED"


def test_a_categoria_respeita_o_papel_do_falante(db, aula_revisada, classificador_falso_categoria_8):
    """constrain_by_role é do motor do shared: uma categoria de fala docente num
    segmento de ALUNO tem de ser corrigida antes de virar intervalo."""
    job = enqueue(db, aula_revisada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    de_aluno = classificacoes_de_papel(db, aula_revisada, "ALUNO")
    assert all(c.categoria in (8, 9) for c in de_aluno)


def test_reclassificar_apaga_o_resultado_anterior(db, aula_classificada, classificador_falso):
    antes = db.query(ClassificacaoFIAS).filter_by(aula_id=aula_classificada.id).count()
    job = enqueue(db, aula_classificada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    depois = db.query(ClassificacaoFIAS).filter_by(aula_id=aula_classificada.id).count()
    assert depois == antes  # não duplicou
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_fias.py`
Expected: FAIL com `KeyError: 'classify_fias'`

- [ ] **Step 3: Implementar `app/fias/service.py`**

Nenhuma conta é feita aqui: tudo vem do motor do shared.

```python
"""Orquestra a classificação e chama o motor do shared.

Nenhuma regra do FIAS é implementada aqui. O Web produz (segmento, logits,
papel) e o fias_ed_engine decide.
"""
from fias_ed_engine.classifier import constrain_by_role
from fias_ed_engine.indices import compute_indices
from fias_ed_engine.intervals import segments_to_intervals, transition_matrix
from fias_ed_engine.rules import load_rules


def classificar_aula(db, aula) -> None:
    regras = load_rules("fias_rules")
    offset = regras["classifier"]["logit_index_offset"]
    segmentos = segmentos_ordenados(db, aula)
    # texto_efetivo, NUNCA texto_original_asr: usar o texto bruto aqui desfaria
    # em silêncio a revisão que o professor fez na Task 10. `segmentos_asr` do
    # service devolve o bruto de propósito (a diarização não usa texto) — não é
    # a função a chamar aqui.
    lotes = obter_classificador().logits(montar_pares([texto_efetivo(s) for s in segmentos]))

    apagar_resultado_anterior(db, aula)
    codificados = []
    for seg, logits in zip(segmentos, lotes):
        predicao = constrain_by_role(logits, seg.falante.role, regras)
        categoria = categoria_de(predicao.logits, offset)
        db.add(ClassificacaoFIAS(aula_id=aula.id, segmento_id=seg.id, categoria=categoria,
                                 confianca=predicao.confidence, modelo_ia_id=modelo_id(db),
                                 rules_version=regras["rules_version"]))
        codificados.append(CodedSegment(start_ms=seg.start_ms, end_ms=seg.end_ms, category=categoria))

    intervalos = segments_to_intervals(codificados, total_ms=duracao(db, aula), rules=regras)
    matriz = transition_matrix(intervalos, regras)
    indices = compute_indices(intervalos, regras, n_segments=len(codificados))
    gravar_indicadores(db, aula, indices, matriz, regras["rules_version"])
```

E `handle_classify_fias` em `handlers.py`, no mesmo estilo dos outros, levando a
aula a `FIAS_COMPLETED` e registrando `log_event("fias_pronto", aula_id=…)`.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_fias.py`
Expected: PASS (5 testes)

- [ ] **Step 5: Gravar o `Processamento` que torna a classificação reproduzível**

O spec §5.4 e o critério 9 exigem que, dada uma aula, se saiba com qual modelo,
com quais parâmetros e sob qual versão de regras ela foi analisada. Sem isso um
relatório de hoje não é reproduzível amanhã (§44).

Teste, em `tests/test_job_fias.py`:

```python
def test_processamento_registra_modelo_parametros_e_versoes(db, aula_revisada, classificador_falso):
    """Os nomes de coluna são os da tabela criada na W1 (app/models.py), não
    inventados aqui: asr_model, asr_model_hash, diarization_model, fias_model,
    fias_model_hash, parameters."""
    job = enqueue(db, aula_revisada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    proc = db.query(Processamento).filter_by(aula_id=aula_revisada.id).one()
    assert proc.asr_model and proc.asr_model_hash
    assert proc.diarization_model
    assert proc.fias_model and proc.fias_model_hash
    assert proc.app_version and proc.rules_version
    assert proc.parameters["asr"]["temperature"] == 0.0
    assert proc.parameters["asr"]["language"] == "pt"


def test_processamento_preenche_todas_as_colunas_obrigatorias(db, aula_revisada, classificador_falso):
    """A tabela da W1 tem seis colunas NOT NULL que não são de modelo; nenhuma
    pode ficar de fora, ou o INSERT falha em produção e não no teste."""
    job = enqueue(db, aula_revisada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    proc = db.query(Processamento).filter_by(aula_id=aula_revisada.id).one()
    assert proc.hardware and proc.device
    assert proc.audio_duration_ms > 0
    assert proc.transcript_source in ("ASR_ORIGINAL", "TRANSCRICAO_REVISADA")
    assert proc.stage_times_ms
    assert proc.status == "FIAS_COMPLETED"


def test_modelo_ia_nasce_do_registro_do_shared(db, aula_revisada, classificador_falso):
    job = enqueue(db, aula_revisada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    m = db.query(ModeloIA).filter_by(task="fias_utterance_classification").one()
    do_registro = entrada(get_settings().clf_model_id)
    assert m.model_id == do_registro["model_id"]
    assert m.registry_version == carregar_registro()["registry_version"]
    # o SHA-256 vem do registro, não de uma lista local
    assert m.sha256 == next(a["sha256"] for a in do_registro["artifacts"] if a["role"] == "weights")


def test_reprocessar_nao_duplica_o_processamento(db, aula_classificada, classificador_falso):
    job = enqueue(db, aula_classificada.id, "classify_fias")
    HANDLERS["classify_fias"](db, job)
    assert db.query(Processamento).filter_by(aula_id=aula_classificada.id).count() == 1
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_fias.py`
Expected: FAIL — `Processamento` ainda nasce vazio (a W1 criou a tabela e deixou os campos para a W2)

Implementar `registrar_processamento(db, aula)` em `app/fias/service.py`, que
grava (ou atualiza, se já existir) a linha usando **os nomes de coluna que a W1
criou**: `asr_model`, `asr_model_hash`, `diarization_model`, `fias_model`,
`fias_model_hash`, `parameters` (JSONB com o que de fato foi usado: `language`,
`temperature`, `max_length`, tamanho do modelo), `app_version` de
`app/__init__.py`, `rules_version` das regras carregadas, e também as seis
colunas obrigatórias restantes: `hardware` e `device` (de `platform` e da
presença de CUDA), `audio_duration_ms` (do `Audio`), `transcript_source`
(`TRANSCRICAO_REVISADA` se algum segmento tem `texto_revisado`, senão
`ASR_ORIGINAL`), `stage_times_ms` e `status`. Os `ModeloIA` são
criados a partir de `entrada(model_id)` do registro do shared — nunca de uma
lista local de hashes.

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_job_fias.py`
Expected: PASS (8 testes)

- [ ] **Step 6: Rodar a suíte inteira**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend
git commit -m "feat(web): job de classificação FIAS com processamento rastreável

O Web produz (segmento, logits, papel) e o fias_ed_engine decide: nenhuma
regra do FIAS é implementada aqui, e a matemática não é retestada porque já
passa nos vetores de conformance do shared. Reclassificar apaga o resultado
anterior, para evidência e resultado não ficarem fora de sincronia.

Cada aula analisada grava um Processamento com modelo, parâmetros, app_version
e rules_version, e os ModeloIA saem do registro do shared — um relatório de
hoje precisa ser reproduzível amanhã (§44).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Padrões de interação — API e tela

**Files:**
- Create: `backend/app/fias/routes.py`, `frontend/src/pages/PadroesInteracao.tsx`, `frontend/src/design/components/FaixaDeTempo.tsx`
- Modify: `backend/app/main.py`, `frontend/src/app/App.tsx`, `frontend/src/api/types.ts`, `frontend/src/design/components.css`
- Test: `backend/tests/test_padroes.py`, `frontend/src/pages/PadroesInteracao.test.tsx`

**Interfaces:**
- Produces: `GET /api/aulas/{id}/padroes` →
  `{"faixa": [{"inicio_ms": 0, "fim_ms": 3000, "grupo": "direta"}], "observacoes": [{"texto": "...", "evidencias": [{"segmento_id": "...", "inicio_ms": 0, "trecho": "..."}]}], "matriz": [[0]*10]*10, "indices": [{"codigo": "ID", "nome": "Razão I/D", "valor": 0.62, "descricao": "..."}]}`

- [ ] **Step 1: Escrever o teste de backend que falha**

```python
def test_padroes_traz_faixa_matriz_e_indices(cliente, aula_classificada):
    r = cliente.get(f"/api/aulas/{aula_classificada.id}/padroes")
    assert r.status_code == 200
    corpo = r.json()
    assert len(corpo["matriz"]) == 10 and all(len(l) == 10 for l in corpo["matriz"])
    assert corpo["indices"]
    assert corpo["faixa"]


def test_cada_observacao_vem_com_evidencia(cliente, aula_classificada):
    corpo = cliente.get(f"/api/aulas/{aula_classificada.id}/padroes").json()
    assert all(o["evidencias"] for o in corpo["observacoes"])


def test_nenhum_indice_vem_com_limiar_de_bom_ou_ruim(cliente, aula_classificada):
    """spec §8.4: os limiares estão PENDING_SCIENTIFIC_VALIDATION; mostrar um
    número contra meta não validada inventa um veredito."""
    corpo = cliente.get(f"/api/aulas/{aula_classificada.id}/padroes").json()
    for i in corpo["indices"]:
        assert set(i) == {"codigo", "nome", "valor", "descricao"}
        assert not any(p in i["descricao"].lower() for p in ("bom", "ruim", "ideal", "abaixo do esperado"))


def test_aula_ainda_nao_classificada_da_409(cliente, aula_em_revisao):
    r = cliente.get(f"/api/aulas/{aula_em_revisao.id}/padroes")
    assert r.status_code == 409
```

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_padroes.py`
Expected: FAIL com 404

- [ ] **Step 2: Implementar a rota**

Lê `ClassificacaoFIAS` e `IndicadorFIAS`, monta a faixa a partir dos intervalos
agrupados por `fias_groups` do `tokens.json` (indireta, direta, estudante,
silêncio), e usa `select_evidence_segments` do motor para as evidências.

- [ ] **Step 3: Rodar e confirmar que passa**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_padroes.py`
Expected: PASS (4 testes)

- [ ] **Step 4: Escrever o teste de frontend que falha**

```tsx
test("a tela abre pela faixa de tempo e pelas observações", async () => {
  mockApi({ /* … */ });
  renderApp("/aulas/a1/padroes");
  const titulos = await screen.findAllByRole("heading", { level: 2 });
  expect(titulos[0]).toHaveTextContent(/como a aula se distribuiu/i);
});

test("cada observação mostra o trecho que a sustenta", async () => {
  mockApi({ /* observacoes com evidencias */ });
  renderApp("/aulas/a1/padroes");
  expect(await screen.findByText(/o que vocês acham disso/i)).toBeInTheDocument();
});

test("a matriz aparece como tabela, com cabeçalho de linha e de coluna", async () => {
  mockApi({ /* … */ });
  renderApp("/aulas/a1/padroes");
  const tabela = await screen.findByRole("table", { name: /matriz de transições/i });
  expect(within(tabela).getAllByRole("columnheader")).toHaveLength(11);
});

test("nenhum índice aparece com veredito", async () => {
  mockApi({ /* … */ });
  renderApp("/aulas/a1/padroes");
  await screen.findByRole("table", { name: /matriz de transições/i });
  expect(screen.queryByText(/abaixo do esperado|bom|ruim|meta/i)).not.toBeInTheDocument();
});

test("a faixa de tempo tem alternativa textual", async () => {
  // Cor não pode ser o único portador de significado (DESIGN.md).
  mockApi({ /* … */ });
  renderApp("/aulas/a1/padroes");
  expect(await screen.findByRole("img", { name: /distribuição da fala ao longo da aula/i })).toBeInTheDocument();
});
```

Run: `cd frontend && npx vitest run src/pages/PadroesInteracao.test.tsx`
Expected: FAIL

- [ ] **Step 5: Implementar a tela e a faixa**

`FaixaDeTempo.tsx` desenha as barras com as quatro cores de `fias_groups`
(`--color-fias-indirect`, `--color-fias-direct`, `--color-fias-student`,
`--color-fias-silence`), com `role="img"` e `aria-label` descrevendo a
distribuição em palavras. A matriz é `<table className="table">` com
`<caption>`. Os índices vêm em lista, com nome por extenso e o que cada um mede
— nunca ao lado de um limiar.

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add fias-ed-web/backend fias-ed-web/frontend
git commit -m "feat(web): tela de padrões de interação

Abre pela faixa de tempo e pelas observações ancoradas em trechos reais; a
matriz vem depois, como tabela de números e não mapa de calor, porque um
heatmap exigiria tons intermediários fora da paleta fechada. Nenhum índice
aparece ao lado de limiar de bom ou ruim: os limiares estão
PENDING_SCIENTIFIC_VALIDATION e um veredito ali seria inventado.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Modelos reais e script de setup

Primeira task que precisa de peso de modelo. Tudo que veio antes roda sem GPU.

**Files:**
- Create: `backend/app/ml/asr_whisper.py`, `backend/app/ml/diar_pyannote.py`, `fias-ed-web/scripts/setup_models.py`
- Modify: `backend/pyproject.toml`, `docker-compose.yml`, `fias-ed-web/README.md`, `fias-ed-shared/scientific-config/models.json`
- Test: `backend/tests/test_modelos_reais.py` (marcado `lento`)

**Interfaces:**
- Produces: `class WhisperASR`, `class PyannoteDiarizador`, ambos implementando os protocolos da Task 3.

- [ ] **Step 1: Acrescentar as dependências e o volume**

`backend/pyproject.toml`: `faster-whisper`, `pyannote.audio`, `transformers`, `torch`.
`docker-compose.yml`: volume `models:/models` em `api` e `worker`, mais
`HF_HUB_OFFLINE=1` e `TRANSFORMERS_OFFLINE=1` no ambiente dos dois.

- [ ] **Step 2: Escrever o teste lento que falha**

`backend/tests/test_modelos_reais.py`:

```python
import pytest

pytestmark = pytest.mark.lento


def test_whisper_transcreve_o_wav_sintetico(wav_sintetico):
    from app.ml.asr_whisper import WhisperASR
    segmentos = WhisperASR().transcrever(wav_sintetico, deslocamento_ms=0)
    assert isinstance(segmentos, list)
    assert all(s.fim_ms >= s.inicio_ms for s in segmentos)


def test_whisper_e_deterministico(wav_sintetico):
    """§44: a mesma aula reprocessada tem de dar o mesmo texto."""
    from app.ml.asr_whisper import WhisperASR
    a = WhisperASR().transcrever(wav_sintetico, 0)
    b = WhisperASR().transcrever(wav_sintetico, 0)
    assert [s.texto for s in a] == [s.texto for s in b]


def test_deslocamento_e_somado(wav_sintetico):
    from app.ml.asr_whisper import WhisperASR
    base = WhisperASR().transcrever(wav_sintetico, 0)
    deslocado = WhisperASR().transcrever(wav_sintetico, 60_000)
    if base:
        assert deslocado[0].inicio_ms == base[0].inicio_ms + 60_000
```

Registrar o marcador em `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["lento: usa modelo real; fora da suíte padrão"]
addopts = "-m 'not lento'"
```

Run: `docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q -m lento`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.ml.asr_whisper'`

- [ ] **Step 3: Implementar `asr_whisper.py`**

```python
from pathlib import Path

from app.core.config import get_settings
from app.ml.protocols import SegmentoASR


class WhisperASR:
    def __init__(self) -> None:
        from faster_whisper import WhisperModel
        s = get_settings()
        self._modelo = WhisperModel(s.asr_size, device="auto", compute_type="int8",
                                    download_root=s.models_dir, local_files_only=True)

    def transcrever(self, caminho: Path, deslocamento_ms: int) -> list[SegmentoASR]:
        # language fixo e temperature 0: o §44 exige reprodutibilidade.
        segmentos, _ = self._modelo.transcribe(str(caminho), language="pt", temperature=0.0,
                                               vad_filter=True)
        return [SegmentoASR(int(s.start * 1000) + deslocamento_ms,
                            int(s.end * 1000) + deslocamento_ms,
                            s.text.strip())
                for s in segmentos if s.text.strip()]
```

- [ ] **Step 4: Implementar `diar_pyannote.py`**

```python
from pathlib import Path

from app.core.config import get_settings
from app.ml.protocols import TurnoDiar


class PyannoteDiarizador:
    def __init__(self) -> None:
        from pyannote.audio import Pipeline
        s = get_settings()
        self._pipeline = Pipeline.from_pretrained(f"{s.models_dir}/pyannote/config.yaml")

    def turnos(self, caminho: Path) -> list[TurnoDiar]:
        # Sem num_speakers: numa sala não se sabe quantas vozes vão aparecer.
        anotacao = self._pipeline(str(caminho))
        turnos = [TurnoDiar(int(seg.start * 1000), int(seg.end * 1000), rotulo)
                  for seg, _, rotulo in anotacao.itertracks(yield_label=True)]
        return sorted(turnos, key=lambda t: t.inicio_ms)
```

- [ ] **Step 5: Escrever `scripts/setup_models.py`**

Script de stdlib + `huggingface_hub`, rodado uma vez na instalação. Baixa o
`pyannote` com o token do ambiente, copia os artefatos do BERTimbau dos
experimentos, e **confere tudo contra o registro** antes de declarar sucesso:

```python
"""Popula o diretório de modelos e confere a integridade.

Roda uma vez, na instalação. Precisa de rede e do token do Hugging Face; o
produto em execução nunca faz isso.
"""
...
def main() -> int:
    base = Path(os.environ["FIAS_ED_MODELS_DIR"])
    baixar_pyannote(base, os.environ["HUGGINGFACE_TOKEN"])
    copiar_bertimbau(base, Path(os.environ["FIAS_ED_EXPERIMENTS_DIR"]))
    baixar_whisper(base, os.environ.get("FIAS_ED_ASR_SIZE", "small"))
    for model_id in ("fias-bertimbau-ptbr-frente3", "pyannote-speaker-diarization-3.1"):
        verificar_artefatos(model_id, base)
    print("MODELOS OK")
    return 0
```

Acrescentar as entradas do `pyannote` e do `faster-whisper` a
`fias-ed-shared/scientific-config/models.json`, no formato que já existe
(`model_id`, `artifacts[].sha256`, `license`, `validation_status`).

- [ ] **Step 6: Rodar o setup e os testes lentos**

Run: `docker compose run --rm -e HUGGINGFACE_TOKEN=<token> api python /app/scripts/setup_models.py`
Expected: `MODELOS OK`

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q -m lento`
Expected: PASS (3 testes)

- [ ] **Step 7: Documentar no README**

Seção nova "Modelos", com: onde ficam, como obter o token do Hugging Face,
como rodar o setup, e a observação de que o produto em execução não acessa a
rede (`HF_HUB_OFFLINE=1`).

- [ ] **Step 8: Rodar a suíte padrão e confirmar que continua sem modelo**

Run: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
Expected: PASS, e os testes `lento` **não** rodam

- [ ] **Step 9: Commit**

```bash
git add fias-ed-web fias-ed-shared/scientific-config/models.json
git commit -m "feat(web): modelos reais de ASR e diarização, com script de setup

faster-whisper e pyannote entram atrás dos protocolos da Task 3, então a suíte
padrão continua rodando sem GPU e sem peso. O setup roda uma vez e confere tudo
contra o registro do shared; em execução, HF_HUB_OFFLINE=1 garante que nada
tenta a rede.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---
### Task 15: Progresso e erros na página da aula

**Files:**
- Modify: `frontend/src/pages/AulaPage.tsx`, `frontend/src/app/status.ts`, `backend/app/aulas/service.py`
- Test: `frontend/src/pages/AulaPage.test.tsx`

**Interfaces:**
- Consumes: `STATUS_TEXT` e `statusTone` (W1, já cobrem os 18 status).

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `frontend/src/pages/AulaPage.test.tsx`:

```tsx
test("aula em transcrição mostra a mensagem do §36, sem jargão", async () => {
  mockApi({ /* aula com status TRANSCRIBING e job_ativo */ });
  renderApp("/aulas/a1");
  expect(await screen.findByText("Transformando áudio em texto…")).toBeInTheDocument();
  expect(screen.queryByText(/whisper|asr|pyannote|bertimbau|diariz/i)).not.toBeInTheDocument();
});

test("aula esperando a escolha da voz leva para a tela de vozes", async () => {
  mockApi({ /* status READY_FOR_SPEAKER_REVIEW */ });
  renderApp("/aulas/a1");
  await userEvent.click(await screen.findByRole("link", { name: /confirme qual voz é a sua/i }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1/vozes"));
});

test("aula classificada leva para os padrões de interação", async () => {
  mockApi({ /* status FIAS_COMPLETED */ });
  renderApp("/aulas/a1");
  expect(await screen.findByRole("link", { name: /ver padrões de interação/i })).toBeInTheDocument();
});

test("áudio sem fala mostra a mensagem humana e a saída", async () => {
  mockApi({ /* status ERROR, error_code AUDIO_SEM_FALA, error_message humano */ });
  renderApp("/aulas/a1");
  expect(await screen.findByRole("alert")).toHaveTextContent(/não conseguimos identificar fala/i);
  expect(screen.getByRole("button", { name: /selecionar áudio/i })).toBeInTheDocument();
});

test("nenhum texto da interface usa o vocabulário proibido", async () => {
  mockApi({ /* status FIAS_COMPLETED */ });
  renderApp("/aulas/a1");
  await screen.findByRole("link", { name: /ver padrões de interação/i });
  expect(document.body.textContent).not.toMatch(/avalia|nota do professor|desempenho|ranking/i);
});
```

Run: `cd frontend && npx vitest run src/pages/AulaPage.test.tsx`
Expected: FAIL

- [ ] **Step 2: Implementar**

A página da aula ganha, conforme o status: a mensagem de progresso do §36 com
`role="status"`, o link para `/vozes` quando `READY_FOR_SPEAKER_REVIEW`, o link
para `/transcricao` quando `READY_FOR_TRANSCRIPT_REVIEW`, e o link para
`/padroes` quando `FIAS_COMPLETED`. `JOB_MESSAGE` da W1 vira um mapa de
status → mensagem, com os textos do §36 já presentes em `status.ts`.

- [ ] **Step 3: Rodar e confirmar que passa**

Run: `cd frontend && npm test && npm run lint`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/frontend fias-ed-web/backend
git commit -m "feat(web): progresso e saídas da aula ao longo do pipeline

As mensagens são as do §36, em linguagem de pessoa: a tela nunca mostra
whisper, pyannote, BERTimbau nem 'diarização'. A tecnologia fica nos
bastidores (§86).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 16: Medição de tempo e memória, e escolha do modelo de ASR

Cumpre o §21 na parte que dá para cumprir sem áudio real de aula.

**Files:**
- Create: `fias-ed-web/scripts/medir_asr.py`
- Modify: `fias-ed-web/README.md`, `fias-ed-web/.env.example`
- Test: — (script de medição; a saída é a evidência)

- [ ] **Step 1: Escrever o script**

`scripts/medir_asr.py`, stdlib + `psutil`. Gera áudio sintético nas durações do
§18, roda cada tamanho de modelo, e imprime uma tabela em Markdown:

```python
"""Mede tempo e pico de memória dos tamanhos de Whisper (§21).

Não mede WER: exigiria áudio real de aula com transcrição de referência, que o
projeto não tem. WER e DER seguem PENDING_SCIENTIFIC_VALIDATION.
"""
DURACOES_MIN = (10, 30, 50, 60, 90)
TAMANHOS = ("tiny", "base", "small")
...
def main() -> int:
    linhas = ["| Modelo | Duração | Tempo | Pico de memória |", "|---|---|---|---|"]
    for tamanho in TAMANHOS:
        for minutos in DURACOES_MIN:
            caminho = gerar_wav(minutos)
            t, pico = medir(tamanho, caminho)
            linhas.append(f"| {tamanho} | {minutos} min | {t:.0f} s | {pico / 1e9:.1f} GB |")
    print("\n".join(linhas))
    return 0
```

- [ ] **Step 2: Rodar a medição**

Run: `docker compose run --rm api python /app/scripts/medir_asr.py | tee /tmp/medicao.md`
Expected: uma tabela com 15 linhas, sem falha

- [ ] **Step 3: Escolher o modelo e registrar**

Critério declarado: o **maior** tamanho cujo tempo numa aula de 90 min fique
abaixo de 2× a duração do áudio e cujo pico de memória fique abaixo de 5 GB (a
máquina de referência tem 6 GB de VRAM e o `pyannote` roda em seguida).

Gravar em `.env.example` (`FIAS_ED_ASR_SIZE=<escolhido>`) e colar a tabela no
README, numa seção "Escolha do modelo de ASR", com o critério escrito ao lado.

- [ ] **Step 4: Commit**

```bash
git add fias-ed-web/scripts fias-ed-web/README.md fias-ed-web/.env.example
git commit -m "chore(web): medição de tempo e memória dos tamanhos de Whisper

Tabela de tiny/base/small em 10, 30, 50, 60 e 90 min, com o critério de escolha
escrito ao lado. Não mede WER: exigiria áudio real de aula com transcrição de
referência, que o projeto não tem — WER e DER seguem
PENDING_SCIENTIFIC_VALIDATION.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 17: Revisão visual com Impeccable e critério do §84

**Files:**
- Modify: `frontend/src/design/*.css`, `frontend/src/pages/**/*.tsx` (somente o que a revisão apontar)

**Interfaces:**
- Consumes: as telas das Tasks 8, 10, 13 e 15 rodando em `http://localhost:8080`.
- Produces: telas revisadas; achados, correções e a tabela do §84 no corpo do commit.

- [ ] **Step 1: Pré-requisito e armadilha conhecida**

Confirmar que a skill `impeccable` está na sessão. **Não confiar no
`impeccable detect`**: na verificação da W1 ele retornou vazio até para CSS
deliberadamente ruim (gradiente, glow, raio de 32px, #ccc sobre #ddd). Antes de
usá-lo como evidência, rodá-lo contra uma entrada sabidamente ruim; se vier
vazio, fazer a revisão sobre as telas reais.

`DESIGN.md` e `.impeccable/design.json` são a autoridade visual.

- [ ] **Step 2: Preparar dados de exemplo**

Com o sistema no ar, criar uma conta de professor e uma aula que percorra o
pipeline inteiro com os modelos reais, até `FIAS_COMPLETED`. Criar também uma
aula parada em `ERROR` por áudio sem fala.

- [ ] **Step 3: Ciclo de revisão**

Para cada tela nova — **vozes**, **revisão da transcrição** (primeiro bloco,
bloco do meio, conflito de versão), **padrões de interação**, e a **página da
aula** em cada estado de progresso — em 360 px e 1280 px:

1. Capturar a tela real e medir contraste nos estilos computados, não a olho.
2. Corrigir dentro das regras: só tokens do shared, nenhuma cor nova, sem
   gradiente, glow ou glassmorphism, `border-radius` só `--radius-sm`/`--radius-md`,
   Rokkitt só em título ≥ 24 px, sem atributo `style`.
3. `cd frontend && npm test && npm run lint && npm run build`.
4. Uma rodada de confirmação, e parar.

- [ ] **Step 4: Critério visual final (§84)**

Responder no commit: "Esta interface parece um produto criado especificamente
para professores ou parece um template gerado por IA?" e preencher a tabela com
evidência por item: hierarquia; espaçamento; tipografia; contraste;
consistência; uso da paleta; uso correto de Ubuntu; uso editorial de Rokkitt;
responsividade; densidade; legibilidade; ausência de gradientes; ausência de
componentes decorativos desnecessários.

Atenção especial a duas coisas desta fatia: a **tela de revisão** é a mais densa
do produto e a mais fácil de virar planilha; e a **tela de padrões** é a que
mais arrisca virar boletim.

- [ ] **Step 5: Rebuild e commit**

```bash
docker compose up -d --build web
git add fias-ed-web/frontend
git commit -m "style(web): revisão visual com Impeccable e critério do §84 nas telas de W2

<achados, correções e a tabela do §84>

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 18: Verificação final da fatia W2

**Files:**
- Modify: `fias-ed-web/README.md` (resultados das auditorias, se mudaram)

**Interfaces:**
- Consumes: tudo.
- Produces: evidência dos 13 critérios de aceite do spec §13, registrada no corpo do commit.

- [ ] **Step 1: Suítes e auditorias**

Run (de `fias-ed-web/`):
```bash
docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q
docker compose -f docker-compose.test.yml run --rm api-test pytest -q -m lento
docker compose -f docker-compose.test.yml run --rm api-test bandit -r app --severity-level high
docker compose -f docker-compose.test.yml run --rm api-test pip-audit --skip-editable
cd frontend && npm ci && npm test && npm run lint && npm run build && npm audit --audit-level=high && cd ..
```
Expected: todos PASS; bandit sem achados altos; pip-audit e npm audit sem
vulnerabilidade alta/crítica não tratada.

Run (de `fias-ed-shared/engine-py`): `.venv/Scripts/python -m pytest -q`
Expected: PASS.

**Se algum teste falhar de forma intermitente, não repetir até passar.** Medir:
rodar o arquivo suspeito cinco vezes e contar. Um teste que falha em 1 de 5 é
defeito de teste, não azar, e é corrigido nesta task.

- [ ] **Step 2: Sistema no ar e fluxo completo**

Run:
```bash
docker compose up -d --build
docker compose ps --format "{{.Service}} {{.Status}}"
docker compose ps --format "{{.Service}} {{.Publishers}}"
for s in api worker web db; do echo "$s: $(docker compose exec -T $s id -u)"; done
```
Expected: todos `healthy` (`migrate` saiu com 0); só `web` publica, em
`127.0.0.1:8080`; nenhum `id -u` igual a `0`.

Pela interface, levar uma aula de `AUDIO_VALIDATED` a `FIAS_COMPLETED` sem
tocar no banco.

- [ ] **Step 3: Fontes científicas intactas**

Run (da raiz do monorepo):
```bash
cd fias-ed-shared && engine-py/.venv/Scripts/python scripts/source_snapshot.py verify ../fias-ed-web/.source-snapshot.json
```
Expected: `OK — nenhuma alteração`.

Se acusar alteração, **conferir se está dentro de `.git/`** antes de concluir
qualquer coisa: o snapshot cobre 856 arquivos de plumbing do git no
`qti_system`, e `FETCH_HEAD` muda a cada `git fetch` sem conter conteúdo do
projeto. Diferença fora de `.git/` é que é alteração de fonte científica.

- [ ] **Step 4: Conferir os 13 critérios de aceite do spec §13, um a um**

Registrar, para cada um, o comando ou teste que o comprova.

- [ ] **Step 5: Commit**

```bash
git add fias-ed-web/README.md
git commit --allow-empty -m "chore(web): verificação final da fatia W2

<resultado de cada critério 1–13 do spec §13, com o comando/teste que o comprova>

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
