# Inventário científico — FIAS-ED

Este documento reúne, com citação de fonte, tudo o que os textos da pesquisa
definem (e não definem) sobre FIAS, QTI, MTSS Tier 1, triangulação, ASR/diarização
e metas de validação. É a base factual dos arquivos `rules/*.json` e dos
demais documentos de `docs/`. Nada aqui foi inventado: onde a fonte não
define um valor, o item aparece marcado `PENDING_SCIENTIFIC_VALIDATION`.

Abreviações de fonte (ver também `SCIENTIFIC_TRACEABILITY.md`):

| Sigla | Caminho completo |
|---|---|
| CAP4 | `artigos selecionados/Dissertacao Qualificação/2-textuais/4-artigo-fias-ed.tex` |
| CAP5 | `artigos selecionados/Dissertacao Qualificação/2-textuais/5-validacao.tex` |
| SIMB | `artigos selecionados/Dissertacao Qualificação/1-pre-textuais/lista-de-simbolos.tex` |
| PQTI | `Adaptação para o Português Brasileiro do Questionário sobre a Interação do Professor (QTI)/01_Projeto_Revisado/Projeto_de_Pesquisa_Revisado.docx` |
| SIS | `Adaptação...QTI/sistema/avalie-seu-professor/` |
| CEP | `artigos selecionados/Projeto_CEP_UERN_FIAS-ED.docx` |
| FU | `artigos selecionados/Formas_de_Uso_Tier1.docx` |

## 1. Fontes consultadas

- `artigos selecionados/Dissertacao Qualificação/2-textuais/4-artigo-fias-ed.tex` (CAP4)
- `artigos selecionados/Dissertacao Qualificação/2-textuais/5-validacao.tex` (CAP5)
- `artigos selecionados/Dissertacao Qualificação/2-textuais/3-artigo-rsl.tex` (revisão sistemática de literatura)
- `artigos selecionados/Dissertacao Qualificação/1-pre-textuais/lista-de-simbolos.tex` (SIMB)
- `artigos selecionados/Projeto_CEP_UERN_FIAS-ED.docx` (CEP)
- `artigos selecionados/Formas_de_Uso_Tier1.docx` (FU)
- `artigos selecionados/Fundamentacao_Teorica_MTSS.docx`
- `artigos selecionados/Analise_Integracao_MTSS_FIAS.docx` (nome de trabalho; enquadramento textual, sem critérios novos)
- `artigos selecionados/Guia_Incorporacao_MTSS.docx` (nome de trabalho; enquadramento textual, sem critérios novos)
- `Adaptação para o Português Brasileiro do Questionário sobre a Interação do Professor (QTI)/01_Projeto_Revisado/Projeto_de_Pesquisa_Revisado.docx` (PQTI)
- `Adaptação...QTI/06_Referencias/Normas_Eticas.md`
- `Adaptação...QTI/Alteracoes_Realizadas.md`
- `Adaptação...QTI/sistema/avalie-seu-professor/` (SIS — README.md e `src/domain/qti/*.ts`)
- `artigos selecionados/experimentos/DOCUMENTACAO_EXPERIMENTOS.md`
- `artigos selecionados/experimentos/resultados_bert/TalkMoves-FIAS/mapeamento_meta.json`
- `artigos selecionados/experimentos/Mapeamento_TalkMoves_FIAS_Tecnicas_IA.docx`

## 2. FIAS

### 2.1 Agrupamento e nomes das categorias

Agrupamento (CAP4, seção "O FIAS como modelo…", l.26): "fala do professor
(categorias 1 a 7, subdivididas em influência indireta, categorias 1 a 4, e
influência direta, categorias 5 a 7)"; "fala do aluno (categorias 8 e 9)";
"silêncio ou confusão (categoria 10)".

