# Spec — Subprojeto 2, fatia W2: `fias-ed-web` — Pipeline

Fatia W2 do subprojeto Web do FIAS-ED. Continua de onde a W1 parou: a aula sai
de `AUDIO_VALIDATED` e chega a `FIAS_COMPLETED`.

Referências: `docs/PROMPT_MESTRE.md` (citado como "§N"), `ARCHITECTURE.md`,
`fias-ed-shared/docs/` (DESIGN_SYSTEM, PRIVACY, ENTITY_DICTIONARY,
ANALISE_MODELOS_EXISTENTES, RESEARCH_INVENTORY, SCIENTIFIC_REPRODUCIBILITY),
`fias-ed-web/PRODUCT.md`, `fias-ed-web/DESIGN.md` e o spec da W1
(`2026-09-22-fias-ed-web-w1-fundacao-design.md`).

## 0. Posição na decomposição

A decomposição do subprojeto Web foi fixada no spec da W1 e **não é reaberta
aqui**:

| Fatia | Conteúdo | Termina em |
|---|---|---|
| W1 Fundação (entregue) | Compose, PostgreSQL + Alembic, autenticação, segurança base, React + design system, Home/Dashboard/Nova Aula, upload e validação | `AUDIO_VALIDATED` |
| **W2 Pipeline** (este documento) | cópia de trabalho, normalização, chunks, ASR, diarização, "qual destas vozes é você?", revisão da transcrição, classificação FIAS, tela de padrões de interação | `FIAS_COMPLETED` |
| W3 Percepção e relatório | QTI (manual, CSV, OCR), triangulação, MTSS, sugestões, Relatório da Aula (PDF), exportação do dataset | `REPORT_READY` |
| W4 Auditorias | auditorias de segurança completas, testes do §76, áudios longos, auditoria visual final | — |

## 1. Objetivo de W2

O professor envia o áudio de uma aula e passa a **compreender os padrões de
interação que aconteceram em sala**, com a evidência ao lado de cada afirmação.

O sucesso de W2 é o professor abrir a aula e pensar "agora eu entendo como essa
aula aconteceu" — nunca "estão me avaliando" (§85). A cadeia que a experiência
comunica é: aula → evidências → compreensão.

## 2. Decisões tomadas no desenho

Registradas aqui porque governam o resto do documento.

1. **A W2 é engenharia, não pesquisa.** O §21 manda comparar `tiny`/`base`/`small`
   por WER, tempo e RAM. Medir WER exige áudio real de aula com transcrição de
   referência, e o projeto não tem nenhum (`PRODUCT.md`, "Evidence on Hand"). A
   escolha do modelo é feita **por tempo e pico de memória**; WER e DER seguem
   `PENDING_SCIENTIFIC_VALIDATION` como o `RESEARCH_INVENTORY.md` já registra. A
   qualidade da transcrição é julgada pelo professor na tela de revisão.
2. **A diarização separa o professor do resto, e nada além disso.** O FIAS
   precisa de fala docente, fala discente e silêncio/confusão — nunca de
   distinguir o aluno A do aluno B. Não existe `ALUNO_1`/`ALUNO_2` em lugar
   nenhum, nem no banco. Os embeddings de voz são descartados assim que os
   segmentos são atribuídos (§48).
3. **A revisão da transcrição corrige falante e texto.** Não é leitura passiva
   nem só troca de atribuição.
4. **Diarização com `pyannote`, alinhada ao ASR** (abordagem A). Exige conta no
   Hugging Face e aceite de termos **uma vez, na instalação**; em execução,
   nada de rede. Sem degradação silenciosa: se a diarização falhar, a aula vai
   para `ERROR` com mensagem humana.
5. **A tela de padrões de interação mostra tudo na mesma página** — faixa de
   tempo, observações, matriz de transições e índices, sem seção recolhida.
   Registrada em contrário a uma ressalva do desenho (a matriz 10×10 é densa e
   puxa a leitura para o lado do relatório técnico); decisão do pesquisador.

## 3. Fluxo e máquina de estados

Nenhum status novo: todos os 18 já foram definidos em W1. A W2 acrescenta
quatro tipos de job à fila que já existe (tabela `job`, worker com
`SELECT … FOR UPDATE SKIP LOCKED`).

