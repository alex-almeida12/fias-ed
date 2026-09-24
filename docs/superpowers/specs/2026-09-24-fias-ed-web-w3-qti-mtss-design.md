# Spec — Subprojeto 2, fatia W3: `fias-ed-web` — QTI, MTSS e triangulação

**Data:** 24 de setembro de 2026
**Autor:** Alex Almeida (alex.amaral@alunos.ufersa.edu.br)
**Fatia anterior:** W2 (áudio → FIAS), concluída em `393ebd3`

---

## 0. Posição na decomposição

| Fatia | Entrega | Estado final da aula |
|---|---|---|
| W1 Fundação (entregue) | Compose, banco, autenticação, design system, upload e validação | `AUDIO_VALIDATED` |
| W2 Pipeline (entregue) | Transcrição, separação de vozes, revisão, classificação FIAS | `FIAS_COMPLETED` |
| **W3 (esta)** | **Percepção dos estudantes, triangulação, MTSS Tier 1, relatórios** | **`REPORT_READY`** |

Nenhum status novo: os cinco que W3 usa — `WAITING_QTI`, `QTI_COMPLETED`,
`TRIANGULATED`, `MTSS_INTERPRETED`, `REPORT_READY` — já foram definidos em W1 e
estão no enum sem nada que os produza.

---

## 1. Objetivo de W3

Responder, para uma aula e para um ciclo de aulas, a pergunta que a Seção 5.9 da
qualificação formula:

> *"o que o professor faz, observado, é coerente com o que os alunos percebem que
> ele faz?"*

E, no fechamento do ciclo, mostrar a **trajetória** da prática ao longo das aulas
acompanhadas — sem emitir veredito sobre ela.

---

## 2. Decisões tomadas no desenho

**2.1 O instrumento é o QTI-24, numa versão.** O `qti_config.json` já traz os 24
itens, 3 por octante, escala Likert de 1 a 5, com os textos congelados do projeto
`avalie-seu-professor`. A qualificação descreve o QTI de 64 itens em duas versões
(aluno e professor); **W3 não o implementa.** Essa divergência entre o texto e o
artefato precisa ser resolvida no Capítulo 4, e é decisão do pesquisador.

**2.2 Duas portas de entrada, um resultado por dentro.** O QTI chega por coleta
nativa (estudantes respondem no FIAS-ED) ou por importação do relatório exportado
pelo `avalie-seu-professor`. As duas convergem para a mesma estrutura persistida,
e **a origem fica registrada e viaja até a exportação** — o mesmo princípio de
`silence_source`, adotado em W2: quem analisa precisa saber de onde o dado veio.

**2.3 O QTI pertence ao ciclo, não à aula.** Um ciclo é uma sequência declarada de
aulas de uma turma numa disciplina. A percepção dos estudantes é sobre o professor
naquela turma, não sobre uma aula de 50 minutos.

**2.4 O ciclo é declarado antes.** O professor informa quantas aulas vai acompanhar
ao criar o ciclo. É isso que permite saber qual aula é a primeira e qual é a última.

**2.5 O questionário é obrigatório na primeira e na última aula do ciclo**, opcional
no meio. É o único ponto em que a falta de QTI bloqueia o avanço de uma aula.

Uma coleta **cobre** uma aula quando foi feita na data da aula ou antes dela. A
primeira aula exige uma coleta que a cubra; a última exige uma coleta posterior à
penúltima aula, para que a medição final não seja a mesma da inicial.

**2.6 Cada aula se triangula contra a coleta mais recente anterior a ela.**
Triangular uma aula de março contra uma percepção medida em junho seria comparar
observação com uma opinião que ainda não existia.

**2.7 O sistema não calcula melhora.** O relatório do ciclo mostra a trajetória dos
índices e as duas coletas de QTI, lado a lado, com a pergunta de reflexão incidindo
sobre o percurso. **Quem conclui é o professor, ou o pesquisador na dissertação.**