Nomes canônicos (CAP4 Tab. `tab:art2-categorias-fias`, l.37–46, "Adaptado de
Flanders (1970)"):

| Cat | Nome canônico | Grupo | Influência |
|---|---|---|---|
| 1 | Aceita sentimentos | professor | indireta |
| 2 | Elogia ou encoraja | professor | indireta |
| 3 | Aceita ou usa ideias | professor | indireta |
| 4 | Faz perguntas | professor | indireta |
| 5 | Expõe (lecture) | professor | direta |
| 6 | Dá instruções | professor | direta |
| 7 | Critica ou justifica autoridade | professor | direta |
| 8 | Resposta do aluno | aluno | — |
| 9 | Iniciativa do aluno | aluno | — |
| 10 | Silêncio ou confusão | silêncio | — |

**Divergência de nomes entre documentos**: `experimentos/resultados_bert/TalkMoves-FIAS/mapeamento_meta.json`
usa "Aceita ou Utiliza Ideias dos Alunos", "Expõe/Explica", "Dá Direções";
`Mapeamento_TalkMoves_FIAS_Tecnicas_IA.docx` §1 usa as mesmas variantes, sem
acentos. `fias_rules.json` registra o nome canônico de CAP4 e essas variantes
em `aliases`.

### 2.2 Protocolo de codificação

Codificação a cada 3 s; classificador turn-level reagrupado em intervalos de
3 s (CAP4 l.56, l.277, l.294, l.298).

Regras de desambiguação — citação literal (CAP4 l.277): "regra do viés de
Flanders (em caso de dúvida entre duas categorias, opta-se pela mais distante
da categoria 5), codificação de chamada nominal como categoria 4, codificação
de repetição da resposta correta como categoria 2, codificação de piada do
professor à custa de aluno como categoria 7 e codificação de perguntas
retóricas como categoria 5."

Essas regras dependem de julgamento humano sobre o conteúdo do turno; o
`fias_ed_engine` não as aplica automaticamente porque nenhuma fonte define um
procedimento determinístico para aplicá-las a partir de texto — ver item 10.11.

### 2.3 Matriz de transições

10×10, célula (i,j) = frequência de transição i→j (CAP4 l.52, l.279).
"Convenciona-se acrescentar 10 no início e no fim da sequência." (CAP4 l.279)
— por isso a matriz também conta as transições de/para o "estado" categoria 10
nas bordas da aula.

### 2.4 Índices

CAP4 l.279 cita um "vetor de oito índices derivados", atribuindo a fonte
apenas a Flanders (1970), sem repetir as fórmulas no corpo do texto. SIMB
l.4–15 dá as definições textuais:

| Símbolo | Definição textual (SIMB) | O que é definido | O que não é definido |
|---|---|---|---|
| TT | "Percentual de fala do professor…sobre o total da aula" | fórmula | faixa de referência |
| PT | análogo a TT, para o aluno | fórmula | faixa de referência |
| SC | análogo a TT, para silêncio/confusão | fórmula | faixa de referência |
| r_id | "proporção entre influência indireta (cat. 1–4) e direta (cat. 5–7)" | fórmula | faixa de referência; fórmula da "razão I/D revisada" citada em CAP4 l.279 |
| PIR | "proporção da categoria 9 sobre o total da fala discente" | fórmula | — |
| PTR | "Razão de resposta do aluno (Pupil Talk Ratio): proporção da categoria 8 sobre o total da fala discente" | fórmula | a sigla PTR é incoerente com a definição (ver 2.5) |
| TRR | "proporção das categorias 1–3 sobre o total da fala docente reativa" | numerador | denominador ("fala docente reativa") indefinido |
| r_pa | "Razão de fala professor/aluno" | — | fórmula não definida |
| I_A (1,2,3), I_E (4), I_C (5,6,7), I_P (8,9) | listados apenas em SIMB | agrupamento de categorias | sem uso nos capítulos, sem faixa de referência |

Não encontrado nas fontes: fórmula da "razão I/D revisada"; definição de
"células steady state"; citação direta a Amidon; faixas de referência
numéricas para I/D, TT, PT ou SC.

Concordância entre codificadores: κ relatado na faixa 0,73–0,90 (chen2019,
yang2025), citada em CAP4 l.56 como "faixa adotada como referência" — não é
uma faixa de referência para os índices, e sim para concordância
inter-codificadores. A "regra dos dois terços de Flanders" é citada sem
definição em CAP4 Tab. `tab:art2-resultados-esperados-sintese` (l.408).

### 2.5 Divergência da sigla PTR

SIMB define PTR ("Pupil Talk Ratio") como "proporção da categoria 8 sobre o
total da fala discente" — mas essa é a definição operacional de uma "razão de
resposta discente", não de uma razão de fala do aluno em geral (que seria
PT). `fias_rules.json` resolve isso adotando o id `PUPIL_RESPONSE_RATIO` (que
segue a definição, cat. 8 / cat. 8+9) e documentando a divergência de sigla
como observação da regra — ver `FIAS.md`.

