# Rastreabilidade científica

Todo objeto científico do FIAS-ED (regra, índice, item, parâmetro) declara de
onde vem (`source_reference`) e qual seu grau de confirmação
(`validation_status`). Este documento explica as siglas de fonte, o
significado de cada `validation_status`, como a cobertura é garantida por
código, e traz a matriz regra → fonte montada manualmente a partir dos
arquivos de `rules/`.

## Tabela de abreviações de fonte

| Sigla | Caminho completo |
|---|---|
| CAP4 | `artigos selecionados/Dissertacao Qualificação/2-textuais/4-artigo-fias-ed.tex` |
| CAP5 | `artigos selecionados/Dissertacao Qualificação/2-textuais/5-validacao.tex` |
| SIMB | `artigos selecionados/Dissertacao Qualificação/1-pre-textuais/lista-de-simbolos.tex` |
| PQTI | `Adaptação para o Português Brasileiro do Questionário sobre a Interação do Professor (QTI)/01_Projeto_Revisado/Projeto_de_Pesquisa_Revisado.docx` |
| SIS | `Adaptação...QTI/sistema/avalie-seu-professor/` |
| CEP | `artigos selecionados/Projeto_CEP_UERN_FIAS-ED.docx` |
| FU | `artigos selecionados/Formas_de_Uso_Tier1.docx` |

Referências para arquivos de experimento (fora do padrão de siglas acima)
usam caminho relativo a `artigos selecionados/experimentos/`, por exemplo
`experimentos/scripts/experimento_fias_ed_bert_ptbr.py` ou
`experimentos/DOCUMENTACAO_EXPERIMENTOS.md §2`.

## Significado de cada `validation_status`

| Valor | Significado |
|---|---|
| `validated` | Explícito em fonte citada — a fórmula, valor ou definição aparece literalmente (ou é reconstrução verificada, como o mapa índice→categoria do classificador) na fonte referenciada. |
| `PENDING_SCIENTIFIC_VALIDATION` | Citado, mas não definido pela fonte; ou proposto (por FU ou pelo desenvolvimento) sem fonte primária. Requer decisão do pesquisador antes de ser tratado como resultado científico. |
| `engineering_decision` | Escolha de implementação necessária para o sistema funcionar (ex.: `token_type_ids = zeros`, restrição por papel, agregação turno→intervalo), não uma afirmação científica em si. |
| `draft_pending_researcher_review` | Texto (interpretação, sugestão, pergunta de triangulação) redigido pelo desenvolvimento no vocabulário formativo exigido, aguardando revisão do pesquisador antes de uso em estudo de caso. |

Regras `PENDING_SCIENTIFIC_VALIDATION` que carregam um corte numérico
normativo (ex.: os quatro cortes de FU em `mtss_rules.json`) ficam também
`enabled: false` — ver `MTSS.md`.

## Como `find_untraced` garante a cobertura

`fias_ed_engine.traceability.find_untraced(obj)` percorre recursivamente
qualquer estrutura JSON (dict/list) carregada de `rules/*.json`. Um objeto
"precisa" de rastreabilidade quando contém qualquer uma das chaves
`source_reference`, `validation_status` ou `rule_id`, ou quando é um item de
uma lista e tem campo `id`. Para cada objeto que precisa, a função exige:

- `source_reference` é uma string não vazia (pelo menos 3 caracteres após
  remover espaços);
- `validation_status` pertence ao conjunto de quatro valores válidos listado
  acima.

Se qualquer condição falhar, o caminho do objeto (ex.:
`$.indices[7]`) é adicionado à lista de retorno. A suíte de testes do
`fias_ed_engine` chama essa função sobre todo o conteúdo de `rules/` e falha
se a lista não estiver vazia — é assim que o critério de aceite 3 do spec
("Nenhuma regra/índice sem `source_reference` e `validation_status`") é
verificado automaticamente, e não apenas por revisão manual.

## Matriz regra → fonte

