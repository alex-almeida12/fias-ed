# Product

<!-- impeccable:product-schema 1 -->

<!--
Verdade de produto do FIAS-ED Web. Os títulos de seção estão em inglês porque
são lidos pelo Impeccable; o conteúdo é em português, como o resto do
repositório. Este arquivo não descreve o mundo visual — isso é DESIGN.md,
gerado por `/impeccable document` a partir do código. Fontes:
docs/PROMPT_MESTRE.md (as referências "§N" abaixo apontam para as seções
numeradas dele), ARCHITECTURE.md, fias-ed-shared/docs/ e o código de
fias-ed-web/.
-->

## Platform

web

## Users

**Primário — o professor participante da pesquisa.** Dá aula presencialmente,
grava o áudio com o equipamento que já tem (celular, gravador, notebook) e
depois, em outro momento e em outro lugar — sala dos professores, casa, fim de
expediente —, senta diante de um computador para enviar aquele arquivo e
entender como a aula aconteceu. Não é a hora da aula: é a hora da reflexão
sobre ela. Chega com pouco tempo, cansado, e quase sempre sem vocabulário
técnico de análise de interação. Recebe a conta pronta do administrador, com
senha provisória, e troca a senha no primeiro acesso. Só enxerga as próprias
aulas.

**Secundário — o ADMIN_LOCAL, que é o próprio pesquisador.** Opera o sistema na
máquina dele: cria e desativa contas de professor, cadastra escolas, turmas e
disciplinas, acompanha as aulas de todos os professores e, quando precisa
apoiar alguém, usa "agir como" para entrar na visão daquele professor — o que
fica registrado (`acesso_admin`) e é anunciado na tela enquanto durar.

**Não são usuários do sistema:** os estudantes não têm conta e nunca fazem
login; entram na pesquisa apenas como respondentes do questionário QTI, sem
identificação individual. Gestores, coordenação e secretaria não têm acesso —
por decisão de produto, não por falta de implementação (§85).

## Product Purpose

O FIAS-ED transforma o áudio de uma aula real em uma leitura pedagógica que o
professor consegue usar: quais padrões de interação aconteceram em sala (FIAS),
como os estudantes perceberam aquela aula (QTI), o que os dois juntos sugerem
(triangulação e interpretação MTSS Tier 1), e o que dá para experimentar na
próxima aula.

A promessa, e a única frase de abertura do produto, é: **"Grave sua aula.
Melhore sua prática docente."** (§14)

O sucesso é o professor abrir o sistema e pensar *"posso enviar o áudio da
minha aula e compreender melhor como ela aconteceu"* — e **nunca** *"estão me
avaliando"* (§85). A cadeia que a experiência precisa comunicar é:
aula → evidências → compreensão → reflexão → sugestões → melhoria.

Falha de produto, mesmo com tudo funcionando: uma tela que faça o professor se
sentir medido, comparado, fiscalizado ou classificado.

## Positioning

Três coisas que um produto vizinho não copiaria de verdade:

1. **O julgamento é do professor, não do sistema.** O FIAS-ED não produz nota,
   ranking, conceito nem diagnóstico clínico. Produz evidência rastreável e
   devolve a interpretação a quem deu a aula. Isso é deliberado e está escrito
   como critério de aceite, não como tom de voz (§31, §85, §86).
2. **Rastreabilidade científica como parte do produto.** Toda regra de FIAS,
   QTI e MTSS vive em JSON declarativo versionado (`fias-ed-shared/rules/`),
   validado por schema e por vetores de conformidade. Uma afirmação sem
   fundamentação na literatura não é suavizada: fica marcada
   `PENDING_SCIENTIFIC_VALIDATION` / `threshold_pending_validation` e a regra
   correspondente fica desligada (§19, §32). O produto prefere dizer "isto
   ainda não está validado" a inventar um número.
3. **Roda inteiro na máquina do usuário.** Nenhum áudio de aula, transcrição ou
   resposta de estudante sai do computador: sem nuvem, sem API externa, sem LLM
   externo para pontuar ou recomendar (§33, §47). O motor de recomendação é de
   regras, determinístico e auditável.

