# Arquitetura — FIAS-ED

Este documento descreve como os três subprojetos do monorepo se encaixam,
o papel do `fias-ed-shared`, o fluxo do professor mapeado para os estados de
uma aula, as decisões de arquitetura já tomadas e o que fica para depois.

## 1. Visão geral dos fluxos

### Web (subprojeto 2, a construir)

```
Navegador (React)
      │  HTTP/JSON
      ▼
FastAPI
      │  chama fias_ed_engine (Python, deste repo)
      ▼
PostgreSQL  ◄────────────►  Pipeline local de áudio
(entidades do modelo         (ASR, diarização, classificador
 lógico de dados)             BERTimbau — pesos fora do Git)
```

O FastAPI roda no PC local do pesquisador via Docker Compose, acessível pelo
navegador na máquina ou na rede local, sem exposição à internet. O motor
Python (`fias_ed_engine`) é importado diretamente pelo backend: ele não
reimplementa nenhuma regra, apenas consome os arquivos de `fias-ed-shared/`.

### Android (subprojeto 3, a construir)

```
Compose (UI)
      │
      ▼
ViewModel / caso de uso
      │
      ▼
Room / SQLite  ◄──────────────►  WorkManager
(mesmo modelo lógico de           (orquestra tarefas em segundo plano:
 dados dos schemas do shared)      transcrição, diarização, classificação)
      │                                    │
      └───────────► motor Kotlin (a implementar) ◄───────────┘
                     consome os mesmos rules/*.json e passa
                     nos mesmos casos de conformance/
                            │
                            ▼
                  whisper.cpp (ASR) / ONNX Runtime
                  (BERTimbau int8, execução local no aparelho)
```

O app Android é offline-first: toda a gravação, transcrição, diarização,
classificação FIAS, questionário QTI, triangulação e geração de relatório
funcionam sem rede. Nada sincroniza automaticamente (ver §5).

## 2. Papel do `fias-ed-shared`

O `shared` é a única fonte das regras científicas e do modelo de dados. Ele
não expõe API nem tela — é consumido como biblioteca/arquivo por Web e
Android:

- **Regras declarativas em JSON** (`rules/fias_rules.json`,
  `qti_config.json`, `mtss_rules.json`, `pedagogical_rules.json`), cada uma
  validada contra um JSON Schema em `schemas/rules/`. Mudar uma regra é
  editar o JSON, nunca o código de um motor específico.
- **Schemas do modelo lógico de dados** (`schemas/entities/`, 20 entidades:
  Professor, Escola, Turma, Disciplina, Aula, Audio, Transcricao, Segmento,
  Falante, ClassificacaoFIAS, IndicadorFIAS, QuestionarioQTI, RespostaQTI,
  ResultadoQTI, Triangulacao, ResultadoMTSS, Recomendacao, Relatorio,
  Processamento, ModeloIA), com campos comuns de rastreabilidade e
  sincronização (`id` UUIDv7, `created_at`, `updated_at`, `deleted_at`,
  `version`, `sync_status`, `device_id`).
- **Vetores de conformidade** (`conformance/cases/*.json`): pares
  entrada → saída esperada para cada função do motor de referência. Um
  motor só é aceito se passar em 100% desses casos.
- **Motor de referência em Python** (`engine-py`, pacote `fias_ed_engine`):
  é a implementação que o backend Web importa diretamente e o exemplo
  executável de como interpretar as regras.
- **Motor Kotlin (a implementar no subprojeto 3)**: reimplementação das
  mesmas funções (`segments_to_intervals`, `transition_matrix`,
  `compute_indices`, `constrain_by_role`, `score_qti`, `triangulate`,
  `evaluate_mtss`, `recommendations`), lendo os mesmos arquivos de `rules/`
  e validado rodando os mesmos casos de `conformance/`. Enquanto esse motor
  não existir, o subprojeto 3 não está liberado para gerar relatórios finais
  no aparelho.
- **Design tokens** (`design-tokens/tokens.json` → `tokens.css` para o Web,
  `FiasTokens.kt` para o Compose) e fontes locais (Ubuntu, Rokkitt), para
  que as duas interfaces compartilhem a mesma identidade visual.

## 3. Fluxo do professor mapeado para os estados da aula

O ciclo de vida de uma aula é modelado pelo campo `status` da entidade
`Aula` (`fias-ed-shared/schemas/entities/aula.schema.json`). O fluxo abaixo
é o mesmo em Web e Android — muda apenas onde cada etapa é executada
(servidor local vs. aparelho):