## 3. QTI

### 3.1 QTI-64 (dissertação)

CAP4 l.63–65 e Tab. `tab:art2-escalas-qti` (l.318–327), citando Wubbels
(1991): oito escalas, cada uma com um setor (DC, CD, CS, SC, SO, OS, OD, DO):
"Liderança" (DC), "Prestativo/Amigável" (CD), "Compreensivo" (CS), "Dá
Responsabilidade ou Liberdade" (SC), "Incerto" (SO), "Insatisfeito" (OS),
"Admoestador" (OD), "Rigoroso" (DO).

Inconsistência interna à dissertação: CAP4 l.65 diz "de sete a nove itens"
por escala; a Tab. `tab:art2-escalas-qti` diz 8 itens por escala.

Likert (CAP4 l.335; PQTI): "1 (Nunca), 2 (Raramente), 3 (Às vezes), 4 (Quase
sempre) e 5 (Sempre)". Versões aluno e professor, real e ideal (Fisher 1995).
64 itens em PT-BR estão nos Anexos A/B de PQTI.

**Não encontrados**: mapeamento item→escala e regra de pontuação da versão de
64 itens.

### 3.2 QTI-24 (sistema)

Fonte: SIS README, seção "Cálculo do QTI-24 (fiel ao manual VIL-24, jan.
2013)", e `src/domain/qti/*.ts`. 24 itens congelados; âncoras Likert "(Quase)
nunca"/"(Quase) sempre"; octantes oc1{1,9,17} … oc8{8,16,24}; rótulos
PT-BR/EN/NL — ver tabela completa em `QTI.md`.

Fórmulas: `oc_k = (média − 1) / 4`; `a = 0.923880`; `b = 0.382683`;
`AGENCY = b·(a·oc1 + b·oc2 − b·oc3 − a·oc4 − a·oc5 − b·oc6 + b·oc7 + a·oc8)`;
`COMMUNION = b·(b·oc1 + a·oc2 + a·oc3 + b·oc4 − b·oc5 − a·oc6 − a·oc7 − b·oc8)`.
Agregado da turma = média entre respondentes. `MIN_RESPONSES_FOR_PUBLIC_RESULT
= 10` (`src/config/env.ts`).

O README do SIS afirma que a tradução "não constitui versão psicometricamente
validada" e que o instrumento "pertence a Wubbels e colegas (Universidade de
Utrecht) e não pode ser usado para fins comerciais".

### 3.3 Decisão do pesquisador

Decisão registrada em 2026-09-21: o FIAS-ED usa o QTI-24 do sistema (não o
QTI-64 da dissertação) como instrumento operacional. O QTI-64 permanece
documentado neste inventário porque é a versão citada na fundamentação
teórica da dissertação.

### 3.4 Status de validação e autorização