## Operating Context

- **Instalação:** Docker Compose na máquina local do pesquisador. Cinco
  serviços (`web`, `api`, `worker`, `db`, `migrate`); só o `web` publica porta,
  e só em `127.0.0.1:8080`. Sem exposição à rede local nem à internet. O
  professor acessa pelo navegador **daquela máquina**, em `localhost` (o cookie
  de sessão é `Secure`, então o navegador não o aceita por IP em HTTP puro).
- **Entrada do trabalho:** importar/enviar um arquivo de áudio já gravado. O
  sistema nunca obriga a gravar dentro dele; gravação interna é
  `OPTIONAL_FEATURE` para o futuro (§12). Formatos: MP3, WAV, M4A, AAC, FLAC.
  Limite atual de 1,5 GB, repetido no nginx e na API — os dois mudam juntos.
- **Aulas longas são o caso normal, não a exceção:** 10 a 90 minutos. O
  processamento é assíncrono (tabela `job`, worker com
  `SELECT … FOR UPDATE SKIP LOCKED`); o professor envia e volta depois.
- **Fluxo do professor (§13):** início → nova aula → turma → disciplina →
  enviar áudio → validação → processamento → transcrição → identificação das
  falas → revisão → FIAS → QTI → triangulação → MTSS → sugestões → relatório.
- **Dois momentos de revisão humana no meio do caminho:** confirmar qual voz é
  a do professor e, opcionalmente, revisar a transcrição. O sistema não decide
  sozinho o que é fala docente.
- **O QTI vem de fora do áudio:** as respostas dos estudantes entram por
  formulário manual, importação ou fotografia com OCR local, sempre com
  confirmação humana antes de virar dado (§28, §29).
- **Ciclo de vida da aula:** 18 estados, de `DRAFT` a `REPORT_READY`, mais
  `ERROR`. A fatia W1 implementada vai de `DRAFT` a `AUDIO_VALIDATED`; a W2
  continua daí.

## Capabilities and Constraints

**Implementado (fatia W1):** entrada com usuário e senha (Argon2id, sessão no
servidor com cookie opaco + token CSRF, mesma origem, sem CORS); contas de
professor criadas pelo admin com senha provisória; escolas, turmas e
disciplinas; aulas; envio de áudio com barra de progresso; conferência
automática do arquivo (formato real, MIME, extensão, tamanho, duração, canais,
sample rate — nunca só a extensão); "agir como" do admin, auditado.

**Restrições duráveis:**

- **Nenhuma regra científica é reimplementada no Web.** O backend importa
  `fias_ed_engine` do `fias-ed-shared`, que lê os JSON de `rules/`. Web e
  Android precisam produzir a mesma saída nos mesmos vetores de
  `conformance/cases/`.
- **O áudio original nunca é modificado.** Pipeline: original → cópia de
  trabalho → normalização → processamento. SHA-256 registrado, nome interno em
  UUID, arquivo fora do banco (nada de BLOB).
- **Funciona offline.** Sem Google Fonts em runtime (fontes empacotadas
  localmente), sem API externa, sem LLM externo. O PostgreSQL só é alcançável
  pela API, em rede interna do Docker; API e worker usam `fias_ed_app`, sem DDL.
- **Privacidade dos estudantes:** sem reconhecimento facial, sem biometria de
  voz, sem identificação individual pela voz. O rótulo padrão é `ALUNO`. Nomes
  de estudante não são armazenados sem necessidade (§48).
- **Retenção e base legal:** retenção de 5 anos após a conclusão da pesquisa;
  exclusão é remoção física, não soft delete. **A base legal LGPD está em
  aberto — `PENDING`, a definir pelo pesquisador com o CEP.** Nenhum texto de
  interface pode afirmar uma base legal enquanto isso não for resolvido.
- **Lacunas científicas são visíveis, não maquiadas.** Limiares de WER, DER e
  kappa, e parte das regras MTSS, estão como `PENDING_SCIENTIFIC_VALIDATION`.
  Qualquer tela que mostre esses números precisa carregar a ressalva junto.