```
AUDIO_VALIDATED
   │ job prepare_audio        → PREPROCESSING
   │   original intocado → cópia de trabalho → normalização 16 kHz mono
   │   → plano de chunks com deslocamento global
   │ job transcribe           → TRANSCRIBING → TRANSCRIBED
   │   faster-whisper por chunk; timestamps somados ao deslocamento
   │ job diarize              → DIARIZING
   │   pyannote no áudio normalizado inteiro; alinhamento por sobreposição
   ▼
READY_FOR_SPEAKER_REVIEW     ← humano: "qual destas vozes é você?"
   ▼                             embeddings descartados aqui
READY_FOR_TRANSCRIPT_REVIEW  ← humano: corrige falante e texto (opcional)
   ▼
READY_FOR_FIAS
   │ job classify_fias        → BERTimbau por segmento
   │   → constrain_by_role → segments_to_intervals
   │   → transition_matrix → compute_indices
   ▼
FIAS_COMPLETED
```

**O chunking é do ASR, não da diarização.** O Whisper precisa de pedaços; o
`pyannote` recebe o arquivo inteiro, porque é exatamente na fronteira entre
chunks que a troca de falante se perde. Os chunks carregam deslocamento global e
os timestamps voltam somados (§18): nenhuma camada acima sabe que houve corte.

**Os dois passos humanos ficam antes do FIAS.** A classificação sempre roda
sobre o texto e a atribuição que o professor aprovou. Se ele reabrir a revisão
depois de `FIAS_COMPLETED`, a aula volta para `READY_FOR_FIAS` e reclassifica —
evidência e resultado nunca ficam fora de sincronia.

**Idempotência.** Um job interrompido volta para a fila e reprocessa do início
do seu estágio, nunca do zero. Cada estágio grava seu resultado numa transação
só, ao final.

## 4. Fronteira com o `fias-ed-shared`

Inalterada e inegociável: **nenhuma regra científica é implementada no backend
Web.** O `classify_fias` produz `(segmento, logits, papel)` e entrega a
`constrain_by_role`, `segments_to_intervals`, `transition_matrix` e
`compute_indices`, que já existem em `fias_ed_engine` e já passam em
`conformance/cases/`. O Web orquestra, persiste e apresenta; o motor decide.

A matemática do FIAS **não é retestada** na W2. Retestá-la duplicaria a fonte de
verdade.

## 5. Modelos e artefatos

Nenhum peso de modelo entra no Git. Ficam num volume, populados por um script de
setup, e o caminho vem do `.env`.

### 5.1 ASR — `faster-whisper`

- Idioma fixado em `pt`. Sem autodetecção: o produto é só pt-BR e detecção
  automática erra em áudio de sala com ruído.
- Decodificação determinística (temperatura 0). O §44 exige reprodutibilidade:
  a mesma aula reprocessada tem de dar o mesmo texto.
- O tamanho não vai chumbado. Uma tarefa do plano mede `tiny`, `base` e `small`
  em áudios de 10, 30, 50, 60 e 90 minutos, registrando **tempo e pico de
  memória**, e o vencedor vira o padrão no `.env`, documentado no README com a
  tabela que o gerou.

### 5.2 Diarização — `pyannote/speaker-diarization-3.1`

- Sem informar número de falantes; o modelo estima.
- Baixado uma vez no setup com token do Hugging Face. Em execução,
  `HF_HUB_OFFLINE=1`.
- O README ganha o passo de obter o token, ao lado do passo que já existe para
  os pesos do BERTimbau.

### 5.3 Classificação — BERTimbau já treinado

Vem de `artigos selecionados/experimentos` (somente leitura), F1 macro 0,7246,
kappa 0,77.

**O mapa índice→categoria FIAS já existe; a W2 consome, não redefine.** O
`config.json` do checkpoint grava apenas `LABEL_0..LABEL_9` — os nomes das
categorias **não ficam no checkpoint** (`ANALISE_MODELOS_EXISTENTES.md` §2.2).
O mapa foi reconstruído, verificado contra 100% do TSV de teste, e está
declarado em dois lugares do shared:

- `scientific-config/models.json`, no campo `label_map`:
  `fias_category = argmax(logits) + 1`;
- `rules/fias_rules.json`, em `classifier.logit_index_offset = 1`.

Portanto, o requisito da W2 é **proibitivo, não construtivo**: o backend obtém a
categoria pelo `logit_index_offset` do `fias_rules.json` e **nunca** lê
`id2label` do checkpoint. Um mapa trocado não falha visivelmente — produz uma
aula inteira classificada errado com aparência normal —, então existe teste que
reprova se o código passar a depender do `id2label`.

O formato de entrada também vem de lá e não é escolha da implementação:
**par de turnos** (`tokenizer(text_a, text_b)`), WordPiece cased, `max_length=256`,
sem lowercasing e sem prefixo de falante no texto
(`ANALISE_MODELOS_EXISTENTES.md` §2.3 e §2.4).

### 5.4 Rastreabilidade e integridade (§44, §67, §81)

O `scientific-config/models.json` já é o registro versionado dos modelos, com
SHA-256 e tamanho por artefato, licença, limitações, `forbidden_files` e
`validation_status`; `scripts/verify_models.py` e
`engine-py/tests/test_models_registry.py` já o verificam. A W2:

- confere os artefatos **contra esse registro** na carga, em vez de manter uma
  lista própria de hashes;
- recusa a carga se algum `forbidden_files` (`training_args.bin`,
  `optimizer.pt`, `rng_state.pth`, `scaler.pt`, `scheduler.pt`) estiver
  presente no diretório do modelo;
- popula `ModeloIA` a partir do registro, e cada `Processamento` guarda qual
  modelo, quais parâmetros, `app_version` e `rules_version`.

O `pyannote` e o `faster-whisper` entram no mesmo registro quando forem
escolhidos, seguindo o formato que já existe.

**Licença.** O registro anota que os dados de treino do BERTimbau são
CC BY-NC-SA 4.0 — **uso não comercial**. O FIAS-ED é pesquisa acadêmica, o que
está dentro da licença, mas a restrição fica registrada aqui para não ser
descoberta tarde.

### 5.5 Memória

O worker processa um job por vez e cada estágio carrega e descarrega seu modelo;
os modelos nunca coexistem. `small` em int8 e o `pyannote` ficam na casa de 1 GB
cada, dentro dos 6 GB da máquina de referência.

## 6. Banco de dados

Entidades novas, todas com schema já definido em `fias-ed-shared/schemas/entities/`:
`Transcricao`, `Segmento`, `Falante`, `ClassificacaoFIAS`, `IndicadorFIAS`,
`ModeloIA`. Mais o preenchimento dos campos de `Processamento` que a W1 deixou
vazios.

`Falante` guarda apenas o papel (`PROFESSOR` ou `ALUNO`) — nunca um agrupamento
de voz por estudante. Nenhum embedding é persistido.

## 7. Privacidade (§47, §48, LGPD)

O `PRIVACY.md` **já promete** o campo `Segmento.text_pseudonymized`, com nomes
de estudantes substituídos por `[NOME]`, e já define que a exportação usa essa
versão e falha inteira se um segmento selecionado não a tiver. Isso é
funcionalidade da W2, porque é a W2 que cria a transcrição.

- Todo segmento recebe `text_pseudonymized` junto com o texto original.
- A pseudonimização roda sobre o texto do ASR **e** sobre o texto revisado pelo
  professor — editar a transcrição não pode reintroduzir um nome em claro na
  versão pseudonimizada.
- A exclusão de uma aula passa a apagar também transcrição e segmentos, de forma
  real (remoção física), como o `PRIVACY.md` já exige para áudio.

A detecção de nome próprio em português falado é desenho de implementação, não
está resolvida aqui; o plano a trata como tarefa própria, com testes.

## 8. Telas

Tudo segue o `DESIGN.md`: paleta fechada, Rokkitt só em título ≥ 24 px, listas
com divisória de 1px em vez de grade de cards, plano em repouso, e o vocabulário
do `PRODUCT.md` (nada "avalia"; o sistema **analisa** e devolve padrões).

### 8.1 Processamento em andamento