O motivo é de produto e de método. De produto: o FIAS-ED se define por não avaliar
o professor, e um sistema capaz de afirmar que alguém melhorou é, pela mesma
mecânica, capaz de afirmar que piorou. De método: duas medições mostram diferença,
não melhora — os índices do FIAS variam entre aulas por conteúdo, horário e turma.
Uma trajetória de 6 a 8 pontos é evidência; dois pontos são anedota.

**2.8 As respostas são guardadas item a item, de forma anônima.** O agregado não
basta: a qualificação exige alfa de Cronbach por escala (§5.9), que precisa de
resposta item a item entre respondentes. O respondente é identificado apenas por
índice sequencial dentro da coleta. O formato de exportação do motor já prevê
exatamente isso (`qti_responses`, com `response_index` e `q1`…`q24`).

**2.9 O cálculo do alfa de Cronbach não entra no produto.** Ele é métrica de
validação do instrumento, para a dissertação, e se calcula sobre o dataset
exportado. O produto guarda o insumo e exporta; não exibe o alfa ao professor.

---

## 3. Fluxo e máquina de estados

```
FIAS_COMPLETED
   │
   ├─ é a 1ª ou a última aula do ciclo, e não há coleta que a cubra
   │     ▼
   │  WAITING_QTI  ← humano: coleta nativa ou importação
   │     ▼
   └─ QTI_COMPLETED
         │ triangulate(intervals, indices, qti_result, …)
         ▼
      TRIANGULATED
         │ build_facts → evaluate → recommendations
         ▼
      MTSS_INTERPRETED
         │ monta o relatório da aula
         ▼
      REPORT_READY
```

**Cada estado é marcado pelo passo que o alcança.** Em W2 descobrimos que
`TRANSCRIBED` nunca era atribuído e que `TRANSCRIBING` era marcado pelo handler
anterior — a tela afirmava trabalho que ainda estava na fila. Aqui, mesmo que os
passos levem milissegundos, nenhum estado é marcado por antecipação.

Uma aula do meio do ciclo, ou de um ciclo que já tem coleta, atravessa de
`FIAS_COMPLETED` a `REPORT_READY` sem parada humana.

---

## 4. Fronteira com o `fias-ed-shared`

O motor **já tem tudo** e é somente leitura nesta fatia:

| Função | Módulo | O que decide |
|---|---|---|
| `score_response`, `aggregate` | `qti.py` | pontuação e agregação do QTI-24 |
| `parse_export_csv` | `qti.py` | importação, com recálculo e recusa |
| `triangulate` | `triangulation.py` | os pares de justaposição |
| `build_facts`, `evaluate`, `recommendations` | `mtss.py` | Tier 1 |
| `select_evidence_segments` | `mtss.py` | trechos de evidência |
| `build_dataset` | `export.py` | as nove tabelas do dataset |

**Nenhuma regra científica é reimplementada no Web.** O Web coleta, persiste e
exibe o que o motor devolveu.

Exceção declarada: se a trajetória do ciclo exigir cálculo novo (por exemplo, uma
série temporal dos índices), ele **nasce no motor**, com fonte declarada, nunca no
Web.

---

## 5. Modelos e artefatos

**`Ciclo`** — `turma_id`, `disciplina_id`, `professor_id`, `n_aulas_previstas`,
`iniciado_em`, `encerrado_em`. Sabe qual aula é a primeira e qual é a última.

**`ColetaQTI`** — pertence ao ciclo. `coletado_em`, `origem`
(`COLETA_NATIVA` | `IMPORTACAO_EXTERNA`), `response_count`, `displayable`,
e a versão da configuração do instrumento sob a qual foi pontuada.

**`RespostaQTI`** — pertence à coleta. `response_index` e os 24 valores. **Nenhuma
ligação com identidade.**

**`ResultadoQTI`** — os oito octantes, agência, comunhão. Derivado do motor,
persistido como veio.

**`Triangulacao`** e **`InterpretacaoMTSS`** — por aula, no mesmo padrão de
`IndicadorFIAS`: o que o motor devolveu, persistido sem recálculo.