**Vocabulário — restrição de produto, não preferência de estilo** (abertura do
prompt mestre). A interface do professor **usa**: "Adicionar aula", "Enviar
áudio da aula", "Analisar minha aula", "Entender minha aula", "Ver padrões de
interação", "Conhecer a percepção dos estudantes", "Pontos para reflexão",
"Sugestões para próximas aulas", "Melhorar minha prática". A interface **nunca**
usa: "avaliação", "avaliar professor", "nota", "desempenho", "ranking",
"professor inadequado", "iniciar avaliação". Recomendação se escreve como
convite — "Considere…", "Você pode experimentar…", "Uma possibilidade é…",
"Este padrão pode indicar…" — nunca como veredito (§33).

Mensagens de progresso são as do §36, em linguagem de pessoa: "Preparando sua
aula…", "Transformando áudio em texto…", "Identificando os momentos de fala…",
"Organizando as interações…", "Analisando padrões da aula…", "Integrando as
respostas dos estudantes…", "Preparando a interpretação pedagógica…", "Gerando
sugestões…", "Preparando seu relatório…". Os 18 estados técnicos existem no
banco e na API; na tela, cada um tem um texto humano
(`frontend/src/app/status.ts`).

**Terminologia interna** (banco, API, código — não necessariamente tela): FIAS
(Flanders Interaction Analysis System), QTI (Questionnaire on Teacher
Interaction), MTSS Tier 1, triangulação, diarização, ASR, segmento, falante,
indicador. O dicionário completo está em
`fias-ed-shared/docs/ENTITY_DICTIONARY.md` (20 entidades).

## Brand Commitments

Compromissos que o usuário fixou e que o trabalho futuro preserva. São
vinculantes; o mundo visual que os materializa é assunto de `DESIGN.md`.

- **Nome:** FIAS-ED. **Frase de marca:** "Grave sua aula. Melhore sua prática
  docente."
- **Paleta oficial e fechada** (§5): Navy `#2F4156`, Teal `#567C8D`, Sky Blue
  `#C8D9E6`, Beige `#F5EFEB`, White `#FFFFFF`, mais cinco cores semânticas de
  estado. Nenhuma outra cor na interface. Sem gradiente decorativo, sem glow. A
  interface é predominantemente clara (branco + beige em 65–75% da área).
- **Duas famílias tipográficas** (§6): **Ubuntu** para interface, **Rokkitt**
  para editorial (títulos ≥ 24 px, cabeçalhos de relatório, frases pedagógicas)
  — nunca Rokkitt em tabela, campo de formulário, número pequeno ou rótulo.
  Ambas empacotadas localmente, funcionando offline. No Android, o equivalente
  é `FIASTypography`; Roboto não é a fonte predominante.
- **Fonte única dos tokens:** `fias-ed-shared/design-tokens/tokens.json` →
  `tokens.css`. Se documento e token divergirem, o token vence.
- **Identidade pretendida** (§4): profissional, acadêmica, contemporânea,
  humana, simples, sóbria, confiável, institucional, baseada em dados.