A página da aula mostra as mensagens do §36 em linguagem de pessoa
("Transformando áudio em texto…", "Identificando os momentos de fala…",
"Analisando padrões da aula…"). Nenhum termo técnico. O professor envia e volta
depois; nada depende de ele ficar esperando.

### 8.2 "Qual destas vozes é você?" — `READY_FOR_SPEAKER_REVIEW`

Lista os grupos de voz, cada um com quanto tempo falou, em quantos momentos, e
dois ou três trechos curtos para ouvir. O professor aponta um; todo o resto vira
ALUNO na mesma ação.

Os grupos se chamam **"Voz 1", "Voz 2"** — nunca "Falante A" nem "Aluno 3".
Depois da escolha deixam de existir como identidades: viram "Você" e "ALUNO".

Um grupo só detectado **não é erro**: a tela aparece com um grupo e o professor
confirma. Pode ser uma aula expositiva legítima.

### 8.3 Revisão da transcrição — `READY_FOR_TRANSCRIPT_REVIEW`

A maior tela da W2. Cada segmento tem horário, quem falou (alternável entre Você
e ALUNO) e o texto (editável), com um controle para ouvir o áudio naquele ponto
— ouvir é como se conserta atribuição errada.

- **Salvamento incremental, por segmento**, ao sair do campo. Não um formulário
  único que se perde se o navegador fechar no minuto 40.
- **Paginação por blocos de tempo** (fatias de cinco minutos) em vez de
  virtualização de lista: mais simples, sem comportamento estranho de rolagem,
  casa com o jeito como o professor pensa a aula e dá fronteira natural de
  salvamento.
- A revisão é opcional (§24): existe saída clara de "está bom assim, seguir" a
  qualquer momento.

**Acessibilidade (WCAG 2.1 AA, meta declarada no `PRODUCT.md`).** É a tela mais
hostil a leitor de tela do produto, e o spec não deixa isso para a implementação
descobrir:

- cada segmento é um grupo rotulado com o horário;
- a alternância de falante é um controle de dois estados com rótulo textual, não
  só cor;
- a navegação por teclado percorre segmento a segmento sem armadilha de foco, e
  o salvamento incremental anuncia sucesso e falha por `role="status"`;
- o controle de áudio de cada segmento tem nome acessível com o horário.

### 8.4 Padrões de interação — `FIAS_COMPLETED`

Ordem de leitura na página, tudo visível, nada recolhido:

1. **Faixa de tempo da aula** — quem falou quando, usando as cores que o
   `tokens.json` já reserva para os grupos FIAS (influência indireta em teal,
   direta em navy, fala do estudante em sky, silêncio em bege). Legível em
   três segundos.
2. **Observações em linguagem de pessoa**, cada uma ancorada em trechos reais da
   transcrição — a evidência ao lado do fato.
3. **Matriz de transições 10×10**, como **tabela de números**, não mapa de
   calor: um heatmap exigiria uma rampa de tons intermediários e a paleta é
   fechada em dez cores; além disso, matriz de Flanders na literatura é tabela.
4. **Os seis índices** (TT, PT, SC, I/D, PIR, razão de resposta), com o nome por
   extenso e o que cada um mede.

**Nenhum índice aparece ao lado de um limiar de "bom/ruim".** Os limiares do
MTSS estão `PENDING_SCIENTIFIC_VALIDATION`; mostrar um número contra uma meta
não validada inventa um veredito que a ciência do projeto não sustenta, além de
produzir exatamente o boletim que o produto promete não ser (§85).

## 9. Erros e casos de borda

Todos com mensagem humana, sem jargão (§36):

| Situação | Resultado |
|---|---|
| Áudio sem fala reconhecível | `ERROR` — "Não conseguimos identificar fala neste áudio. Confira se o arquivo é mesmo o da aula." |
| Diarização falha (modelo ausente, token não configurado, áudio curto demais) | `ERROR` com mensagem humana. Sem degradação silenciosa. |
| Uma voz só detectada | Não é erro; a tela de escolha aparece com um grupo |
| Job interrompido | Volta para a fila; reprocessa do início do estágio |
| Professor reabre a revisão depois do FIAS | Volta a `READY_FOR_FIAS` e reclassifica |

