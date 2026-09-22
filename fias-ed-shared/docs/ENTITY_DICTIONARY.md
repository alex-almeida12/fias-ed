# Dicionário de entidades

Gerado a partir dos JSON Schemas em `schemas/entities/*.schema.json`
(fonte única — qualquer divergência deste documento com o schema deve ser
corrigida aqui, não no schema). Todas as 20 entidades estendem os campos
comuns de `_base.schema.json`, documentados uma vez abaixo e omitidos das
tabelas por entidade.

## Campos comuns (`_base.schema.json`)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `id` | string (uuid) | sim | Identificador da entidade. |
| `created_at` | string (date-time) | sim | Data/hora de criação. |
| `updated_at` | string (date-time) | sim | Data/hora da última alteração. |
| `deleted_at` | string (date-time) ou null | sim | Soft delete; `null` quando ativo. |
| `version` | integer (≥1) | sim | Contador de versão. |
| `sync_status` | enum: LOCAL_ONLY, PENDING_SYNC, SYNCED, CONFLICT | sim | Estado de sincronização. |
| `device_id` | string | sim | Dispositivo de origem da última alteração. |

## Professor

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `display_name` | string (≤120) | sim | Nome de exibição. |
| `role` | enum: ADMIN_LOCAL, PROFESSOR | sim | Papel de acesso ao sistema. |
| `username` | string (≤64) | não | Nome de usuário de login. |

## Escola

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `name` | string (≤200) | sim | Nome da escola. |
| `municipality` | string (≤120) | não | Município. |
| `region` | enum: Norte, Nordeste, Centro-Oeste, Sudeste, Sul | não | Região do Brasil. |

## Turma

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `escola_id` | string (uuid) | sim | Referência a `Escola`. |
| `professor_id` | string (uuid) | sim | Referência a `Professor`. |
| `name` | string (≤120) | sim | Nome/identificação da turma. |
| `school_year` | integer | não | Ano letivo. |
| `level` | string (≤60) | não | Nível/etapa de ensino. |

## Disciplina

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `professor_id` | string (uuid) | sim | Referência a `Professor`. |
| `name` | string (≤120) | sim | Nome da disciplina. |

## Aula

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `professor_id` | string (uuid) | sim | Referência a `Professor`. |
| `turma_id` | string (uuid) | sim | Referência a `Turma`. |
| `disciplina_id` | string (uuid) | sim | Referência a `Disciplina`. |
| `lesson_date` | string (date) | sim | Data da aula. |
| `status` | enum (17 valores) | sim | Estado do pipeline: DRAFT, AUDIO_IMPORTED, AUDIO_VALIDATED, PREPROCESSING, TRANSCRIBING, TRANSCRIBED, DIARIZING, READY_FOR_SPEAKER_REVIEW, READY_FOR_TRANSCRIPT_REVIEW, READY_FOR_FIAS, FIAS_COMPLETED, WAITING_QTI, QTI_COMPLETED, TRIANGULATED, MTSS_INTERPRETED, REPORT_READY, ERROR. |
| `note` | string (≤2000) | não | Anotação livre. |
| `error_code` | string (≤64) | não | Código de erro, se `status = ERROR`. |

## Audio

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `original_filename` | string (≤255) | sim | Nome original do arquivo enviado. |
| `internal_filename` | string (padrão `<uuid>.<ext>`) | sim | Nome do arquivo no armazenamento interno. |
| `path` | string (≤1024) | sim | Caminho do arquivo (filesystem, não BLOB). |
| `mime_type` | enum: audio/mpeg, audio/wav, audio/x-wav, audio/mp4, audio/aac, audio/flac, audio/x-flac | sim | Tipo MIME do áudio. |
| `size_bytes` | integer (≥1) | sim | Tamanho em bytes. |
| `duration_ms` | integer (≥1) | sim | Duração em milissegundos. |
| `sha256` | string (64 hex) | sim | Hash de integridade do arquivo. |
| `channels` | integer (≥1) | sim | Número de canais. |
| `sample_rate` | integer (≥8000) | sim | Taxa de amostragem. |
| `is_original` | boolean | sim | Marca se é o arquivo original (imutável) ou uma cópia derivada. |
| `derived_from_audio_id` | string (uuid) ou null | não | Áudio de origem, se derivado. |

## Transcricao

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `audio_id` | string (uuid) | sim | Referência a `Audio`. |
| `language` | enum: pt-BR | sim | Idioma da transcrição. |
| `asr_model_id` | string | sim | Código do `ModeloIA` de ASR usado (`ModeloIA.model_id`, ex. `faster-whisper-small`) — string curta, não UUID (mesma convenção de `ClassificacaoFIAS.model_id`). |