Montada manualmente a partir dos arquivos JSON de `rules/` (não gerada por
script); deve ser conferida a cada `rules_version` nova.

### `fias_rules.json`

| Campo | Fonte | Status |
|---|---|---|
| `coding.interval_seconds` | CAP4 l.56 | validated |
| `aggregation.*` | Spec §4.3 (inventário item 11) | PENDING_SCIENTIFIC_VALIDATION |
| `matrix.pad_category` | CAP4 l.52, l.279 | validated |
| `classifier.*` | `experimento_fias_ed_bert_ptbr.py`; `ANALISE_MODELOS_EXISTENTES.md` §token_type_ids; spec §4.2 | engineering_decision |
| `categories[]` (10 itens) | CAP4 Tab. `tab:art2-categorias-fias` l.37-46; grupos CAP4 l.26 | validated |
| `indices.TT/PT/SC/ID_RATIO/PIR/PUPIL_RESPONSE_RATIO` | SIMB l.4-15; CAP4 l.279 | validated |
| `indices.ID_REVISED/TRR/I_A/I_E/I_C/I_P/R_PA` | SIMB (citados, sem fórmula ou sem uso) | PENDING_SCIENTIFIC_VALIDATION |

### `qti_config.json`

| Campo | Fonte | Status |
|---|---|---|
| `instrument.*` | `avalie-seu-professor/src/domain/qti/*`; README §Cálculo do QTI-24 | PENDING_SCIENTIFIC_VALIDATION |
| `octants[]` (8 itens, pesos) | `QtiOctant.ts`; `qtiWeights.ts` (manual VIL-24, jan. 2013) | validated |
| `items[]` (24 itens) | `qtiItems.ts` (textos congelados) | PENDING_SCIENTIFIC_VALIDATION |

### `mtss_rules.json`

| Grupo de regras | Fonte | Status |
|---|---|---|
| 9 regras descritivas (`MTSS_EXPOSITIVE_PREDOMINANCE` … `MTSS_QUESTIONS_PRESENT`) | CAP4 Tab. `tab:art2-fias-tier1` l.137-146 | PENDING_SCIENTIFIC_VALIDATION |
| 4 regras de corte de FU (`MTSS_FU_*`) | FU (Usos #2, #3, #9); CAP4 `tab:art2-resultados-esperados-sintese` l.408 | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |

### `pedagogical_rules.json`

| Campo | Fonte | Status |
|---|---|---|
| `recommendations[]` (9 itens) | Redigidas a partir das dimensões Tier 1 de CAP4 Tab. `tab:art2-fias-tier1` | draft_pending_researcher_review |
| `triangulation_pairs[]` (4 itens) | CAP4 `subsec:art2-triangulacao` l.350-371 (Fisher 1995); pareamento operacional proposto no spec §6 | PENDING_SCIENTIFIC_VALIDATION |

### `metric_targets.json`

| Campo | Fonte | Status |
|---|---|---|
| `WER`, `DER` | CAP5 `tab:val-criterios-sintese` (`"conforme literatura"`, sem citação) | PENDING_SCIENTIFIC_VALIDATION |
| `KAPPA_MODEL` | CAP5 `tab:val-criterios-sintese` | PENDING_SCIENTIFIC_VALIDATION |
| `KAPPA_HUMAN`, `F1_AXIS`, `OCR_ACCURACY`, `PIPELINE_COMPLETION`, `CLOUD_OFFLINE_DEGRADATION`, `SUS`, `TAM` | CAP5 `tab:val-criterios-sintese` | validated |

### `models.json`

| Campo | Fonte | Status |
|---|---|---|
| `fias-bertimbau-ptbr-frente3` e `-onnx-int8` (artefatos, métricas, licenças, limitações) | `experimentos/DOCUMENTACAO_EXPERIMENTOS.md` §2-4; `resultados.json`; `info_exportacao.json`; `benchmark_resultado_bertimbau_A06.json` | validated |