**`ConsentimentoQTI`** — só no caminho nativo. Documento versionado e registro de
aceite. **Sem chave estrangeira para `RespostaQTI`** — a ausência é o mecanismo:
é ela que impede reconstruir quem respondeu o quê, pelo mesmo princípio do §48,
que proíbe agrupar voz por estudante.

> **Pendência do pesquisador:** a forma legal do consentimento — texto, quem
> consente quando o respondente é menor de idade, e o que precisa ser registrado —
> vem do comitê de ética, não deste documento.

---

## 6. Banco de dados

Migração nova, aditiva. Nenhuma tabela de W1 ou W2 muda de forma.

Exclusão lógica em todas as entidades novas, seguindo o padrão já estabelecido.
A exclusão de uma aula não apaga a coleta de QTI: ela pertence ao ciclo, e outras
aulas dependem dela. A exclusão do ciclo apaga a coleta, as respostas e o
consentimento.

---

## 7. Privacidade (§47, §48, LGPD)

**Os respondentes são estudantes, possivelmente menores de idade.** Esta é a fatia
mais sensível do sistema.

1. **Nenhuma identidade de respondente é persistida.** Sem nome, sem matrícula, sem
   endereço de rede, sem identificador de dispositivo.
2. **O consentimento não se liga à resposta.** Registra-se que houve consentimento;
   não se registra de quem é qual resposta.
3. **O resultado só é exibido a partir de 10 respostas** (`min_responses` no
   `qti_config.json`). Abaixo disso, a triangulação aparece com os valores nulos e a
   pergunta de reflexão preservada — o que já é o comportamento de `triangulate`.
   O propósito é estatístico e também de privacidade: com 3 respondentes numa turma
   de 30, o professor pode inferir quem respondeu.
4. **O link público não identifica a turma para quem o abre** além do necessário
   para responder.

---

## 8. Telas

**Ciclo — criar.** O professor informa a turma, a disciplina e **quantas aulas vai
acompanhar**. Vocabulário: "acompanhar", nunca "avaliar".

**Coleta de QTI — escolher a porta.** Duas opções explícitas: gerar o link para a
turma responder, ou enviar o relatório exportado do `avalie-seu-professor`.

**Link público — responder.** Consentimento, 24 perguntas em escala de 1 a 5,
envio. Sem login. Acessível em celular, que é o dispositivo real do estudante.

**Relatório da aula.** O que a observação mediu, a triangulação contra a coleta
vigente, e as recomendações de MTSS.

**Relatório do ciclo.** A trajetória dos índices ao longo das aulas e as duas
coletas de QTI. Sem veredito.

Todas as telas seguem o `DESIGN.md`: paleta fechada, WCAG 2.1 AA, sem gradiente,
sem `style` inline.

---

## 9. Erros e casos de borda

- **Importação com coluna faltando ou valor divergente do recálculo** → recusa o
  arquivo inteiro, nomeando a linha e a coluna. O motor já faz.
- **Importação de um formato que o `avalie-seu-professor` mudou** → o arquivo
  precisa declarar a própria versão, e a importação recusa versão desconhecida.
  Sem isso, uma mudança lá quebra a importação em silêncio.
- **Menos de 10 respostas** → não é erro. A coleta existe, o resultado não é
  exibível, a triangulação mostra a pergunta sem os valores.
- **Ciclo encerrado sem a última coleta** → a última aula fica em `WAITING_QTI`. O
  professor pode encerrar o ciclo assim mesmo, e o relatório declara a ausência.
- **Aula excluída no meio do ciclo** → o ciclo recalcula qual é a última.
- **O professor grava menos aulas do que declarou** → "a última" é a última aula
  efetivamente gravada quando o professor encerra o ciclo, não a de número `n`. O
  número declarado orienta o professor e nunca trava o encerramento; o relatório do
  ciclo declara quantas foram previstas e quantas aconteceram.
- **O professor grava mais aulas do que declarou** → nenhuma trava. As aulas
  excedentes são do meio do ciclo até que ele o encerre.

---