## Falante

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `transcricao_id` | string (uuid) | sim | Referência a `Transcricao`. |
| `diarization_label` | string (≤32) | sim | Rótulo bruto de diarização (ex. "SPEAKER_00"). |
| `role` | enum: PROFESSOR, ALUNO, UNASSIGNED | sim | Papel atribuído ao falante. Nenhum embedding de voz é persistido nesta entidade. |

## Segmento

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `transcricao_id` | string (uuid) | sim | Referência a `Transcricao`. |
| `falante_id` | string (uuid) | sim | Referência a `Falante`. |
| `start_ms` | integer (≥0) | sim | Início do segmento (tempo global da aula). |
| `end_ms` | integer (≥1) | sim | Fim do segmento (tempo global da aula). |
| `texto_original_asr` | string (≤10000) | sim | Transcrição bruta do ASR. |
| `texto_revisado` | string (≤10000) ou null | sim | Transcrição revisada por humano, se houver. |
| `revisado` | boolean | sim | Se o segmento já passou por revisão humana. |
| `asr_confidence` | number [0,1] | não | Confiança do ASR para o segmento. |
| `text_pseudonymized` | string (≤10000) ou null | não | Texto do segmento após a etapa de NER (nomes próprios substituídos por `[NOME]`), só presente quando essa etapa já rodou (ver `PRIVACY.md`). |

## ClassificacaoFIAS

Schema: `schemas/entities/classificacao_fias.schema.json`.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `segmento_id` | string (uuid) | sim | Referência a `Segmento`. |
| `transcript_source` | enum: ASR_ORIGINAL, TRANSCRICAO_REVISADA | sim | Qual texto foi classificado. |
| `pred_raw` | integer [1,10] | sim | Categoria FIAS prevista sem restrição por papel (argmax sobre as 10 categorias). |
| `pred_role_constrained` | integer [1,10] | sim | Categoria FIAS prevista com restrição por papel (ver `FIAS.md`). |
| `confidence_raw` | number [0,1] | sim | Confiança (softmax) da predição sem restrição. |
| `confidence` | number [0,1] | sim | Confiança (softmax) da predição restrita por papel. |
| `uncertain` | boolean | sim | `confidence < uncertain_below` (0,5). |
| `model_id` | string | sim | Identificador do modelo usado (`ModeloIA.model_id`). |
| `rules_version` | string | sim | Versão de `fias_rules.json` usada. |

## IndicadorFIAS

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `index_id` | string | sim | Identificador do índice (ex. `TT`, `ID_RATIO`). |
| `value` | number ou null | sim | Valor calculado; `null` se `reason = insufficient_data`. |
| `reason` | null ou `"insufficient_data"` | sim | Motivo de `value` ser nulo. |
| `numerator_count` | integer (≥0) | sim | Contagem do numerador. |
| `denominator_count` | integer (≥0) | sim | Contagem do denominador. |
| `n_intervals` | integer (≥0) | sim | Número de intervalos de 3 s usados no cálculo. |
| `rules_version` | string | sim | Versão de `fias_rules.json` usada. |
| `validation_status` | enum: validated, PENDING_SCIENTIFIC_VALIDATION, engineering_decision, draft_pending_researcher_review | sim | Status do índice na fonte científica. |
| `mean_confidence` | number [0,1] ou null | não | Confiança média das classificações usadas. |

## QuestionarioQTI

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `instrument_version` | string | sim | Versão do instrumento QTI usado. |
| `source` | enum: IMPORT_AVALIE_SEU_PROFESSOR, FORM, MANUAL, OCR | sim | Origem das respostas. |
| `confirmed` | boolean | sim | Se as respostas foram confirmadas por humano. |
| `import_filename` | string (≤255) | não | Nome do arquivo importado, se `source = IMPORT_AVALIE_SEU_PROFESSOR`. |

## RespostaQTI

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `questionario_qti_id` | string (uuid) | sim | Referência a `QuestionarioQTI`. |
| `answers` | objeto com exatamente 24 chaves "1".."24", valores inteiros [1,5] | sim | Respostas do item, por número de item. |
| `ocr_confidence` | number [0,1] | não | Confiança do OCR, se `source = OCR`. |

