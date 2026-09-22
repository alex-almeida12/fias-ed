# FIAS (`rules/fias_rules.json`)

Este documento explica, para o pesquisador e para quem mantém o código, o
que `fias_rules.json` contém, cada regra/índice com fórmula, fonte e status,
e como alterá-lo com segurança. Fundamentação científica completa: ver
`RESEARCH_INVENTORY.md` §2.

## O que o arquivo contém

`fias_rules.json` (`rules_version: "1.0.0"`) tem cinco blocos:

1. `coding` — intervalo de codificação (segundos).
2. `aggregation` — como um segmento de fala vira um intervalo codificado.
3. `matrix` — como a matriz de transições 10×10 é montada.
4. `classifier` — como o BERTimbau é lido e restrito por papel.
5. `categories` — as 10 categorias FIAS, com nome canônico e aliases.
6. `indices` — os índices derivados (habilitados e desabilitados).

## Categorias

Nomes canônicos de CAP4 Tab. `tab:art2-categorias-fias` (l.37–46, "Adaptado
de Flanders 1970"); grupos de CAP4 l.26 (`validated`):

| Cat | Nome canônico | Grupo | Influência | Aliases registrados |
|---|---|---|---|---|
| 1 | Aceita sentimentos | professor | indireta | Aceita Sentimentos |
| 2 | Elogia ou encoraja | professor | indireta | — |
| 3 | Aceita ou usa ideias | professor | indireta | Aceita ou Utiliza Ideias dos Alunos, Aceita/Utiliza Ideias |
| 4 | Faz perguntas | professor | indireta | Faz Perguntas |
| 5 | Expõe | professor | direta | Expõe/Explica, Expõe (lecture) |
| 6 | Dá instruções | professor | direta | Dá Direções |
| 7 | Critica ou justifica autoridade | professor | direta | Critica/Autoridade, Critica ou Justifica Autoridade |
| 8 | Resposta do aluno | aluno | — | Resposta do Aluno |
| 9 | Iniciativa do aluno | aluno | — | Iniciativa do Aluno |
| 10 | Silêncio ou confusão | silêncio | — | Silêncio/Confusão, Silêncio ou Confusão |

## Protocolo de codificação e agregação

`coding.interval_seconds = 3` (CAP4 l.56, `validated`) — a codificação FIAS
opera em intervalos de 3 s.

`aggregation`: o classificador é turn-level (opera por turno de fala); para
reagrupar em intervalos de 3 s, o `fias_ed_engine` usa
`method: "largest_coverage"` (o intervalo recebe a categoria do segmento que
cobre a maior fração dele), `tie_break: "earliest_start"` (em empate, vence o
segmento que começa antes) e `gap_category: 10` (intervalo sem nenhum
segmento de fala vira categoria 10, silêncio). Essa regra de agregação **não
está definida em nenhuma fonte primária** (inventário item 11) —
`validation_status: PENDING_SCIENTIFIC_VALIDATION`. É uma decisão de
implementação necessária para o motor funcionar; o pesquisador deve revisá-la
frente a Flanders (1970) antes de publicar resultados baseados nela.

## Matriz de transições

`matrix.pad_category = 10`: "Convenciona-se acrescentar 10 no início e no fim
da sequência" (CAP4 l.52, l.279, `validated`). A matriz 10×10 conta, na
célula `(i, j)`, quantas vezes a categoria `i` foi seguida pela categoria
`j`, incluindo as transições de/para a categoria de preenchimento nas bordas
da sequência.

## Mapeamento do classificador

- `classifier.logit_index_offset = 1`: categoria FIAS = argmax(logits) + 1.
  Reconstruído de `build_label_info` em
  `experimentos/scripts/experimento_fias_ed_bert_ptbr.py`; verificado em 100%
  do TSV de teste (`validated`, ver `ANALISE_MODELOS_EXISTENTES.md`).
- `classifier.input_format = "pair:previous_turn,current_turn"`: `text_a` =
  turno anterior, `text_b` = turno atual.
- `classifier.max_length = 256`, `padding = "max_length"`.
- `classifier.token_type_ids = "zeros"`: decisão de engenharia (accuracy
  0,7915 vs 0,7773 com segmentos, n=211) — ver `ANALISE_MODELOS_EXISTENTES.md`
  §2.5.
- `classifier.uncertain_below = 0.5`: limiar de confiança abaixo do qual a
  predição é marcada `uncertain` para destaque na revisão humana.
- **Restrição por papel** (`role_categories`): `PROFESSOR → [1..7]`,
  `ALUNO → [8, 9]`. O papel do falante já é conhecido (o professor confirma a
  própria voz na revisão de falantes), então o argmax final é restrito às
  categorias do papel. São salvos `pred_raw` (argmax sobre as 10 categorias)
  e `pred_role_constrained` (argmax restrito). A taxa de divergência entre os
  dois é registrada em `Processamento.role_divergence_rate` (ver
  `SCIENTIFIC_REPRODUCIBILITY.md`). `validation_status:
  engineering_decision` — é uma restrição imposta pela engenharia do
  sistema, não uma afirmação da fonte científica.

Todo o bloco `classifier` está marcado `engineering_decision`, porque combina
decisões de implementação (zeros em `token_type_ids`, limiar 0,5, restrição
por papel) com um fato reconstruído dos scripts de experimento
(`logit_index_offset`).

## Índices

| id | Nome | Fórmula | Fonte | Status |
|---|---|---|---|---|
| `TT` | Fala docente | (cat. 1–7) / total de intervalos | SIMB l.4-15; CAP4 l.279 | validated |
| `PT` | Fala discente | (cat. 8–9) / total de intervalos | SIMB l.4-15; CAP4 l.279 | validated |
| `SC` | Silêncio ou confusão | (cat. 10) / total de intervalos | SIMB l.4-15; CAP4 l.279 | validated |
| `ID_RATIO` | Razão influência indireta/direta (I/D) | (cat. 1+2+3+4) / (cat. 5+6+7) | SIMB l.4-15 (r_id); CAP4 l.279 | validated |
| `PIR` | Razão de iniciativa discente | (cat. 9) / (cat. 8+9) | SIMB l.4-15 | validated |
| `PUPIL_RESPONSE_RATIO` | Razão de resposta discente | (cat. 8) / (cat. 8+9) | SIMB l.4-15 | validated na definição — ver divergência de sigla abaixo |
| `ID_REVISED` | Razão I/D revisada | não definida | CAP4 l.279 (citada, sem fórmula) | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |
| `TRR` | Razão de resposta docente | numerador = cat. 1+2+3; denominador ("fala docente reativa") não definido | SIMB l.4-15 | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |
| `I_A` | Índice de Acolhimento | cat. 1+2+3 / — | SIMB (só lista de símbolos) | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |
| `I_E` | Índice de Estímulo ao Raciocínio | cat. 4 / — | SIMB (só lista de símbolos) | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |
| `I_C` | Índice de Controle | cat. 5+6+7 / — | SIMB (só lista de símbolos) | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |
| `I_P` | Índice de Protagonismo Discente | cat. 8+9 / — | SIMB (só lista de símbolos) | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |
| `R_PA` | Razão de fala professor/aluno | não definida | SIMB (sem definição) | PENDING_SCIENTIFIC_VALIDATION, `enabled: false` |

Divisão por zero: todo índice usa `value: null` com `reason:
"insufficient_data"` quando o denominador é zero — nunca `0` nem infinito.
Todo índice é emitido com `evidence` (`n_intervals`, `n_segments`,
`mean_confidence`).

### Divergência da sigla PTR

SIMB usa a sigla "PTR" (Pupil Talk Ratio) para a fórmula cat. 8 / (cat. 8+9)
— mas essa sigla, tomada literalmente, sugeriria uma razão de fala do aluno
em geral (o que já é o papel de `PT`). `fias_rules.json` resolve a
ambiguidade adotando o id `PUPIL_RESPONSE_RATIO`, que segue a definição
textual da fórmula em vez da sigla; a observação da regra registra explicitamente:
"SIMB usa a sigla PTR (Pupil Talk Ratio), que diverge da definição; o id
adotado segue a definição." Esta é uma `engineering_decision` de
nomenclatura, não uma redefinição da fórmula em si (a fórmula continua
`validated`).

## Como alterar

1. Editar `rules/fias_rules.json` (categorias, índices ou parâmetros do
   classificador), sempre com `source_reference` e `validation_status`
   corretos para qualquer campo novo ou alterado.
2. Subir `rules_version` (semver) no arquivo alterado.
3. Regenerar os casos de conformidade: `engine-py/.venv/Scripts/python
   scripts/generate_conformance.py` (a partir de `fias-ed-shared/`).
4. Rodar a suíte de testes: `engine-py/.venv/Scripts/python -m pytest`
   (a partir de `fias-ed-shared/engine-py/`).
5. Confirmar que `test_rules.py`, `test_conformance.py` e `test_docs.py`
   continuam verdes, e que nenhuma regra ficou sem `source_reference` (ver
   `traceability.find_untraced`, documentado em
   `SCIENTIFIC_TRACEABILITY.md`).