## 10. Segurança

O link público é **a única porta sem autenticação do sistema**. Requisitos:

- prazo de validade;
- limite de respostas, coerente com o tamanho da turma;
- revogável pelo professor a qualquer momento;
- resistente a envio repetido do mesmo navegador, sem persistir identificador que
  permita reconhecer a pessoa;
- nenhuma informação sobre o professor ou a turma além do necessário para responder.

O restante do sistema continua com autenticação obrigatória.

---

## 11. Testes

- Importação: arquivo válido, coluna ausente, valor divergente, versão desconhecida.
- Coleta nativa: consentimento obrigatório, resposta incompleta recusada, valor fora
  da escala recusado, limite de respostas, link expirado, link revogado.
- Privacidade: **nenhuma coluna de identidade existe nas tabelas de resposta**, e
  nenhum valor gravado permite ligar consentimento a resposta. Trava por teste, como
  `test_diarize_nao_grava_o_rotulo_da_voz_em_lugar_nenhum` faz para a voz.
- Estados: cada um marcado pelo passo que o alcança, e nenhum marcado por
  antecipação — o teste-espião de W2 é o padrão a seguir.
- Triangulação: a aula usa a coleta mais recente **anterior** a ela, nunca a
  posterior.
- Exportação: as nove tabelas saem preenchidas, e a origem do QTI viaja.

---

## 12. Fora do escopo de W3

- O QTI de 64 itens e a versão do professor.
- Cálculo de alfa de Cronbach no produto.
- Comparação entre professores ou entre turmas.
- Qualquer afirmação automática de melhora ou piora.
- Coleta repetida ao longo do ciclo além da primeira e da última.

---

## 13. Critérios de aceite de W3

1. Um professor cria um ciclo declarando o número de aulas, e o sistema sabe qual
   aula é a primeira e qual é a última.
2. Uma aula em `FIAS_COMPLETED` que seja a primeira do ciclo para em `WAITING_QTI`;
   uma do meio segue direto a `REPORT_READY`.
3. O relatório exportado pelo `avalie-seu-professor` é importado, recalculado e
   aceito; um arquivo com um valor adulterado é recusado nomeando a linha.
4. Um estudante responde pelo link público, em celular, sem login, e a resposta
   entra na coleta.
5. Nenhuma tabela de resposta tem coluna de identidade, e não há caminho no banco
   que ligue um consentimento a uma resposta.
6. Com menos de 10 respostas, a triangulação aparece com a pergunta de reflexão e
   sem os valores.
7. Uma aula se triangula contra a coleta mais recente anterior a ela, comprovado
   por um ciclo com duas coletas em datas diferentes.
8. As recomendações de MTSS aparecem enquadradas como reflexão, e nenhuma delas
   afirma erro do professor.
9. O relatório do ciclo mostra a trajetória dos índices e as duas coletas, e **não
   contém nenhuma afirmação de melhora ou piora**.
10. O link público expira, respeita o limite de respostas e pode ser revogado.
11. Nenhum texto visível usa "avaliação", "avaliar", "nota", "desempenho" ou
    "ranking".
12. A exportação traz as nove tabelas preenchidas, com a origem do QTI declarada.
13. As suítes continuam verdes: motor científico, serviço e interface.

---

## Anexo — Riscos declarados

**O tamanho.** Esta fatia tem um ator novo, duas portas de entrada, consentimento,
dois relatórios e cinco estados. É maior que W2. Se o plano de implementação passar
de vinte tarefas, decompor em duas fatias — importação e relatórios primeiro,
coleta nativa depois — é a saída recomendada.

**A dependência externa.** A importação depende do formato que o
`avalie-seu-professor` exporta. O requisito de versão declarada no arquivo existe
para que uma mudança lá falhe alto, e não em silêncio.

**O instrumento não está validado.** O `qti_config.json` inteiro está como
`PENDING_SCIENTIFIC_VALIDATION`. W3 implementa a coleta e o cálculo; não valida o
instrumento. Isso continua sendo trabalho de dissertação.
