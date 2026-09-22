# QTI (`rules/qti_config.json`)

Este documento explica o Questionário sobre a Interação do Professor (QTI)
usado no FIAS-ED, a decisão de usar a versão de 24 itens do sistema
`avalie-seu-professor` em vez da versão de 64 itens da dissertação, e como
`qti_config.json` é gerado e mantido. Fundamentação completa:
`RESEARCH_INVENTORY.md` §3.

## Duas versões, uma decisão

- **QTI-64** (dissertação, CAP4 l.63–65 e Tab. `tab:art2-escalas-qti`): oito
  escalas de 8 itens (embora l.65 diga "de sete a nove itens", divergindo da
  tabela), citando Wubbels (1991). Mapeamento item→escala e regra de
  pontuação **não foram encontrados** nas fontes.
- **QTI-24** (sistema `avalie-seu-professor`, "fiel ao manual VIL-24, jan.
  2013"): 24 itens congelados, com fórmula completa de octantes e eixos
  Agency/Communion implementada em código.
- **Decisão do pesquisador (2026-09-21)**: o FIAS-ED usa o **QTI-24** como
  instrumento operacional, por ter mapeamento, pontuação e implementação de
  referência completos e auditáveis.

## Tabela de rótulos (sistema × dissertação × EN × NL)

| Octante | PT-BR (sistema, QTI-24) | PT-BR (dissertação, QTI-64) | EN | NL |
|---|---|---|---|---|
| oc1 | Liderança | Liderança (DC) | Directing | Sturend |
| oc2 | Amigável | Prestativo/Amigável (CD) | Helpful | Vriendelijk |
| oc3 | Compreensivo | Compreensivo (CS) | Understanding | Begrijpend |
| oc4 | Dá Liberdade | Dá Responsabilidade ou Liberdade (SC) | Compliant | Inschikkelijk |
| oc5 | **Inseguro** | **Incerto** (SO) | Uncertain | Onzeker |
| oc6 | Insatisfeito | Insatisfeito (OS) | Dissatisfied | Ontevreden |
| oc7 | **Irritável** | **Admoestador** (OD) | Confrontational | Corrigerend |
| oc8 | Rigoroso | Rigoroso (DO) | Imposing | Dwingend |

As duas divergências de rótulo em destaque (oc5: Inseguro/Incerto; oc7:
Irritável/Admoestador) não são erros — são traduções diferentes do mesmo
octante feitas em momentos e projetos diferentes (sistema vs. dissertação).
Como o FIAS-ED usa o QTI-24, os relatórios usam os rótulos da coluna
"sistema" (Inseguro, Irritável).

## Fórmula completa de octantes, Agency e Communion

Tronco do item: "Este(a) professor(a)…". Likert 1–5, âncoras "(Quase)
nunca" / "(Quase) sempre". Octantes: `oc1 = {1, 9, 17}`, `oc2 = {2, 10, 18}`,
`oc3 = {3, 11, 19}`, `oc4 = {4, 12, 20}`, `oc5 = {5, 13, 21}`,
`oc6 = {6, 14, 22}`, `oc7 = {7, 15, 23}`, `oc8 = {8, 16, 24}`.

```
oc_k = (média(respostas do octante k) − 1) / 4

a = 0.923880
b = 0.382683

AGENCY   = b · (a·oc1 + b·oc2 − b·oc3 − a·oc4 − a·oc5 − b·oc6 + b·oc7 + a·oc8)
COMMUNION = b · (b·oc1 + a·oc2 + a·oc3 + b·oc4 − b·oc5 − a·oc6 − a·oc7 − b·oc8)
```

Fonte: `avalie-seu-professor/src/domain/qti/QtiOctant.ts` e `qtiWeights.ts`
(manual VIL-24, jan. 2013). `validation_status: validated` para os pesos
`a`/`b` e a fórmula (é a implementação de referência do sistema); o
instrumento como um todo (tradução, itens) está `PENDING_SCIENTIFIC_VALIDATION`
(ver seção "Status de validação" abaixo).

## Agregação e exibição

O resultado agregado de uma turma é a **média entre respondentes**, por
octante, e por Agency/Communion. `MIN_RESPONSES_FOR_PUBLIC_RESULT = 10`
(`min_responses` em `qti_config.json.instrument`, `engineering_decision`
herdada de `avalie-seu-professor`) — abaixo desse número de respostas, o
resultado não é `displayable`.

## Formas de entrada

Todas as entradas alimentam o mesmo esquema `RespostaQTI` (24 respostas,
1–5, chaves "1".."24"):

- Importação do dataset exportado pelo `avalie-seu-professor`
  (`source: IMPORT_AVALIE_SEU_PROFESSOR`).
- Formulário digital (`source: FORM`).
- Digitação manual (`source: MANUAL`).
- OCR de folha impressa (`source: OCR`).

Toda entrada que não veio de importação direta do sistema (formulário
digital já validado) passa por confirmação humana antes de ser usada
(`QuestionarioQTI.confirmed`).

## Mínimo de 10 respostas

Reforçando a seção "Agregação e exibição": o resultado de turma só é exibido
(`displayable = true`) quando `response_count >= 10`. Abaixo disso, o motor
ainda calcula os valores internamente (para permitir auditoria), mas o
relatório não os expõe, para preservar o anonimato de turmas pequenas.

## Aviso de licença

O instrumento QTI-24 "pertence a Wubbels e colegas (Universidade de Utrecht)
e não pode ser usado para fins comerciais" (README de
`avalie-seu-professor`). A tradução para PT-BR usada pelo sistema "não
constitui versão psicometricamente validada" (mesmo README).
`Normas_Eticas.md` l.78: "Autorização de uso obtida junto aos detentores dos
direitos (providência pendente…)"; `Alteracoes_Realizadas.md` Parte V:
"[ ] Autorização de uso do QTI junto a Wubbels… tratativa em curso." Por isso
`qti_config.json.instrument.validation_status = PENDING_SCIENTIFIC_VALIDATION`
e `license_note` registra a pendência de autorização formal.

