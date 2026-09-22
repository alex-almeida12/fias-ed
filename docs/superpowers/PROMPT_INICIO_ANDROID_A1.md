# Prompt de partida — Android, fatia A1

Colar no Claude Code aberto em `C:\Users\Alex Almeida\Documents\mestrado\sistemas`.
A primeira linha precisa ser a invocação da skill; o resto vira argumento.

```
/superpowers:using-superpowers

Conduza do início ao fim a primeira fatia vertical (A1) do subprojeto Android
do FIAS-ED, na sequência aprovada spec → plano → execução, usando
OBRIGATORIAMENTE estas skills, nesta ordem:

1. superpowers:brainstorming — antes de qualquer pergunta, leia
   docs/PROMPT_MESTRE.md, ARCHITECTURE.md,
   docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md, o spec do Web W1
   e a memória do projeto. Não reabra decisões já aprovadas. Pergunte uma coisa
   de cada vez, proponha o recorte da fatia A1 e PARE para eu aprovar. Ao final,
   escreva o spec em
   docs/superpowers/specs/<data>-fias-ed-android-a1-<nome>-design.md.
2. superpowers:writing-plans — a partir do spec aprovado, escreva
   docs/superpowers/plans/<data>-fias-ed-android-a1.md no mesmo formato do plano
   do Web W1: tasks numeradas, cada uma terminando em commit, TDD onde couber,
   constraints globais explícitas. PARE para eu aprovar o plano.
3. superpowers:subagent-driven-development — execute o plano na branch
   feat/fias-ed-android-a1, uma task por vez, aplicando
   superpowers:test-driven-development em cada task,
   superpowers:requesting-code-review depois de cada task e
   superpowers:verification-before-completion antes de dizer que algo está
   pronto. Não pule tasks nem antecipe trabalho de fatias futuras.

Regras: todo commit termina com o trailer
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>.
Não toque em fias-ed-shared/, em "artigos selecionados" nem em
avalie-seu-professor. Responda sempre em pt-BR.

Comece agora pela etapa 1.
```

Observações:
- A execução para duas vezes de propósito: aprovação do spec e aprovação do plano.
- Dá para encurtar o brainstorming já dizendo o recorte desejado da A1
  (por exemplo: gravar a aula, salvar offline e listar aulas, sem transcrição).
- Antes do Android, o Web W1 ainda tem pendências: Task 17 (revisão visual com
  Impeccable), verificação de entrada em navegador real e Task 18; a branch
  `feat/fias-ed-web-w1` não foi publicada nem mergeada.