CAP4 l.343 e l.460: "inexistência de validação brasileira formal"; "em fase
de adaptação, sem validação concluída". Protocolo proposto: Beaton (2000) +
ISPOR/Wild (2005), 6 estágios, retrotradução por 2 nativos (PQTI, "Etapas da
adaptação transcultural"); CVCc ≥ 0,80 (Hernández-Nieto); IVC 0,78; piloto
30+30; reformulação de itens compreendidos por menos de 80% dos respondentes;
AFC com cargas ≥ 0,50, CFI ≥ 0,90, RMSEA ≤ 0,08; α ≥ 0,70 (PQTI, "Plano de
análise"; CAP5 Tab. `tab:val-criterios-sintese`).

Licença: `06_Referencias/Normas_Eticas.md` l.78: "Autorização de uso obtida
junto aos detentores dos direitos (providência pendente…)";
`Alteracoes_Realizadas.md` Parte V: "[ ] Autorização de uso do QTI junto a
Wubbels… tratativa em curso".

### 3.5 Divergência de escopo

PQTI descreve coleta online (Google Forms) com estudantes de Ensino
Médio/EPT/EJA; a dissertação (CAP4) descreve formulários impressos com
estudantes do Fundamental II.

## 4. MTSS Tier 1

CAP4, seção "O Tier 1 do MTSS…" (l.122–124): meta de "aproximadamente 80% dos
alunos" (vaughn2003redefining); antes de intervir, revisar primeiro "as
variáveis sob responsabilidade docente" (stecker2005cbm, mandinach2021).

### 4.1 Tabela `tab:art2-fias-tier1` (CAP4 l.137–146)

"O autor (2026), com base em" Flanders, Nitz e Stecker:

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

### 4.2 Leitura qualitativa (CAP4 l.285)

Citação literal: "razão indireta/direta (I/D) elevada aponta para práticas
associadas a engajamento e diferenciação; percentuais altos nas categorias 5,
6 ou 7 indicam padrão mais expositivo ou diretivo." Não há limiar numérico
associado a essa leitura.

### 4.3 Lacuna dos critérios por aula

CAP4 l.287 promete um diagnóstico por aula em três rótulos "segundo os
critérios formalizados na Subseção `subsec:val-tier1`" — mas essa subseção,
em CAP5 (l.348), define **critérios de validação do framework como um todo**
(cobertura ≥ 80% das aulas interpretáveis; discriminação por coeficiente de
variação de I/D, PIR e a razão de resposta discente ≥ 0,15; resposta a
retorno: melhora em ao menos 1 indicador), não critérios de leitura de uma
aula individual. A "faixa de referência" de I/D citada em CAP4 l.285 não é
definida em nenhuma das duas seções. Este é o motivo pelo qual o
`fias_ed_engine` não classifica aulas em rótulos por intensidade — apenas
relata fatos descritivos (ver `MTSS.md`).

### 4.4 Formas de Uso (FU) como documento de apoio

`Formas_de_Uso_Tier1.docx` propõe cortes operacionais, mas **não cita uma
fonte primária** — apenas "literatura sobre Tier 1" de forma genérica:

- Uso #2: selo de I/D ≥ 0,70 / entre 0,40 e 0,69 / < 0,40; fala discente < 25%.
- Uso #3: ≥ 80% acima da "mediana esperada" nas 4 escalas cooperativas do
  QTI; ≥ 60% de intervalos docentes indiretos, "adaptado… regra dos dois
  terços"; ≥ 70% de convergência.
- Uso #4: exemplo numérico "PIR = 0,12, PTR = 0,18 (zona de atenção)".
- Uso #9: meta I/D = 0,70, avaliada por tendência ao longo do tempo.

`Fundamentacao_Teorica_MTSS.docx` §4.5 registra ainda: ">20% abaixo do
benchmark → revisar Tier 1" (Vaughn & Fuchs 2003; Branching Minds) — também
sem definição operacional de "benchmark" para o contexto FIAS-ED.
`Analise_Integracao_MTSS_FIAS.docx` e `Guia_Incorporacao_MTSS.docx` trazem
apenas enquadramento textual, sem critérios numéricos novos.

Por não terem fonte primária, todos esses cortes estão presentes em
`mtss_rules.json` com `enabled: false` e `threshold_pending_validation: true`
— ver `MTSS.md`.

## 5. Triangulação

CAP4, subseção `subsec:art2-triangulacao` (l.350–371), citando Fisher (1995):
três planos de leitura — convergência (exemplo dado: alta frequência de cat.
2/3 do FIAS junto com escalas DC/CS altas do QTI), divergência reveladora
(exemplo: I/D alta do FIAS junto com escala DO alta do QTI) e
complementaridade; e uma "quarta dimensão", a comparação entre QTI-professor
(autopercepção) e QTI-alunos.

CAP5, seção `sec:val-metricas`: correlações de Pearson e Spearman e
diferença média absoluta entre QTI-aluno e QTI-professor (real); Spearman
esperado entre 0,40 e 0,70 (l.390); discrepância esperada em 30–50% dos
pares (wubbels1991). CAP5, seção `sec:val-discrepancias` (l.353–355): três
tipos de discrepância, teste de Wilcoxon pareado, correlação de Spearman e
uma tipologia das discrepâncias. QE4 (questão de pesquisa) espera que os
padrões apareçam em ao menos 2/3 das aulas.

**Não definido em nenhuma fonte**: um algoritmo que classifique
automaticamente em qual dos três planos uma aula se enquadra; um pareamento
formal entre cada índice do FIAS e cada escala do QTI (o pareamento usado em
`pedagogical_rules.json` é uma proposta operacional do desenvolvimento,
`PENDING_SCIENTIFIC_VALIDATION` — ver `MTSS.md` e a seção 6 do spec).

## 6. AIED Unplugged

CAP4 l.115 (Isotani 2023) lista os princípios: conformidade, desconexão,
proxy, multiusuário, simplicidade — no sentido do termo técnico dos "princípios
AIED Unplugged", não usado aqui como avaliação de conformidade do sistema.

CEP l.55 lista princípios com redação diferente: "conformidade…, frugalidade
computacional, robustez a falhas de conectividade, autonomia local…,
equidade de acesso". Os dois textos citam a mesma ideia geral (sistema
robusto a restrições tecnológicas) mas com listas de princípios distintas —
divergência registrada, não resolvida pelas fontes.

## 7. ASR/diarização

Nenhum modelo de ASR ou diarização é nomeado no corpo da dissertação (CAP4 /
CAP5). O Whisper é sugerido apenas na revisão sistemática de literatura
(`3-artigo-rsl.tex` l.308), não na dissertação principal. Requisitos de
áudio: WAV/FLAC, ≥ 16 kHz, aulas de aproximadamente 50 min (CAP5, seção de
captura).

Metas (CAP5, seção `sec:val-metricas` e Tab. `tab:val-criterios-sintese`):
WER = (S+D+I)/N ≤ 25%; DER ≤ 25% — ambas descritas na tabela como
`"conforme literatura"`, sem citação bibliográfica específica. κ do modelo ≥ 0,60
(esperado entre 0,65 e 0,80); κ humano ≥ 0,70. Ver tabela completa na seção 8.

## 8. Métricas-alvo (`metric_targets.json`)

| id | Definição / meta | Status |
|---|---|---|
| WER | (S+D+I)/N ≤ 0,25 | PENDING_SCIENTIFIC_VALIDATION (sem citação) |
| DER | ≤ 0,25 | PENDING_SCIENTIFIC_VALIDATION (sem citação) |
| KAPPA_MODEL | ≥ 0,60 (esperado 0,65–0,80) | PENDING_SCIENTIFIC_VALIDATION |
| KAPPA_HUMAN | ≥ 0,70 | validated |
| F1_AXIS | ≥ 0,70 | validated |
| OCR_ACCURACY | ≥ 0,95 | validated |
| PIPELINE_COMPLETION | ≥ 0,90 das aulas | validated |
| CLOUD_OFFLINE_DEGRADATION | ≤ 10 p.p. de F1 | validated |
| SUS | ≥ 70 | validated |
| TAM | ≥ 4,0 | validated |

Todas as linhas têm fonte CAP5 `tab:val-criterios-sintese`. F1 ≥ 0,65
aparece nos textos apenas como o valor relatado por Foster (2024) na tabela
comparativa `tab:art2-comparativo`, não como meta própria do FIAS-ED —
reforça, sem ser meta formal, a leitura de que os resultados dos experimentos
(F1 macro 0,7246 no BERTimbau PT-BR; ver `ANALISE_MODELOS_EXISTENTES.md`)
estão acima dessa referência externa.

## 9. Divergências entre documentos

| Divergência | Onde aparece | Resolução adotada |
|---|---|---|
| Nomes das categorias FIAS (acentuação, "Aceita ou Utiliza Ideias dos Alunos" vs "Aceita ou usa ideias") | CAP4 vs `mapeamento_meta.json` vs `Mapeamento_TalkMoves_FIAS_Tecnicas_IA.docx` | nome canônico de CAP4 em `fias_rules.json.categories[].name`; variantes em `aliases` |
| Rótulos QTI (Incerto/Inseguro; Admoestador/Irritável) | CAP4 (QTI-64) vs SIS (QTI-24) | sistema usa QTI-24; ver tabela comparativa em `QTI.md` |
| Mapeamento TalkMoves→FIAS em três versões | `mapeamento_meta.json` vs `Mapeamento_TalkMoves_FIAS_Tecnicas_IA.docx` (numeração diferente, ex. "Cat. 6 - Aceita ou Utiliza Ideias") vs CAP5 l.204 ("retomar contribuição de aluno ↔ categoria 2") | não unificado nesta fase; item 7 da lista de pendências abaixo |
| UFERSA × UERN | CEP (projeto vinculado à UERN) vs CAP5 l.82 (menciona UFERSA) | não resolvido nas fontes; registrado em `PRIVACY.md` |
| Sigla PTR incoerente com a definição de PIR/PTR | SIMB l.4–15 | ver seção 2.5 acima e `FIAS.md` |

## 10. Lista completa de pendências científicas (`PENDING_SCIENTIFIC_VALIDATION`)

Esta lista consolida o spec §17 e o item 7 deste inventário; é a base de
`SCIENTIFIC_TRACEABILITY.md` e de todo `validation_status` marcado como
pendente em `rules/*.json`.

1. Critérios de diagnóstico por aula do Tier 1: referenciados em CAP4 l.287,
   mas nunca definidos (CAP5 `subsec:val-tier1` define critérios de validação
   do framework, não da aula).
2. Faixa de referência de I/D e limiares de TT, PT, SC, PIR e da razão de
   resposta discente — os cortes de FU não têm fonte primária.
3. Fórmula da "razão I/D revisada"; denominador da TRR ("fala docente
   reativa"); definição de r_pa; uso de I_A/I_E/I_C/I_P (listados só em SIMB).
4. "Regra dos dois terços de Flanders", citada sem definição (CAP4
   `tab:art2-resultados-esperados-sintese` l.408).
5. Algoritmo de triangulação e pareamento formal entre índices FIAS e
   escalas QTI (os pares em `pedagogical_rules.json` são propostas do
   desenvolvimento).
6. QTI-64: mapeamento item→escala e regra de pontuação, ausentes; e a
   harmonização de rótulos entre QTI-64 (Incerto, Admoestador) e QTI-24
   (Inseguro, Irritável).
7. Tradução PT-BR do QTI-24 sem validação psicométrica concluída;
   autorização de uso junto a Wubbels e colegas pendente.
8. Mapeamento TalkMoves→FIAS existe em três versões divergentes, não
   unificadas.
9. Metas de WER e DER ≤ 25% sem citação bibliográfica; meta de κ do modelo
   ≥ 0,60 também sem citação direta.
10. A Tab. `tab:art2-fias-tier1` (categoria FIAS ↔ dimensão Tier 1) é de
    autoria própria do pesquisador ("O autor (2026), com base em…"), não uma
    tradução direta de uma fonte única.
11. Regra de agregação de turno para intervalo de 3 s (maior cobertura,
    desempate pelo início mais cedo) e aplicação automática/determinística
    das regras de desambiguação de CAP4 l.277 — nenhuma fonte define o
    procedimento algorítmico.
12. Tratamento de privacidade em modo cloud/LLM (envio a APIs de terceiros)
    não é coberto pelos termos de consentimento (TCLE/TALE) nem pelo projeto
    CEP.
