# MTSS Tier 1 (`rules/mtss_rules.json`, `rules/pedagogical_rules.json`)

Este documento explica o que `mtss_rules.json` contém, cada regra com sua
condição e texto, por que os cortes de `Formas_de_Uso_Tier1.docx` (FU) estão
desligados, e a garantia de que o sistema nunca emite rótulos de
conformidade. Fundamentação completa: `RESEARCH_INVENTORY.md` §4.

## O que o MTSS Tier 1 significa aqui

O framework foca no **Tier 1** do MTSS (Multi-Tiered System of Supports):
meta de atender "aproximadamente 80% dos alunos" (CAP4 l.122–124,
vaughn2003redefining) através das variáveis sob responsabilidade docente
(stecker2005cbm, mandinach2021), antes de considerar intervenções de tiers
mais intensivos. O FIAS-ED não decide sobre tiers de estudantes individuais —
ele descreve padrões da aula inteira, como reflexão para o professor.

## Tab. `tab:art2-fias-tier1` (CAP4 l.137–146)

Correspondência categoria FIAS → dimensão Tier 1, "de autoria do autor
(2026), com base em Flanders, Nitz e Stecker":

| Cat. FIAS | Dimensão Tier 1 | Intensidade |
|---|---|---|
| 1 | Gestão proativa do clima de sala | Forte |
| 2 | Feedback formativo contingente | Forte |
| 3 | Engajamento e uptake dialógico | Forte |
| 4 | Engajamento cognitivo de alta demanda | Forte |
| 5 | Ensino explícito (modelagem) | Moderada |
| 6 | Gestão proativa de rotinas e transições | Moderada |
| 7 | Gestão reativa (sinal de fragilidade no Tier 1) | Negativa |
| 8 | Oportunidade de resposta estruturada | Forte |
| 9 | Engajamento ativo e voz discente | Forte |
| 10 | Indicador de fragilidade na fidelidade do Tier 1 | Diagnóstica |

## Cada regra: condição e texto

`mtss_rules.json` tem 13 regras. As 9 primeiras são condições descritivas
(fatos aritméticos sobre a aula, sem corte normativo) e ficam
`enabled: true`:

| rule_id | Dimensão Tier 1 | Condição | Enquadramento |
|---|---|---|---|
| `MTSS_EXPOSITIVE_PREDOMINANCE` | Ensino explícito (modelagem) | categoria docente modal = 5 | reflection |
| `MTSS_INSTRUCTIONS_PREDOMINANCE` | Gestão proativa de rotinas e transições | categoria docente modal = 6 | reflection |
| `MTSS_DIRECT_OVER_INDIRECT` | Engajamento e uptake dialógico | `ID_RATIO` < 1 (fato aritmético: direta > indireta) | reflection |
| `MTSS_NO_STUDENT_INITIATIVE` | Engajamento ativo e voz discente | cat. 9 = 0 e cat. 8 > 0 | reflection |
| `MTSS_NO_IDEA_UPTAKE` | Engajamento e uptake dialógico | cat. 3 = 0 e cat. 8 > 0 | reflection |
| `MTSS_NO_PRAISE` | Feedback formativo contingente | cat. 2 = 0 e cat. 8 > 0 | reflection |
| `MTSS_REACTIVE_MANAGEMENT_PRESENT` | Gestão reativa | cat. 7 > 0 | reflection |
| `MTSS_STUDENT_INITIATIVE_PRESENT` | Engajamento ativo e voz discente | cat. 9 > 0 | strength |
| `MTSS_QUESTIONS_PRESENT` | Engajamento cognitivo de alta demanda | cat. 4 > 0 | strength |

Cada regra ativa traz um `interpretation` no vocabulário formativo exigido
("Este padrão pode indicar…") e uma lista de `recommendation_ids`
(`pedagogical_rules.json`). Todas têm `source_reference` apontando para a Tab.
`tab:art2-fias-tier1` e `validation_status: PENDING_SCIENTIFIC_VALIDATION`,
porque a correspondência categoria↔dimensão é uma proposta do próprio
pesquisador, não uma tradução direta de uma fonte externa única (ver
`RESEARCH_INVENTORY.md` §4.1).

## Por que os cortes de FU estão `enabled: false`

`Formas_de_Uso_Tier1.docx` (FU) propõe 4 cortes numéricos, todos sem fonte
primária citada (apenas "literatura sobre Tier 1" genericamente):