- **Antirreferências explícitas** (§7): não pode parecer chatbot, produto de IA
  generativa, SaaS genérico, template automático nem dashboard futurista.
  Proibidos: glassmorphism, blobs, glow, cards em excesso, `border-radius`
  exagerado, ícones de estrela, cérebro, robô ou sparkle, ilustrações genéricas,
  gráficos decorativos. Proibidas também as frases de marketing de IA ("AI
  powered", "insights inteligentes", "transforme sua jornada", "desbloqueie seu
  potencial"). **A tecnologia fica nos bastidores; o professor é o
  protagonista** (§86).
- **Idioma:** português do Brasil, em toda a interface e em toda mensagem de
  erro. Sem internacionalização prevista.
- **Critério de aceite visual (§84):** antes de considerar uma tela pronta,
  responder "isto parece um produto feito para professores ou um template
  gerado por IA?". Se parecer template, refatorar.

## Evidence on Hand

**Existe no repositório:**

- `docs/PROMPT_MESTRE.md` — requisitos originais do pesquisador (2026-09-21),
  86 seções, fonte versionada e não editável.
- `fias-ed-shared/docs/` — DESIGN_SYSTEM.md, UI_REFERENCES.md (referências de
  interface pesquisadas, com o que inspira e o que não copiar), FIAS.md,
  QTI.md, MTSS.md, PRIVACY.md, ENTITY_DICTIONARY.md, DATABASE_MODEL.md,
  RESEARCH_INVENTORY.md, ANALISE_MODELOS_EXISTENTES.md,
  SCIENTIFIC_TRACEABILITY.md, SCIENTIFIC_REPRODUCIBILITY.md.
- `fias-ed-shared/rules/`, `schemas/` e `conformance/cases/` — regras, as 20
  entidades e os vetores de conformidade.
- `fias-ed-shared/engine-py/` — motor de referência em Python, com testes.
- `fias-ed-shared/design-tokens/` — tokens, build CSS e as fontes .woff2/.ttf.
- Base científica do mestrado, fora do repositório e **somente leitura**, em
  `…/mestrado/artigos selecionados/` (inclui `experimentos/`, com o
  classificador BERTimbau já treinado). Integridade verificada por
  `.source-snapshot.json`.

**Não existe — e não pode ser inventado por trabalho futuro:**

- Nenhum áudio real de aula versionado. O que existe é um WAV sintético gerado
  por `scripts/smoke.py` para teste.
- Nenhuma resposta QTI real de estudante e nenhum relatório de aula real.
- Nenhum depoimento, estudo de caso, logotipo de escola, número de usuários,
  métrica de adoção, preço, licença ou citação de imprensa. O produto não tem
  clientes: tem participantes de pesquisa.
- Nenhum benchmark de WER/DER/kappa medido neste projeto; os limiares estão
  `PENDING_SCIENTIFIC_VALIDATION`.
- Os pesos do BERTimbau ficam fora do Git.

## Product Principles

1. **O professor é o protagonista; o sistema é testemunha.** Toda tela devolve o
   que aconteceu na aula e deixa a conclusão com quem deu a aula. Nada de
   veredito, nota, comparação entre professores ou linguagem de fiscalização.
2. **Evidência antes de interpretação.** Nenhuma afirmação pedagógica aparece
   sem o dado que a sustenta ao alcance. O que não tem fundamentação aparece
   marcado como pendente, não escondido nem arredondado.
3. **A tecnologia fica nos bastidores.** ASR, diarização, BERTimbau, FIAS, QTI e
   MTSS existem para produzir uma leitura compreensível. O nome do método pode
   aparecer; o jargão do método não substitui a frase que o professor entende.
4. **Sóbrio por convicção, não por timidez.** A identidade é acadêmica e
   institucional porque o conteúdo é sensível e o produto precisa ser levado a
   sério — o que exige tipografia, hierarquia e espaçamento impecáveis, não
   ornamento.
5. **Privacidade e execução local são parte da promessa.** O áudio de uma aula e
   a voz de crianças não saem da máquina. Qualquer funcionalidade futura que
   exija rede é mudança de produto, não detalhe de implementação.

## Accessibility & Inclusion

**Meta declarada: WCAG 2.1 AA.** O que já sustenta isso e não pode regredir:

- `lang="pt-BR"` no documento; toda a interface e toda mensagem de erro em
  português claro.
- Pares de contraste de texto permitidos e **proibidos** fixados no design
  system (`teal/beige`, `sky/white` e `teal/sky` nunca como texto sobre fundo).
- Foco visível em todo elemento interativo (contorno de 3px em teal, com
  `outline-offset`), sem remoção de outline.
- Navegação por teclado em todo o fluxo; todo campo com rótulo associado;
  mudanças de estado anunciadas (`role="status"` na faixa de "agindo como").
- Cor nunca é o único portador de significado — estado de aula tem texto, não só
  cor.

Requisitos do contexto de uso: o professor chega cansado e com pressa, e pode
estar em tela pequena; a Task 17 revisa cada tela em 360 px e 1280 px. Áudio não
é meio de comunicação da interface — o áudio é o dado de entrada, e tudo que o
sistema devolve é texto e dado visual.
