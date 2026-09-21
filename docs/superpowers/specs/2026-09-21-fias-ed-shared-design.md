# Spec — Subprojeto 1: `fias-ed-shared`

Data: 2026-09-21
Autor da solicitação: Alex Almeida do Amaral (PPgCC UFERSA/UERN)
Status: aguardando revisão do pesquisador

---

## 0. Contexto e decomposição

O FIAS-ED foi decomposto em três subprojetos, cada um com spec → plano →
implementação próprios, nesta ordem:

1. **`fias-ed-shared`** (este documento) — base científica, regras, schemas,
   motor de referência, design tokens e documentação.
2. `fias-ed-web` — FastAPI + PostgreSQL + pipeline de áudio + React.
3. `fias-ed-android` — Kotlin/Compose offline, reutilizando shared + ONNX.

Repositório: monorepo Git em `Documents\mestrado\sistemas\` contendo as três
pastas. Os experimentos em `artigos selecionados\experimentos\` e o sistema
`avalie-seu-professor` **não são modificados** — são fontes somente leitura.

Implantação alvo do Web (decidida): PC local do pesquisador, Docker Compose,
acesso via navegador na máquina/rede local, sem exposição à Internet.

## 1. Objetivo

Fornecer uma fonte única, versionada e rastreável das regras científicas
(FIAS, QTI-24, triangulação, MTSS Tier 1, sugestões pedagógicas), do modelo
lógico de dados e da identidade visual, de modo que Web (Python) e Android
(Kotlin) produzam **exatamente os mesmos resultados** a partir das mesmas
entradas.

Abordagem escolhida: **regras declarativas em JSON + JSON Schema + vetores de
conformidade compartilhados**, com um motor de referência em Python. Motores
multiplataforma (KMP/Rust) foram descartados por custo de build; regras apenas
no servidor foram descartadas por violar o requisito offline do Android.

## 2. Estrutura

```
fias-ed-shared/
├── rules/
│   ├── fias_rules.json
│   ├── qti_config.json          (gerado a partir do avalie-seu-professor)
│   ├── mtss_rules.json
│   └── pedagogical_rules.json
├── schemas/                     JSON Schema (draft 2020-12)
│   ├── rules/*.schema.json      um por arquivo de regras
│   └── entities/*.schema.json   entidades do modelo lógico
├── conformance/                 casos entrada → saída esperada
├── scientific-config/
│   ├── models.json              registro de modelos (hash, origem, licença, métricas)
│   └── metric_targets.json      metas WER/DER/κ/F1… com fonte
├── design-tokens/
│   ├── tokens.json              fonte única
│   └── build/                   tokens.css, FiasTokens.kt (gerados)
├── engine-py/                   pacote `fias_ed_engine` (motor de referência)
├── scripts/                     extração do QTI, geração de tokens, verificação de hashes
└── docs/
```

## 3. Metadados obrigatórios de rastreabilidade

Todo arquivo de regras tem `rules_version` (semver; início `1.0.0`). Toda regra,
índice ou parâmetro tem:

- `source_reference` — arquivo + seção/linha da fonte (ex.: `CAP4 l.279`,
  `SIMB l.4–15`, `avalie-seu-professor/src/domain/qti/qtiWeights.ts`);
- `validation_status` ∈
  - `validated` — explícito em fonte citada;
  - `PENDING_SCIENTIFIC_VALIDATION` — citado mas não definido, ou proposto sem
    fonte primária;
  - `engineering_decision` — escolha de implementação, não afirmação científica;
  - `draft_pending_researcher_review` — texto redigido pelo desenvolvedor,
    aguardando revisão do pesquisador;
- `enabled` (bool) — regras PENDING com cortes normativos ficam `false`.

Abreviações de fonte (definidas em `docs/SCIENTIFIC_TRACEABILITY.md`):
CAP4 = `Dissertacao Qualificação/2-textuais/4-artigo-fias-ed.tex`;
CAP5 = `.../5-validacao.tex`; SIMB = `.../1-pre-textuais/lista-de-simbolos.tex`;
FU = `Formas_de_Uso_Tier1.docx`; CEP = `Projeto_CEP_UERN_FIAS-ED.docx`.

## 4. FIAS (`fias_rules.json`)

### 4.1 Categorias

Nomes canônicos da Tabela `tab:art2-categorias-fias` (CAP4 l.37–46, adaptado
de Flanders 1970). Variantes do dataset/experimentos registradas em `aliases`.

| Cat | Nome canônico | Grupo | Aliases |
|---|---|---|---|
| 1 | Aceita sentimentos | professor · indireta | Aceita Sentimentos |
| 2 | Elogia ou encoraja | professor · indireta | |
| 3 | Aceita ou usa ideias | professor · indireta | Aceita ou Utiliza Ideias dos Alunos |
| 4 | Faz perguntas | professor · indireta | |
| 5 | Expõe | professor · direta | Expõe/Explica |
| 6 | Dá instruções | professor · direta | Dá Direções |
| 7 | Critica ou justifica autoridade | professor · direta | |
| 8 | Resposta do aluno | aluno | |
| 9 | Iniciativa do aluno | aluno | |
| 10 | Silêncio ou confusão | silêncio | |

Grupos: CAP4 l.26 (`validated`).

### 4.2 Mapeamento do classificador

- Modelo: BERTimbau base fine-tuned (Frente 3), `BertForSequenceClassification`,
  10 saídas; `config.json` tem apenas `LABEL_0..9`.
- **Categoria FIAS = índice do logit + 1** (reconstruído de
  `build_label_info` em `scripts/experimento_fias_ed_bert_ptbr.py`; verificado em
  100% do test TSV). `validated`.
- Entrada: par `(text_a = turno anterior, text_b = turno atual)`, tokenizer
  WordPiece cased do próprio checkpoint, `max_length=256`, truncation, padding
  fixo 256, **`token_type_ids` todos zero** (fiel ao treino; acc 0,7915 vs
  0,7773 com segmentos, n=211). `engineering_decision` documentada.
- Confiança = softmax(logits)[pred]. Limiar de "incerto" para destaque na
  revisão: parâmetro `uncertain_below`, valor inicial 0,50,
  `engineering_decision`.
- **Restrição por papel**: o papel do falante é conhecido (professor confirma a
  própria voz). Salvam-se `pred_raw` (argmax sobre 10) e `pred_role_constrained`
  (argmax restrito a 1–7 para PROFESSOR, 8–9 para ALUNO). O relatório usa a
  restrita; a taxa de divergência raw × restrita é registrada no
  `Processamento`. `engineering_decision`.
- Silêncio: intervalos sem segmento de fala recebem categoria 10 por regra
  (coerente com o treino, onde cat. 10 = `text_b` vazio). `engineering_decision`.

### 4.3 Unidade de codificação e matriz

- Intervalos de 3 s (CAP4 l.56, `validated`).
- Agregação turno → intervalo: o intervalo recebe a categoria do segmento que
  cobre a maior fração dele; sem fala → 10; empate → segmento que inicia antes.
  `PENDING_SCIENTIFIC_VALIDATION` (regra não definida nas fontes).
- Matriz de transições 10×10, com 10 acrescentado no início e no fim da
  sequência (CAP4 l.52, l.279, `validated`).

### 4.4 Índices

| id | Definição | Status |
|---|---|---|
| `TT` | % intervalos em 1–7 | validated (SIMB; Flanders 1970) |
| `PT` | % intervalos em 8–9 | validated |
| `SC` | % intervalos em 10 | validated |
| `ID_RATIO` | (1+2+3+4)/(5+6+7) | validated (SIMB) |
| `PIR` | 9/(8+9) | validated (SIMB) |
| `PUPIL_RESPONSE_RATIO` | 8/(8+9) | validated na definição; sigla "PTR" em SIMB diverge do nome — documentado |
| `ID_REVISED`, `TRR` | denominador não definido nas fontes | PENDING, `enabled=false`, não calculado |
| `I_A`, `I_E`, `I_C`, `I_P`, `r_pa` | só na lista de símbolos | PENDING, `enabled=false` |

Divisão por zero → valor `null` com motivo `insufficient_data` (nunca 0 ou ∞).
Todo índice é emitido com `evidence`: n de intervalos, n de segmentos,
confiança média das classificações usadas.

## 5. QTI-24 (`qti_config.json`)

- **Fonte canônica**: `avalie-seu-professor/src/domain/qti/qtiItems.ts`
  (textos congelados, SHA-256 `5d0105f3b1a355be1c4112a1d1f538566a7e380ee46ef78fceef187b2c56bcb6`),
  `QtiOctant.ts`, `qtiWeights.ts`, `likertScale.ts`.
- `scripts/extract_qti.py` gera o JSON a partir desses arquivos e grava origem
  + hash de cada um. O JSON nunca é editado à mão. O teste de conformidade falha
  se texto, posição ou octante divergir da fonte.
- Conteúdo: 24 itens, tronco "Este(a) professor(a)…", Likert 1–5 com âncoras
  extremas, octantes oc1{1,9,17} … oc8{8,16,24} com os rótulos do sistema
  (Liderança, Amigável, Compreensivo, Dá Liberdade, Inseguro, Insatisfeito,
  Irritável, Rigoroso), `oc_k = (média−1)/4`, AGENCY e COMMUNION com
  `a=0.923880`, `b=0.382683` (manual VIL-24, jan. 2013).
- Agregado da turma = média entre respondentes. Mínimo para exibir:
  `min_responses = 10` (`engineering_decision`, herdado do sistema).
- Divergência de rótulos com a dissertação (Incerto/Inseguro,
  Admoestador/Irritável) documentada em `docs/QTI.md`.
- `validation_status` do instrumento: `PENDING_SCIENTIFIC_VALIDATION`
  (adaptação transcultural não concluída; autorização de Wubbels pendente —
  registrado em `docs/QTI.md`).
- Entradas suportadas (esquema único `RespostaQTI`): importação do dataset
  exportado pelo `avalie-seu-professor`, formulário, digitação manual, OCR de
  folha impressa. Toda entrada não-importada passa por confirmação humana.

## 6. Triangulação

- Baseada nos três planos de CAP4 §`subsec:art2-triangulacao` (Fisher 1995):
  convergência, divergência reveladora, complementaridade.
- **Não há classificação automática** do plano (não existe algoritmo nem
  definição de "alto/baixo" nas fontes).
- `pedagogical_rules.json` define **pares conceituais** FIAS ↔ QTI, todos
  `PENDING_SCIENTIFIC_VALIDATION`:
  - cat. 2+3 ↔ Amigável, Compreensivo;
  - `ID_RATIO` ↔ Liderança, Rigoroso;
  - cat. 8+9 / `PIR` ↔ Dá Liberdade;
  - cat. 7 ↔ Irritável, Insatisfeito.
- Saída por par: valores FIAS + valores QTI + evidências + uma pergunta de
  reflexão (texto `draft_pending_researcher_review`).

## 7. MTSS Tier 1 (`mtss_rules.json`)

Esquema de regra:

```json
{
  "rule_id": "MTSS_001",
  "rules_version": "1.0.0",
  "tier1_dimension": "Ensino explícito (modelagem)",
  "conditions": { "all": [ { "fact": "modal_teacher_category", "op": "eq", "value": 5 } ] },
  "evidence": ["ID_RATIO", "TT", "segments:category=5"],
  "interpretation": "Este padrão pode indicar …",
  "recommendation_ids": ["PED_005_a"],
  "source_reference": "CAP4 tab:art2-fias-tier1",
  "validation_status": "PENDING_SCIENTIFIC_VALIDATION",
  "enabled": true
}
```

- Condições **descritivas** somente: categoria docente modal, `ID_RATIO < 1`
  (fato aritmético: direta > indireta), ausência de cat. 9, presença de cat. 7
  em N intervalos, etc. Operadores: `eq, ne, lt, lte, gt, gte, present,
  absent`; combinadores `all/any`.
- Correspondência categoria → dimensão Tier 1 da Tab. `tab:art2-fias-tier1`
  (CAP4 l.137–146): proposta do autor, `PENDING`, **ativa** (núcleo do
  framework).
- Cortes de FU (I/D 0,40/0,70; fala discente < 25%; ≥60% indiretos; ≥80%;
  ≥70%) presentes com `enabled: false`, `threshold_pending_validation: true`.
- Proibido emitir "conforme / parcialmente conforme / não conforme", notas,
  cores de semáforo ou qualquer rótulo de desempenho.
- Toda regra disparada inclui evidências: índices usados + trechos de
  transcrição (segmento, timestamp) que sustentam o padrão.

## 8. Sugestões (`pedagogical_rules.json`)

- Textos ligados às dimensões Tier 1, na forma "Considere… / Você pode
  experimentar… / Uma possibilidade é… / Este padrão pode indicar…".
- Lista de expressões proibidas validada por teste ("errado", "ruim",
  "inadequado", "nota", "desempenho", "fracasso", "deveria ter").
- Todos `draft_pending_researcher_review`; o relatório exibe em Informações
  Técnicas que as sugestões estão em versão preliminar. **O pesquisador revisa
  antes do estudo de caso.**

## 9. Modelo lógico de dados (`schemas/entities/`)

Campos comuns: `id` (UUIDv7), `created_at`, `updated_at`, `deleted_at`,
`version`, `sync_status` (LOCAL_ONLY | PENDING_SYNC | SYNCED | CONFLICT),
`device_id`. Sincronização não implementada; apenas preparada.

Entidades: Professor, Escola, Turma, Disciplina, Aula, Audio, Transcricao,
Segmento, Falante, ClassificacaoFIAS, IndicadorFIAS, QuestionarioQTI,
RespostaQTI, ResultadoQTI, Triangulacao, ResultadoMTSS, Recomendacao,
Relatorio, Processamento, ModeloIA.

Pontos específicos:

- **Audio**: `path`, `sha256`, `size`, `duration`, `mime_type`,
  `original_filename`, `internal_filename` (UUID), `channels`, `sample_rate`.
  Sem BLOB. Original imutável; cópias de trabalho separadas e descartáveis.
- **Falante**: apenas rótulo de diarização + papel (PROFESSOR/ALUNO). Nenhum
  embedding de voz persistido.
- **Segmento**: `start_ms`, `end_ms` globais, `texto_original_asr`,
  `texto_revisado`, `revisado`.
- **ClassificacaoFIAS**: `segmento_id`, `transcript_source`
  (ASR_ORIGINAL | TRANSCRICAO_REVISADA), `pred_raw`, `pred_role_constrained`,
  `confidence`, `model_version`.
- **Aula.status**: DRAFT, AUDIO_IMPORTED, AUDIO_VALIDATED, PREPROCESSING,
  TRANSCRIBING, TRANSCRIBED, DIARIZING, READY_FOR_SPEAKER_REVIEW,
  READY_FOR_TRANSCRIPT_REVIEW, READY_FOR_FIAS, FIAS_COMPLETED, WAITING_QTI,
  QTI_COMPLETED, TRIANGULATED, MTSS_INTERPRETED, REPORT_READY, ERROR.
- **Processamento** (reprodutibilidade): app_version, rules_version,
  asr_model/hash, diarization_model, fias_model/hash, parameters, hardware,
  device, audio_duration, processing_time por etapa, created_at,
  transcript_source, taxa de divergência raw × restrita.

## 10. Registro de modelos (`scientific-config/models.json`)

Artefatos referenciados por caminho em `experimentos\` + SHA-256; **não
copiados para o Git**, não retreinados:

| Artefato | Caminho | SHA-256 |
|---|---|---|
| BERTimbau safetensors (Web) | `resultados_bert_ptbr/frente3_ptbr/melhor_modelo/model.safetensors` | `625d32a2…42ded` |
| tokenizer.json | idem | `b22b95ac…9466` |
| tokenizer_config.json | idem | `a350de5e…378d` |
| config.json | idem | `e43872df…5279` |
| BERTimbau ONNX int8 (Android) | `mobile_deploy/bertimbau/model_int8.onnx` | `cdeb8ccb…abcd4` |

(hashes completos no JSON). Inclui métricas (F1 macro 0,7246; acc 0,8231;
κ 0,7698; A06: 713 ms/turno, 182 MB), licenças (TalkMoves CC BY-NC-SA 4.0 →
uso não comercial; BERTimbau MIT) e limitações (seleção do melhor checkpoint
no conjunto de teste; domínio: aulas de matemática dos EUA traduzidas).
Arquivos pickle (`training_args.bin`, `*.pt`, `*.pth`) são listados como
**proibidos de carregar**. `scripts/verify_models.py` confere hashes e recusa
divergência.

## 11. Motor de referência (`engine-py`, pacote `fias_ed_engine`)

Python 3.11+, sem dependências pesadas (sem torch). API pura:

- `load_rules(path) -> Rules` (valida contra JSON Schema)
- `segments_to_intervals(segments, interval_s=3) -> list[int]`
- `transition_matrix(intervals) -> 10×10`
- `compute_indices(intervals, rules) -> dict[id, IndexResult]`
- `constrain_by_role(logits, role) -> (pred_raw, pred_constrained, confidence)`
- `score_qti(responses, qti_config) -> ResultadoQTI`
- `triangulate(indices, qti_result, rules) -> list[TriangulationPair]`
- `evaluate_mtss(facts, mtss_rules) -> list[FiredRule]`
- `recommendations(fired, pedagogical_rules) -> list[Recomendacao]`

Testes: pytest cobrindo cada função + execução de todos os casos de
`conformance/`. O motor Kotlin (subprojeto 3) roda os mesmos casos.

## 12. Conformance (`conformance/`)

Casos JSON `{ "id", "description", "input", "expected" }` para: agregação em
intervalos (incluindo empates e silêncios), matriz, cada índice (incluindo
divisão por zero), restrição por papel, pontuação QTI (valores conferidos
contra o `avalie-seu-professor`), triangulação, disparo de cada regra MTSS
habilitada, e textos QTI idênticos à fonte. Constitui o
`schema_compatibility_test` (Aula, FIAS, QTI, MTSS, Relatório).

## 13. Design tokens e identidade

- `tokens.json` → `tokens.css` (Web) e `FiasTokens.kt` (Compose) por script.
- Paleta oficial exata: Navy #2F4156, Teal #567C8D, Sky Blue #C8D9E6,
  Beige #F5EFEB, White #FFFFFF. Regras de contraste (WCAG):
  Navy sobre branco 10,4:1 (texto livre); Teal sobre branco 4,5:1 (links,
  ícones, texto ≥14 px medium); Teal sobre Beige ≈3,9:1 (proibido para texto);
  Sky Blue só como superfície. Cores semânticas (erro, sucesso, atenção,
  informação) dessaturadas, cada uma verificada AA; o script de tokens falha se
  algum par declarado como "texto" ficar abaixo de 4,5:1.
- Gráficos FIAS: cores por bloco (indireta, direta, aluno, silêncio) derivadas
  da paleta.
- Fontes locais: Ubuntu (Ubuntu Font Licence) e Rokkitt (OFL), WOFF2 no Web,
  `res/font` no Android. `--font-interface`, `--font-editorial`;
  `FIASTypography`. Rokkitt proibida em tabelas, inputs e números pequenos.
- Estilo: raio 4–6 px, bordas finas, sombras mínimas, sem gradientes, glow,
  glassmorphism, ícones de IA ou sparkles.

## 14. Documentação entregue neste subprojeto

Em `fias-ed-shared/docs/`: RESEARCH_INVENTORY.md, ANALISE_MODELOS_EXISTENTES.md,
MODELS.md, FIAS.md, QTI.md, MTSS.md, SCIENTIFIC_TRACEABILITY.md,
SCIENTIFIC_REPRODUCIBILITY.md, DATABASE_MODEL.md, ENTITY_DICTIONARY.md,
PRIVACY.md, DESIGN_SYSTEM.md, UI_REFERENCES.md, FUTURE_SYNC.md,
FUTURE_SYNC_API.md. Na raiz de `sistemas/`: README.md e ARCHITECTURE.md
(visão dos três subprojetos).

Documentos dos subprojetos 2 e 3 (PIPELINE.md, OFFLINE_FIRST.md,
ANDROID_DIARIZATION_FEASIBILITY.md, ANDROID_BENCHMARK.md, SECURITY_AUDIT.md,
FINAL_SECURITY_CHECK.md) ficam para seus respectivos specs.

Conteúdo obrigatório de ANALISE_MODELOS_EXISTENTES.md: mapa de rótulos,
formato de entrada, discrepância de `token_type_ids` (0,7773 → 0,7915),
padding fixo, ausência de conjunto de validação separado, riscos de domain
shift, licenças, arquivos pickle.

UI_REFERENCES.md: ≥10 referências de fontes públicas (Dribbble, Behance,
Land-book, Awwwards, SaaSFrame, sites de produtos educacionais/científicos),
cada uma com nome, URL, tela, elemento relevante, inspiração, o que não
copiar. Mobbin/Refero/Figma exigem login: registrados como não consultados.

PRIVACY.md: dados coletados, finalidade, localização, retenção (5 anos, CEP),
acesso (pesquisador e orientador; professor vê só as próprias aulas),
exclusão real de áudio/transcrição, pseudonimização por NER antes de
exportar (etapa opcional, PENDING), exportação. Sem inventar base legal;
cita apenas TCLE e projeto CEP. Registra as divergências encontradas
(UFERSA × UERN; princípios AIED Unplugged CAP4 × CEP; modo cloud não coberto
pelos termos).

## 14A. Exportação do dataset da(s) aula(s)

Requisito do pesquisador (2026-09-21): exportar o dataset de uma ou mais
aulas. O **formato** é definido aqui (schema + função de referência), para que
Web e Android exportem exatamente o mesmo conteúdo; a tela de exportação fica
nos subprojetos 2 e 3.

- Entrada: uma ou mais aulas (segmentos classificados, respostas QTI,
  metadados de processamento). O motor recalcula intervalos, matriz, índices,
  QTI, MTSS, sugestões e triangulação com as mesmas funções da conformidade.
- Tabelas: `lessons`, `segments`, `intervals`, `matrix`, `indices`,
  `qti_responses` (q1..q24 por resposta, sem dados sociodemográficos),
  `qti_results`, `mtss`, `recommendations`, `triangulation` e `manifest`.
- Formatos: JSON único (validado por `schemas/export/lesson_dataset.schema.json`)
  e ZIP com um CSV por tabela, mais `manifest.json` com SHA-256 de cada CSV.
- **Privacidade**:
  - Por padrão, **sem texto das falas**.
  - A opção `include_text` exporta apenas `text_pseudonymized`: nomes próprios
    substituídos por `[NOME]`, produzido pela etapa de NER do app. Se algum
    segmento não tiver versão pseudonimizada, a exportação é recusada.
  - Nunca exporta áudio, caminhos de arquivo, nome do professor, nome da turma,
    `texto_original_asr` nem dados de login.
  - A turma aparece só pelo UUID; a disciplina aparece pelo nome.
- `manifest` registra `export_version`, `rules_version`, opções usadas,
  quantidade de aulas, modelos e hashes (do `Processamento`) e data da
  exportação, para reprodutibilidade.

## 15. Fora do escopo deste subprojeto

API, banco físico, pipeline de áudio (ASR, diarização, OCR), telas, app
Android, auditorias de segurança de aplicação, benchmarks. Revisões com
Impeccable acontecem sobre telas reais (subprojeto 2); o plugin precisa ser
instalado pelo usuário (`npx impeccable install --global --providers=claude -y`).

## 16. Critérios de aceite

1. `pytest` verde em `engine-py`, incluindo 100% dos casos de `conformance/`.
2. Todos os JSON de `rules/` validam contra seus schemas.
3. Nenhuma regra/índice sem `source_reference` e `validation_status` (teste).
4. `qti_config.json` idêntico à fonte congelada (teste de hash + textos).
5. `verify_models.py` confirma os 5 hashes do registro.
6. Script de tokens gera CSS e Kotlin; teste de contraste passa.
7. Teste de linguagem: nenhuma expressão proibida em interpretações e sugestões.
8. Documentos da Seção 14 presentes, sem afirmações sem fonte.
9. Nenhum arquivo alterado em `experimentos\` ou `avalie-seu-professor\`
   (conferido por hash antes/depois).
10. Exportação: JSON valida contra o schema; ZIP tem um CSV por tabela com
    hashes no manifest; sem `include_text` não há texto; com `include_text`
    e segmento sem pseudonimização → recusa.

## 17. Pendências científicas que dependem do pesquisador

1. Fórmulas de i/d revisada e TRR (Flanders 1970).
2. Critérios por aula do Tier 1 e faixa de referência de I/D.
3. Regra de agregação turno → intervalo de 3 s.
4. Pareamento FIAS ↔ QTI da triangulação.
5. Revisão dos textos de interpretação e sugestões.
6. Validação da tradução do QTI-24 e autorização de uso.
7. Unificação do mapeamento TalkMoves → FIAS (três versões divergentes).
