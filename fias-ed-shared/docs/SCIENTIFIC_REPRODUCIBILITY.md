# Reprodutibilidade científica

Este documento reúne o que o FIAS-ED grava para permitir reproduzir um
resultado: os campos de `Processamento`, o papel dos casos de `conformance/`,
as seeds usadas nos experimentos, as versões de dependências e o mecanismo
de snapshot de integridade das fontes externas.

## Campos de `Processamento`

A entidade `Processamento` (`schemas/entities/processamento.schema.json`)
registra, por aula, tudo que é necessário para reproduzir o processamento
daquela aula especificamente:

| Campo | Descrição |
|---|---|
| `app_version` | Versão do aplicativo que processou a aula. |
| `rules_version` | Versão de `rules/*.json` usada (deve bater com a de todos os JSON envolvidos). |
| `asr_model` | Identificador do modelo de ASR usado (definido pelos subprojetos 2/3). |
| `asr_model_hash` | SHA-256 do modelo de ASR. |
| `diarization_model` | Identificador do modelo de diarização usado. |
| `fias_model` | Identificador do modelo de classificação FIAS (ex.: `fias-bertimbau-ptbr-frente3`). |
| `fias_model_hash` | SHA-256 do artefato de pesos do modelo FIAS. |
| `parameters` | Objeto livre com parâmetros de execução (ex.: limiares, opções do pipeline). |
| `hardware` | Descrição do hardware usado no processamento. |
| `device` | Dispositivo (ex.: identificador do celular ou "Web"). |
| `audio_duration_ms` | Duração do áudio processado. |
| `processing_time_ms` | Tempo total de processamento. |
| `stage_times_ms` | Tempo de processamento por etapa (objeto livre, uma chave por etapa do pipeline). |
| `created_at` | Data/hora de criação do registro (campo comum da entidade base). |
| `transcript_source` | `ASR_ORIGINAL` ou `TRANSCRICAO_REVISADA` — qual versão do texto foi usada para classificar. |
| `role_divergence_rate` | Taxa de divergência entre `pred_raw` e `pred_role_constrained` no conjunto de segmentos da aula (ver `FIAS.md` §"Restrição por papel"). |
| `status` | Estado do pipeline no momento do registro (mesmo enum de `Aula.status`). |
| `error_code` | Código de erro, se houve falha em alguma etapa. |

Esses campos aparecem tanto na entidade `Processamento` quanto, de forma
resumida (`app_version`, `fias_model`, `fias_model_hash`, `asr_model`,
`asr_model_hash`, `diarization_model`), no `manifest.processing` da
exportação de dataset (`export.py`, ver `DATABASE_MODEL.md`).

## Papel dos casos de `conformance/`

`conformance/cases/*.json` fixa, para cada função pura do motor
(`segments_to_intervals`, `transition_matrix`, `compute_indices`,
`constrain_by_role`, `score_response`, `aggregate_qti`, `evaluate_mtss`,
`triangulate`), um conjunto de casos `{id, function, description, input,
expected}` gerados pelo motor de referência Python
(`scripts/generate_conformance.py`) contra a `rules_version` corrente.
Qualquer motor (o Python de referência, ou o motor Kotlin do subprojeto 3)
só atende ao critério de conformidade se reproduzir **100% dos casos**, com tolerância
absoluta de `1e-9` para valores de ponto flutuante. Isso é o que garante que
Web e Android, embora sejam duas implementações diferentes da mesma
lógica, produzam exatamente o mesmo resultado científico para a mesma
entrada — a reprodutibilidade entre plataformas depende inteiramente desses
casos, não de inspeção manual de código.

## Seeds

Seed `42` é usada de forma consistente em todos os experimentos de modelo
registrados em `models.json` (treino do BERTimbau, amostragem estratificada
do benchmark de 211 amostras) — ver `ANALISE_MODELOS_EXISTENTES.md` §3. O
motor de referência (`fias_ed_engine`) é determinístico e não usa
aleatoriedade em tempo de execução (nenhuma função de `rules.py`,
`indices.py`, `intervals.py`, `qti.py`, `mtss.py` ou `triangulation.py`
consulta um gerador de números aleatórios).

## Versões de dependências

`engine-py/pyproject.toml`: Python `>=3.11`; dependência de execução
`jsonschema[format-nongpl]>=4.23,<5`; dependência de desenvolvimento
`pytest>=8`; dependências opcionais de ferramentas (`tools`)
`fonttools>=4.53` e `brotli>=1.1` (usadas por `scripts/fetch_fonts.py` e
`scripts/build_tokens.py`, fora do escopo científico). O modelo BERTimbau
registrado foi treinado com `transformers 5.8.1` (gravado em
`config.json` do checkpoint).

## Snapshot de integridade das fontes

`scripts/source_snapshot.py` varre, recursivamente, `experiments_dir()` e
`qti_system_dir()` (as duas árvores de arquivos externas somente leitura) e
grava, por arquivo, `[tamanho_em_bytes, mtime_em_ns]`, ignorando diretórios
como `.venv`, `node_modules`, `.next`, `test-results` e `__pycache__`.

- `python scripts/source_snapshot.py create <arquivo.json>` grava o
  snapshot atual.
- `python scripts/source_snapshot.py verify <arquivo.json>` compara o
  snapshot salvo com o estado atual e retorna código de saída 1, listando
  até 50 arquivos alterados, se algo mudou.

O snapshot de referência do projeto vive em
`.superpowers/sdd/2026-09-21-fias-ed-shared/fias_sources_before.json`
(Ruling 1 dos global-constraints). É a evidência usada para confirmar o
critério de aceite 9 do spec: nenhum arquivo alterado em `experimentos\` ou
em `avalie-seu-professor\` durante o desenvolvimento deste subprojeto.