**Higiene de disco.** Cópia de trabalho e chunks são grandes (90 min a 16 kHz
mono passam de 170 MB) e são apagados ao fim do estágio que os consome. O
original nunca é tocado (§17).

## 10. Segurança

- **`ffmpeg`/`ffprobe`** (§57): lista de argumentos, sem shell, seguindo o
  padrão que a W1 já estabeleceu em `app/audio/probe.py`.
- **XSS** (§59): a transcrição é o primeiro texto longo editável pelo usuário
  que o produto renderiza de volta. `dangerouslySetInnerHTML` é proibido em todo
  o caminho da transcrição, e o relatório da W3 herda essa transcrição.
- **Integridade dos modelos** (§67): SHA-256 conferido na carga e registrado em
  `ModeloIA`. Um arquivo de modelo trocado não passa despercebido.
- Autorização segue a da W1: o professor só vê as próprias aulas; o admin usa
  "agir como", auditado.

## 11. Testes

A suíte inteira roda no `docker-compose.test.yml` **sem modelo e sem GPU**, como
já roda hoje. Os três modelos entram por uma interface fina e são substituídos
por implementações falsas nos testes: um ASR que devolve segmentos fixos, uma
diarização que devolve turnos fixos, um classificador que devolve logits fixos.

Testa-se o que é nosso:

- alinhamento entre segmentos do ASR e turnos da diarização;
- atribuição professor/ALUNO e descarte dos embeddings;
- verificação do mapa índice→categoria FIAS (§5.3);
- máquina de estados dos jobs, incluindo idempotência e reprocessamento;
- salvamento incremental da revisão;
- pseudonimização, incluindo o caso do texto revisado;
- persistência com rastreabilidade (`ModeloIA`, `Processamento`).

Separado: um teste de integração **opcional e marcado como lento**, que roda os
modelos de verdade num áudio sintético, fora da suíte padrão. É ele que a tarefa
de medição de tempo e memória usa.

## 12. Fora do escopo de W2

QTI em qualquer forma, OCR, triangulação, MTSS, recomendações, Relatório da
Aula, exportação do dataset, gravação dentro do app (`OPTIONAL_FEATURE`, §12),
medição de WER e DER, e qualquer trabalho do subprojeto Android.

## 13. Critérios de aceite de W2

1. Uma aula em `AUDIO_VALIDATED` percorre todo o pipeline até `FIAS_COMPLETED`
   pela interface, sem intervenção no banco.
2. Áudios de 10, 30, 50, 60 e 90 minutos processam até o fim; a tabela de tempo
   e pico de memória por tamanho de modelo está no README.
3. Timestamps continuam globais depois do chunking: o último segmento de uma
   aula de 90 min tem horário coerente com a duração do arquivo.
4. A tela "qual destas vozes é você?" aparece com os grupos detectados, e a
   escolha atribui todo o resto a ALUNO; nenhum embedding fica no banco.
5. A revisão salva por segmento e sobrevive a fechar e reabrir o navegador no
   meio.
6. Todo segmento tem `text_pseudonymized`, inclusive depois de o professor
   editar o texto.
7. A categoria FIAS sai do `classifier.logit_index_offset` do `fias_rules.json`;
   nenhum código lê `id2label` do checkpoint, com teste que reprova se passar a
   ler.
8. A carga confere os artefatos contra `scientific-config/models.json` e recusa
   o modelo se um SHA-256 divergir ou se algum `forbidden_files` estiver
   presente no diretório.
9. `ModeloIA` e `Processamento` permitem reproduzir uma classificação: modelo,
   SHA-256, parâmetros, `app_version` e `rules_version`.
10. A tela de padrões de interação mostra faixa de tempo, observações com
   evidência, matriz e índices, e **nenhum índice ao lado de limiar de bom/ruim**.
11. Áudio sem fala e falha de diarização terminam em `ERROR` com mensagem
    humana; um grupo de voz só não é erro.
12. pytest e vitest verdes, sem modelo e sem GPU; bandit, pip-audit e npm audit
    sem HIGH/CRITICAL não tratados.
13. Telas revisadas com Impeccable e aprovadas no §84, em 360 px e 1280 px.
