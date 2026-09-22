# Modelo de dados

Modelo lógico das 20 entidades do FIAS-ED (`schemas/entities/*.schema.json`),
comum a Web e Android. Para os campos entidade a entidade, ver
`ENTITY_DICTIONARY.md`. Para a exportação de dataset entre aulas, ver a
seção 5 abaixo e `PRIVACY.md`.

## Diagrama textual das relações

```
Professor 1──N Turma
Professor 1──N Disciplina
Escola     1──N Turma

Turma 1──N Aula
Disciplina 1──N Aula
Professor  1──N Aula

Aula 1──N Audio               (Audio.aula_id; is_original marca o original)
Aula 1──N Transcricao         (uma por combinação áudio×modelo ASR)
Aula 1──N Processamento       (um registro por execução do pipeline)
Aula 1──1 Relatorio
Aula 1──1 QuestionarioQTI     (0 ou 1; pode não existir ainda)
Aula 1──1 Triangulacao
Aula 1──1 ResultadoMTSS
Aula 1──N IndicadorFIAS       (um por índice habilitado)

Transcricao 1──N Falante
Transcricao 1──N Segmento

Segmento 1──1 Falante          (Segmento.falante_id)
Segmento 1──1 ClassificacaoFIAS (ClassificacaoFIAS.segmento_id)

QuestionarioQTI 1──N RespostaQTI
QuestionarioQTI 1──1 ResultadoQTI

ResultadoMTSS 1──N Recomendacao

ModeloIA (registro independente, referenciado por model_id em
          ClassificacaoFIAS, Transcricao, Processamento)
```

## Campos comuns

Todas as entidades herdam de `_base.schema.json` (`allOf` no JSON Schema):

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string (UUID) | Identificador. `UUIDv7` (ordenável por tempo de criação), gerado localmente em cada dispositivo. |
| `created_at` | string (date-time) | Data/hora de criação. |
| `updated_at` | string (date-time) | Data/hora da última alteração. |
| `deleted_at` | string (date-time) ou `null` | Soft delete: quando preenchido, a entidade é tratada como excluída sem remover a linha fisicamente (exceto onde a exclusão real é exigida — ver `PRIVACY.md` para Audio/Segmento). |
| `version` | integer (≥1) | Contador de versão da entidade, incrementado a cada alteração — base do controle de conflito de sincronização (ver `FUTURE_SYNC.md`). |
| `sync_status` | enum | `LOCAL_ONLY`, `PENDING_SYNC`, `SYNCED`, `CONFLICT`. |
| `device_id` | string | Identificador do dispositivo onde a entidade foi criada/alterada por último. |

## UUIDv7 e soft delete

`UUIDv7` foi escolhido (em vez de `UUIDv4`) porque incorpora um timestamp,
permitindo ordenar registros por criação sem precisar de uma coluna extra de
sequência — útil tanto no SQLite/Room do Android quanto num futuro Postgres.
Soft delete (`deleted_at`) é o padrão para a maioria das entidades, porque
preserva o histórico necessário à reprodutibilidade científica (ex.: um
`Relatorio` já gerado deve continuar existindo mesmo que a `Aula` de origem
seja posteriormente marcada como excluída). A exclusão **real** (remoção
física) é usada apenas para dados de áudio e transcrição, por exigência de
privacidade (CEP l.85 — "O áudio original permanece restrito ao dispositivo
do professor"; ver `PRIVACY.md` §"Exclusão").

## Áudio em filesystem (sem BLOB)

A entidade `Audio` não guarda o conteúdo binário do áudio no banco de dados
— apenas metadados (`path`, `sha256`, `size_bytes`, `duration_ms`,
`mime_type`, `original_filename`, `internal_filename` no formato
`<uuid>.<extensão>`, `channels`, `sample_rate`, `is_original`,
`derived_from_audio_id`). O arquivo de áudio em si fica no sistema de
arquivos local (Web: pasta do pesquisador / volume Docker; Android:
armazenamento privado do app). Nenhuma entidade deste modelo tem coluna do
tipo `BLOB` para dados binários; isso mantém o banco pequeno, permite copiar
apenas os metadados em exportações (sem áudio) e facilita a exclusão física
segura do arquivo original quando necessário.

## Mapeamento previsto para PostgreSQL (Web) e Room (Android)

Este subprojeto define apenas o modelo lógico (JSON Schema); o mapeamento
físico fica a cargo dos subprojetos 2 e 3, mas segue o mesmo desenho:

- **Web (PostgreSQL)**: uma tabela por entidade, `id UUID PRIMARY KEY`,
  colunas `created_at`/`updated_at` `TIMESTAMPTZ`, `deleted_at`
  `TIMESTAMPTZ NULL`, índices em toda foreign key (`professor_id`,
  `turma_id`, `aula_id`, etc.) e em `sync_status` para consultas de
  sincronização futura. Objetos livres (`parameters`, `stage_times_ms`,
  `evidence` de `ResultadoMTSS.fired_rules`) mapeiam para colunas `JSONB`.
- **Android (Room/SQLite)**: uma tabela `@Entity` por entidade, `id` como
  `PRIMARY KEY` em `TEXT`, campos de data como `TEXT` ISO-8601 ou `INTEGER`
  epoch (a critério do subprojeto 3), objetos livres serializados como
  `TEXT` (JSON). O áudio permanece em armazenamento privado do app
  (`context.filesDir` ou equivalente), nunca em `BLOB` no SQLite.

## Exportação do dataset (`schemas/export/lesson_dataset.schema.json`)

Além do modelo transacional acima, existe um formato de **exportação**
agregando uma ou mais aulas para análise externa (planilhas, R, Python),
gerado por `fias_ed_engine.export.build_dataset` e validado por
`schemas/export/lesson_dataset.schema.json`. É um formato tabular derivado
(10 tabelas: `lessons`, `segments`, `intervals`, `matrix`, `indices`,
`qti_responses`, `qti_results`, `mtss`, `recommendations`, `triangulation`,
mais um `manifest`), não uma cópia do banco transacional. Por padrão
**nenhum texto de fala é exportado**; a opção `include_text` inclui apenas
`text_pseudonymized` (produzido pela etapa de NER do app), e a exportação é
recusada se qualquer segmento não tiver essa versão pseudonimizada. **Áudio
nunca é exportado** neste formato. Ver `PRIVACY.md` §"Exportação" para o
detalhamento de privacidade.