## ResultadoQTI

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `questionario_qti_id` | string (uuid) | sim | Referência a `QuestionarioQTI`. |
| `response_count` | integer (≥0) | sim | Número de respostas agregadas. |
| `displayable` | boolean | sim | `response_count >= min_responses` (10). |
| `octants` | objeto com oc1..oc8, cada um number ou null | sim | Valor agregado por octante. |
| `agency` | number ou null | sim | Eixo Agency agregado. |
| `communion` | number ou null | sim | Eixo Communion agregado. |
| `rules_version` | string | sim | Versão de `qti_config.json` usada. |

## Triangulacao

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `pairs` | array de objetos `{pair_id, fias_value, qti_available, qti_values}` | sim | Um item por par de triangulação definido em `pedagogical_rules.json`. |
| `rules_version` | string | sim | Versão de `pedagogical_rules.json` usada. |

## ResultadoMTSS

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `fired_rules` | array de objetos `{rule_id, tier1_dimension, framing, evidence, evidence_segments?, validation_status}` | sim | Regras MTSS disparadas para a aula. `evidence_segments` (opcional) é uma lista de `{segmento_id, start_ms, end_ms}` apontando os trechos de transcrição citados como evidência (spec §7: "segmento, timestamp"); `validation_status` é o status de validação da própria regra (`mtss_rules.json`). |
| `rules_version` | string | sim | Versão de `mtss_rules.json` usada. |

## Recomendacao

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `resultado_mtss_id` | string (uuid) | sim | Referência a `ResultadoMTSS`. |
| `recommendation_id` | string | sim | Identificador da sugestão em `pedagogical_rules.json`. |
| `rule_id` | string | sim | Regra MTSS que originou a sugestão. |
| `text` | string (≤2000) | sim | Texto da sugestão (vocabulário formativo). |
| `validation_status` | enum: validated, PENDING_SCIENTIFIC_VALIDATION, engineering_decision, draft_pending_researcher_review | sim | Status do texto da sugestão. |

## Relatorio

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `status` | enum: DRAFT, READY | sim | Estado de geração do relatório. |
| `rules_version` | string | sim | Versão de regras usada na geração. |
| `app_version` | string | sim | Versão do app que gerou o relatório. |
| `pdf_path` | string (≤1024) | não | Caminho do PDF gerado. |
| `pdf_sha256` | string (64 hex) | não | Hash do PDF gerado. |

## Processamento

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `aula_id` | string (uuid) | sim | Referência a `Aula`. |
| `app_version` | string | sim | Versão do app. |
| `rules_version` | string | sim | Versão de `rules/` usada. |
| `asr_model` | string | sim | Identificador do modelo de ASR. |
| `asr_model_hash` | string (64 hex) | sim | Hash do modelo de ASR. |
| `diarization_model` | string | sim | Identificador do modelo de diarização. |
| `fias_model` | string | sim | Identificador do modelo FIAS. |
| `fias_model_hash` | string (64 hex) | sim | Hash do modelo FIAS. |
| `parameters` | objeto livre | sim | Parâmetros de execução. |
| `hardware` | string (≤200) | sim | Descrição do hardware. |
| `device` | string (≤200) | sim | Dispositivo de processamento. |
| `audio_duration_ms` | integer (≥0) | sim | Duração do áudio processado. |
| `transcript_source` | enum: ASR_ORIGINAL, TRANSCRICAO_REVISADA | sim | Fonte de texto usada. |
| `stage_times_ms` | objeto livre | sim | Tempo por etapa do pipeline. |
| `status` | enum (mesmo de `Aula.status`) | sim | Estado do pipeline neste processamento. |
| `processing_time_ms` | integer (≥0) | não | Tempo total de processamento. |
| `role_divergence_rate` | number [0,1] ou null | não | Taxa de divergência `pred_raw` × `pred_role_constrained`. |
| `error_code` | string (≤64) | não | Código de erro, se houve falha. |

## ModeloIA

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `model_id` | string | sim | Identificador único do modelo (ex. `fias-bertimbau-ptbr-frente3`). |
| `name` | string | sim | Nome descritivo. |
| `model_version` | string | sim | Versão do modelo. |
| `task` | string | sim | Tarefa (ex. `fias_utterance_classification`). |
| `format` | enum: safetensors, onnx, ggml, other | sim | Formato do artefato. |
| `sha256` | string (64 hex) | sim | Hash de integridade dos pesos. |
| `size_bytes` | integer (≥1) | sim | Tamanho em bytes. |
| `source` | string (≤500) | sim | Origem/caminho do artefato. |
| `license` | string (≤200) | sim | Licença. |
| `parameters` | objeto livre | sim | Metadados/hiperparâmetros do modelo. |