```
DRAFT
  │ professor cria a aula (turma, disciplina, data)
  ▼
AUDIO_IMPORTED
  │ professor grava ou importa o áudio
  ▼
AUDIO_VALIDATED
  │ checagem de formato/duração/integridade do áudio
  ▼
PREPROCESSING ──► TRANSCRIBING ──► TRANSCRIBED ──► DIARIZING
  │ pipeline local: ASR (whisper.cpp/Web) e diarização de falantes
  ▼
READY_FOR_SPEAKER_REVIEW
  │ professor confirma qual falante é o professor (restrição por papel, §4)
  ▼
READY_FOR_TRANSCRIPT_REVIEW
  │ revisão opcional do texto transcrito (texto_original_asr vs. texto_revisado)
  ▼
READY_FOR_FIAS ──► FIAS_COMPLETED
  │ classificação por intervalo de 3 s, matriz de transições, índices (TT, PT, SC, ID_RATIO, PIR…)
  ▼
WAITING_QTI ──► QTI_COMPLETED
  │ turma responde o QTI-24 (formulário, importação, digitação ou OCR); agregação por turma (mínimo 10 respostas)
  ▼
TRIANGULATED
  │ pares conceituais FIAS ↔ QTI com evidências, sem classificação automática do plano
  ▼
MTSS_INTERPRETED
  │ regras descritivas do Tier 1 disparadas + sugestões pedagógicas preliminares
  ▼
REPORT_READY
  │ relatório final disponível ao professor
```

Qualquer etapa pode transicionar para `ERROR` (com `error_code` e `note`)
em caso de falha técnica; o professor pode retomar a partir do último
estado consistente. Este fluxo e os nomes de estado vêm da spec do `shared`
(§9, entidade `Aula`) — não existe, neste repositório, uma descrição do
prompt original do pesquisador além do que está formalizado nesse enum.

## 4. Decisões de arquitetura tomadas

- **Monorepo único** para os três subprojetos, em vez de repositórios
  separados: mantém `shared` como dependência versionada junto com quem o
  consome, sem publicação de pacote.
- **Regras declarativas em JSON + JSON Schema + conformidade
  compartilhada**, em vez de um motor multiplataforma (Kotlin
  Multiplatform/Rust): descartado por custo de build; e em vez de regras
  apenas no servidor: descartado por violar o requisito de o Android
  funcionar offline. Cada motor (Python, Kotlin) é uma implementação
  independente das mesmas regras, validada pelo mesmo conjunto de casos.
- **MTSS Tier 1 descritivo**: as regras de `mtss_rules.json` descrevem
  padrões observáveis (categoria docente modal, `ID_RATIO`, presença ou
  ausência de categorias) e nunca emitem rótulos de julgamento — vocabulário
  proibido é verificado por teste automatizado (`fias_ed_engine.language`).
- **QTI-24**, não QTI-64: o QTI-24 do sistema `avalie-seu-professor` tem
  mapeamento, pontuação e implementação de referência completos e
  auditáveis; o QTI-64 da dissertação não tem mapeamento item→escala
  documentado nas fontes disponíveis (ver `fias-ed-shared/docs/QTI.md`).
- **Restrição por papel** na classificação FIAS: como o papel do falante é
  conhecido (o professor confirma a própria voz), o motor grava tanto
  `pred_raw` (argmax sobre as 10 categorias) quanto
  `pred_role_constrained` (argmax restrito às categorias válidas para o
  papel); o relatório usa a versão restrita e a divergência entre as duas é
  registrada em `Processamento`.
- **`token_type_ids` sempre zero** na entrada do classificador BERTimbau:
  decisão de engenharia documentada (não uma afirmação científica), fiel ao
  que o modelo viu no treino — acurácia 0,7915 nessa configuração contra
  0,7773 usando segmentos de frase, medida em 211 casos
  (`fias-ed-shared/docs/ANALISE_MODELOS_EXISTENTES.md`).
- **Toda regra, índice ou parâmetro tem `source_reference` e
  `validation_status`** (`validated`, `PENDING_SCIENTIFIC_VALIDATION`,
  `engineering_decision` ou `draft_pending_researcher_review`); regras
  pendentes com corte normativo ficam desativadas (`enabled: false`) até
  revisão do pesquisador.

## 5. Futuro: sincronização

A sincronização entre o app Android (offline-first) e um futuro backend Web
**não está implementada** neste subprojeto — apenas preparada: cada
entidade já tem `sync_status` (`LOCAL_ONLY`, `PENDING_SYNC`, `SYNCED`,
`CONFLICT`), `version` e `device_id`. A estratégia proposta (last-writer-wins
combinado com detecção de conflito por `version`, resolução manual para
`CONFLICT`, e a regra de que o áudio original nunca sincroniza sem
autorização explícita do professor) está detalhada em
[`fias-ed-shared/docs/FUTURE_SYNC.md`](fias-ed-shared/docs/FUTURE_SYNC.md) e
no esboço de API em
[`fias-ed-shared/docs/FUTURE_SYNC_API.md`](fias-ed-shared/docs/FUTURE_SYNC_API.md).
Nenhum dos dois documentos corresponde a código existente; servem de ponto
de partida para quando o subprojeto 2 (ou uma fase posterior) implementar a
sincronização de fato.

## 6. Documentação relacionada

- [`README.md`](README.md) — visão geral do projeto e como rodar os testes.
- [`fias-ed-shared/README.md`](fias-ed-shared/README.md) — comandos do
  `shared` e procedimento para alterar uma regra.
- [`docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md`](docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md)
  — especificação completa do `shared`, com todas as decisões, fontes e
  critérios de aceite.
- `fias-ed-shared/docs/` — documentação científica detalhada (FIAS, QTI,
  MTSS, rastreabilidade, reprodutibilidade, modelo de dados, privacidade,
  design system, referências de interface).