## Status de validação

CAP4 l.343/l.460: "inexistência de validação brasileira formal"; "em fase de
adaptação, sem validação concluída". O protocolo de adaptação transcultural
proposto (Beaton 2000 + ISPOR/Wild 2005, retrotradução, CVCc ≥ 0,80, IVC
0,78, piloto 30+30, AFC com CFI ≥ 0,90 e RMSEA ≤ 0,08, α ≥ 0,70) ainda não foi
concluído — ver `RESEARCH_INVENTORY.md` §3.4.

## `extract_qti.py --check`

`qti_config.json` **nunca é editado à mão**. Ele é gerado por
`scripts/extract_qti.py` a partir dos arquivos TypeScript congelados do
sistema (`qtiItems.ts`, `QtiOctant.ts`, `qtiWeights.ts`, `likertScale.ts`),
que ficam fora deste repositório, em modo somente leitura. O gerador extrai
os 24 itens, os 8 octantes, os pesos `a`/`b` e as âncoras Likert por regex, e
grava o SHA-256 de cada arquivo-fonte lido.

- `python scripts/extract_qti.py` regenera `rules/qti_config.json`.
- `python scripts/extract_qti.py --check` **não escreve nada**: compara o
  JSON que seria gerado com o que já está em `rules/qti_config.json` e
  retorna código de saída 1 se divergirem, imprimindo "DIVERGENTE — rode
  extract_qti.py". Este é o comando usado para confirmar, antes de qualquer
  mudança, que `qti_config.json` continua idêntico ao sistema
  `avalie-seu-professor`.

Qualquer alteração de texto, posição ou octante de um item só deve ser feita
no sistema `avalie-seu-professor` (fonte canônica) e depois propagada aqui
rodando o extrator — nunca editando `qti_config.json` diretamente.