| rule_id | Corte proposto por FU | Fonte FU |
|---|---|---|
| `MTSS_FU_ID_BAND_LOW` | `ID_RATIO` < 0,40 | Uso #2 |
| `MTSS_FU_ID_BAND_TARGET` | `ID_RATIO` < 0,70 | Usos #2 e #9 |
| `MTSS_FU_STUDENT_TALK_LOW` | `PT` < 0,25 | Uso #2 |
| `MTSS_FU_INDIRECT_TWO_THIRDS` | `ID_RATIO` < 1,5 (equivalente a 60% de intervalos indiretos) | Uso #3, "adaptado da regra dos dois terços" (citada sem definição em CAP4 `tab:art2-resultados-esperados-sintese` l.408) |

Todas as quatro estão gravadas em `mtss_rules.json` com `enabled: false` e
`threshold_pending_validation: true` — elas **existem no arquivo** (para que
a proposta fique documentada e pronta para ativação), mas **não disparam**
enquanto o pesquisador não confirmar o corte junto a uma fonte primária. O
motor (`fias_ed_engine.mtss.evaluate`) ignora toda regra com
`enabled: false`.

FU (Uso #3) cita ainda mais dois cortes que não estão representados em
`mtss_rules.json`, nem mesmo como regra desabilitada: "≥ 80% acima da
'mediana esperada' nas 4 escalas cooperativas do QTI" e "≥ 70% de
convergência" (`RESEARCH_INVENTORY.md` §4.4). Diferente dos quatro cortes
acima — que reaproximam um fato já calculado pelo motor a partir dos
intervalos FIAS (`ID_RATIO`, `PT`) —, esses dois dependem de uma "mediana
esperada" do QTI e de uma definição de "convergência" entre FIAS e QTI que
o próprio FU não define operacionalmente. Por isso ficam pendentes da
revisão do pesquisador (spec §17, item 4 — pareamento FIAS↔QTI), sem uma
regra correspondente neste arquivo.

## O sistema nunca emite rótulos de conformidade

Nenhuma regra, interpretação ou sugestão usa os rótulos `conforme` /
`não conforme`, pontuação em escala numérica, cores de semáforo ou qualquer
rótulo de `avaliação docente`. Isso é garantido por duas camadas:

1. **Conteúdo das regras**: toda `interpretation` em `mtss_rules.json` e todo
   `text` em `pedagogical_rules.json` foi redigido no vocabulário formativo
   ("Considere…", "Você pode experimentar…", "Uma possibilidade é…", "Este
   padrão pode indicar…").
2. **Teste automatizado**: `fias_ed_engine.language.find_forbidden` varre o
   texto de interpretações e sugestões contra uma lista de expressões
   proibidas (`errado/errada`, `ruim/ruins`, `inadequado`, `nota/notas`,
   `desempenho`, `fracasso`, `deveria ter`, `conforme`, `não conforme`,
   `reprovado/reprovada`, `avaliação docente`). `test_language.py` e
   `test_docs.py` falham se qualquer uma dessas expressões aparecer fora de
   crases.

Além disso, toda regra disparada (`evaluate_mtss`) sempre inclui evidências:
os índices numéricos usados e, quando aplicável, trechos de transcrição
(`segments:category=N`) que sustentam o padrão relatado — nunca apenas um
veredito isolado.

## Seleção de trechos de evidência (`select_evidence_segments`)

`fias_ed_engine.mtss.select_evidence_segments(segments, category, limit=3)`
escolhe, para uma categoria FIAS disparada, até `limit` segmentos como
evidência (maior confiança primeiro, empate pelo início mais cedo). Ela
espera que cada item de `segments` seja um dicionário com as chaves
`category` (categoria FIAS já resolvida) e `confidence` — diferente de
outras estruturas de segmento do motor (`export.py`, `classifier.py`), que
carregam `pred_role_constrained`/`pred_raw` em vez de `category`. Quem
chama esta função (Web/Android) precisa mapear `pred_role_constrained` para
`category` antes de montar a lista.

## `pedagogical_rules.json`: sugestões e pares de triangulação

`pedagogical_rules.json` liga cada dimensão Tier 1 a sugestões de reflexão
(campo `recommendations`, todas `validation_status:
draft_pending_researcher_review` — redigidas pelo desenvolvimento, aguardando
revisão do pesquisador antes de qualquer estudo de caso) e define os
`triangulation_pairs` usados por `triangulation.py` (ver
`RESEARCH_INVENTORY.md` §5).
