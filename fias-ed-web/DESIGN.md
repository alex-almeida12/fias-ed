---
name: FIAS-ED Web
description: O caderno de campo do professor sobre a própria aula — sóbrio, claro e sem veredito.
colors:
  tinta-permanente: "#2F4156"
  azul-anotacao: "#567C8D"
  papel-milimetrado: "#C8D9E6"
  papel-caderno: "#F5EFEB"
  folha-branca: "#FFFFFF"
  grafite: "#5B6673"
  erro: "#9B3B3B"
  acerto: "#3E6B4F"
  atencao: "#7A5512"
  informacao: "#3F6A8A"
typography:
  display:
    fontFamily: "Rokkitt, Georgia, serif"
    fontSize: "2.75rem"
    fontWeight: 600
    lineHeight: 1.1
  headline:
    fontFamily: "Rokkitt, Georgia, serif"
    fontSize: "2.125rem"
    fontWeight: 600
    lineHeight: 1.15
  title:
    fontFamily: "Rokkitt, Georgia, serif"
    fontSize: "1.625rem"
    fontWeight: 600
    lineHeight: 1.2
  subtitle:
    fontFamily: "Ubuntu, system-ui, sans-serif"
    fontSize: "1.188rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Ubuntu, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Ubuntu, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
  button:
    fontFamily: "Ubuntu, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 500
    lineHeight: 1.2
  caption:
    fontFamily: "Ubuntu, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "4px"
  md: "6px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "24px"
  "6": "32px"
  "7": "48px"
  "8": "64px"
components:
  button-primary:
    backgroundColor: "{colors.tinta-permanente}"
    textColor: "{colors.folha-branca}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "8px 24px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.azul-anotacao}"
    textColor: "{colors.folha-branca}"
  button-secondary:
    backgroundColor: "{colors.folha-branca}"
    textColor: "{colors.azul-anotacao}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "8px 24px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.papel-milimetrado}"
    textColor: "{colors.tinta-permanente}"
  button-tertiary:
    backgroundColor: "transparent"
    textColor: "{colors.azul-anotacao}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "8px 8px"
    height: "44px"
  input-field:
    backgroundColor: "{colors.folha-branca}"
    textColor: "{colors.tinta-permanente}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
    height: "44px"
  banner:
    backgroundColor: "{colors.papel-caderno}"
    textColor: "{colors.tinta-permanente}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "12px 16px"
  dialog:
    backgroundColor: "{colors.folha-branca}"
    textColor: "{colors.tinta-permanente}"
    rounded: "{rounded.md}"
    padding: "32px"
    width: "32rem"
  empty-state:
    backgroundColor: "{colors.papel-caderno}"
    textColor: "{colors.tinta-permanente}"
    rounded: "{rounded.md}"
    padding: "48px 24px"
  badge-progress:
    backgroundColor: "{colors.papel-milimetrado}"
    textColor: "{colors.tinta-permanente}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "4px 12px"
  badge-attention:
    backgroundColor: "{colors.papel-caderno}"
    textColor: "{colors.tinta-permanente}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "4px 12px"
  badge-done:
    backgroundColor: "{colors.folha-branca}"
    textColor: "{colors.tinta-permanente}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "4px 12px"
  topbar:
    backgroundColor: "{colors.tinta-permanente}"
    textColor: "{colors.folha-branca}"
    typography: "{typography.body}"
    padding: "12px 16px"
---

# Design System: FIAS-ED Web

> A fonte normativa dos valores é `fias-ed-shared/design-tokens/tokens.json`
> (`tokens_version: "1.0.0"`), compilada em `build/tokens.css`. Se este
> documento e o token divergirem, o token vence e este arquivo é corrigido.
> O frontmatter acima espelha os tokens; a prosa explica onde e por quê.

## Overview

**Creative North Star: "O Caderno de Campo"**

O FIAS-ED é o caderno em que o professor registra e relê a própria aula. Não é
um painel que o observa, não é um relatório que alguém emitiu sobre ele: é a
anotação dele, organizada. Essa metáfora decide tudo o que vem depois — a
superfície é papel, a tipografia editorial é a letra de quem escreve, a
tipografia de interface é o dado anotado, e a evidência fica sempre ao lado do
fato, nunca substituída por um placar.

A densidade é baixa e o ritmo é largo. O produto é usado por alguém cansado, no
fim do expediente, para reler uma aula de 50 minutos — então o espaço em branco
não é estética, é condição de leitura. A página tem no máximo 72rem, respira em
passos de 4 a 64px, e prefere uma lista honesta a uma grade de cards. A cor é
quase toda papel: branco e bege ocupam 65–75% de qualquer tela, e o azul entra
só onde há ação, navegação ou hierarquia.

O sistema é discreto e acolhedor, não frio. A contenção vem da confiança, não
da timidez: alvos de 44px, cantos de 4px, uma linha de 1px onde outros
sistemas poriam uma sombra. As rejeições são confirmadas e vinculantes
(prompt §7): nada de gradiente, glow, glassmorphism, blob, card em excesso,
raio exagerado, ícone de estrela, cérebro, robô ou sparkle, ilustração genérica
ou gráfico decorativo. A tecnologia fica nos bastidores.

**Key Characteristics:**

- Papel antes de pigmento: branco e bege dominam; o azul é escasso por decisão.
- Duas vozes tipográficas com fronteira rígida: Rokkitt escreve, Ubuntu informa.
- Plano em repouso: profundidade por camada de cor e linha de 1px, não por sombra.
- Alvo generoso, canto discreto: 44px de altura mínima, 4px de raio.
- Evidência ao lado do fato; nunca um veredito sozinho na tela.

## Colors

Uma paleta fechada de dez cores, nomeada pelos materiais de um caderno: cinco
de marca e cinco de estado. Nenhuma outra cor pode aparecer na interface.

### Primary

- **Tinta Permanente** (`#2F4156`): a cor do que foi escrito para ficar. Texto
  corrido, todos os títulos, a barra de navegação inteira, o fundo do botão
  primário, o rótulo dentro de qualquer badge. É a única cor de texto padrão do
  produto — `--color-text` aponta para ela.

### Secondary

- **Azul de Anotação** (`#567C8D`): a cor do que foi acrescentado à margem.
  Ação secundária (fundo branco, texto e borda nesta cor), ação terciária,
  links, o anel de foco de 3px, o `accent-color` da barra de progresso, e a
  série "influência indireta" nos gráficos FIAS.

### Tertiary

- **Papel Milimetrado** (`#C8D9E6`): a superfície que sinaliza sem gritar.
  Todas as bordas e divisórias do produto (`--color-border`), o fundo da faixa
  "você está agindo como", o fundo do badge de etapa em andamento, e a série
  "fala do estudante" nos gráficos. Nunca recebe texto em Azul de Anotação.

### Neutral

- **Papel de Caderno** (`#F5EFEB`): a segunda superfície. É onde o produto
  convida a ler e a pensar — o bloco de entrar na Home, o estado vazio, a área
  de adicionar áudio, o fundo de todos os avisos, e (na W2) as seções de pontos
  para reflexão e sugestões. Bege significa "conteúdo pedagógico", não alerta.
- **Folha em Branco** (`#FFFFFF`): a superfície principal. Fundo da página, dos
  formulários, das tabelas, dos relatórios e do diálogo modal.
- **Grafite** (`#5B6673`): metadado. Legenda de tabela, nome e tamanho do
  arquivo, data secundária, contagem. Nunca carrega informação que o professor
  precise para decidir.

### Estado

Cinco cores que existem só para estado e não fazem parte da identidade:
**Erro** (`#9B3B3B`), **Acerto** (`#3E6B4F`), **Atenção** (`#7A5512`) e
**Informação** (`#3F6A8A`) — usadas quase sempre como a borda-esquerda de 2px
de um aviso sobre bege, ou como cor do texto de erro de um campo.

### Named Rules

**A Regra dos 70% de Papel.** Branco e Papel de Caderno ocupam 65–75% da área de
qualquer tela; Tinta Permanente fica em 10–15%, Azul de Anotação em 8–12%,
Papel Milimetrado em 5–10%. Uma tela em que Tinta Permanente ou Azul de Anotação
passem de 20% da área — uma barra lateral sólida em navy cobrindo meia tela, por
exemplo — é revista antes de ir para implementação.

**A Regra dos Três Pares Proibidos.** Estes três nunca aparecem como texto de um
sobre fundo do outro, em nenhuma direção: Azul de Anotação sobre Papel de
Caderno, Papel Milimetrado sobre Folha em Branco, Azul de Anotação sobre Papel
Milimetrado. Eles podem coexistir como blocos vizinhos; nunca como texto sobre
fundo. Isto é contraste, não gosto — está em `forbidden_text_pairs`.

**A Regra das Superfícies do Navegador.** O que o produto não desenhou também
carrega a identidade. Seleção de texto é Papel Milimetrado com texto em Tinta
Permanente (`::selection`), o cursor de digitação é Azul de Anotação
(`caret-color`), e a barra de rolagem usa Azul de Anotação sobre Papel de
Caderno (`scrollbar-color`, `scrollbar-width: thin`). Deixar qualquer um deles
no padrão do sistema operacional é deixar um pedaço da tela fora da paleta.

**A Regra da Paleta Fechada.** Um estado nunca cria uma cor. Não existe "navy um
pouco mais escuro" para hover, nem `filter: brightness()`, nem `opacity` sobre
uma cor de marca para simular um tom intermediário. Uma mudança de estado troca
de token dentro das dez cores — é por isso que o hover do botão primário vai
para Azul de Anotação em vez de escurecer a Tinta Permanente.

## Typography

**Display Font:** Rokkitt (com Georgia, serif)
**Body Font:** Ubuntu (com system-ui, sans-serif)

Ambas empacotadas localmente em `fias-ed-shared/design-tokens/fonts/` como
`.woff2` com `font-display: swap`. Rokkitt é variável (eixo `wght` 100–900);
Ubuntu vem em três arquivos estáticos (400/500/700). **Nenhuma chamada a fonte
externa em runtime** — o produto funciona offline, e isso é requisito, não
otimização.

**Character:** uma serifa egípcia de traço reto ao lado de uma humanista de
terminais suaves. Rokkitt dá à frase pedagógica a autoridade de algo escrito à
mão com cuidado; Ubuntu dá ao dado a neutralidade de algo apenas registrado. A
tensão entre as duas é o produto inteiro: quem interpreta é a pessoa, quem
informa é o sistema.

### Hierarchy

- **Display** (Rokkitt 600, 2.75rem/44px, 1.1): a frase de abertura da Home —
  "Grave sua aula. Melhore sua prática docente." Uma por tela, no máximo.
- **Headline** (Rokkitt 600, 2.125rem/34px, 1.15): `h1`. Título de página e de
  relatório.
- **Title** (Rokkitt 600, 1.625rem/26px, 1.2): `h2`. Título de seção, título do
  diálogo modal, título do estado vazio.
- **Subtitle** (Ubuntu 700, 1.188rem/19px, 1.3): `h3`. Subtítulo funcional
  dentro de tabela, painel ou filtro. Em contexto editorial pode virar Rokkitt
  Medium — mas só se subir para 24px ou mais.
- **Body** (Ubuntu 400, 1rem/16px, 1.55): texto corrido. A entrelinha larga é
  deliberada: o produto é lido cansado.
- **Label** (Ubuntu 500, 0.875rem/14px, 1.4): rótulo de campo, rótulo de eixo.
- **Button** (Ubuntu 500, 0.9375rem/15px, 1.2): texto de botão. Sem caixa alta,
  sem `letter-spacing` — o produto não grita.
- **Caption** (Ubuntu 400, 0.8125rem/13px, 1.4): metadado em Grafite, texto de
  erro de campo, conteúdo do badge de etapa.

### Named Rules

**A Regra dos 24px.** Rokkitt nunca aparece abaixo de 24px. Nunca em tabela,
campo de formulário, número, rótulo, texto técnico longo ou qualquer elemento
que se repita em lista. Rokkitt cria personalidade; Ubuntu garante legibilidade.
Na dúvida, Ubuntu.

**A Regra da Fronteira.** A escolha entre as duas famílias nunca é estética: é
"isto é conteúdo pedagógico para ler ou é interface para operar?". Conteúdo
pedagógico e títulos → Rokkitt. Tudo que o professor clica, digita, filtra ou
compara → Ubuntu. Nenhum componente define fonte por conta própria; tudo sai de
`--font-interface` e `--font-editorial`.

## Layout

Coluna única centralizada, com largura máxima de 72rem e respiro de 32px em cima
e embaixo, 16px nas laterais (`.page`). A Home é a única exceção: a partir de
900px ela vira duas colunas em proporção 3fr/2fr, com a frase de abertura à
esquerda e o bloco de entrar à direita, ocupando a altura da janela.

A escala de espaço tem oito passos — 4, 8, 12, 16, 24, 32, 48, 64px — e o ritmo
vertical usa quase sempre 16px entre irmãos, 24px entre grupos e 32px entre
seções. Formulários longos viram duas colunas a partir de 900px
(`.form-grid`), com 24px de calha e nenhum espaço extra entre linhas: os campos
se alinham pela própria altura de 44px.

**Breakpoints:** 600px (sm), 900px (md), 1200px (lg). Na prática só o de 900px
muda layout hoje. Abaixo dele tudo é coluna única, e todo agrupamento horizontal
— barra de navegação, cabeçalho de página, item de lista, ações de diálogo —
usa `flex-wrap: wrap` em vez de esconder ou truncar. **Nada desaparece em tela
estreita.**

Listas são o padrão para coleções, não grades de cards: `.list` é uma lista sem
marcador, com uma linha de 1px em Papel Milimetrado entre itens, cada item com
16px de respiro vertical e fundo Papel de Caderno no hover. Abaixo de 600px o
item empilha (`flex-direction: column`) em vez de depender da quebra automática,
que fazia o status cair para a linha de baixo só em alguns itens, conforme o
comprimento do texto. Tabelas (`.table`) usam a mesma linha de 1px e alinhamento
à esquerda, sem zebra e sem borda externa.

Há duas variantes de tabela, e a diferença é só de alinhamento vertical.
**Tabela de texto** (`.table`, ex.: Contas) alinha ao meio: a linha de texto de
uma célula casa com o rótulo de um botão de 44px, que é centrado na própria
altura. **Tabela de formulário** (`.table .table--campos`, ex.: Escolas) alinha
ao topo — ao meio, cada coluna se centraria pela própria altura e os campos de
uma mesma linha não se alinhariam entre si. Nela, uma célula que só tem ação,
sem rótulo acima, desce exatamente uma linha de rótulo mais o intervalo do
campo (`calc(var(--type-label-size) * var(--type-label-line) + var(--space-1))`),
para o botão alinhar com os campos vizinhos e não com os rótulos deles.

### Named Rules

**A Regra do Alvo de 44px.** Todo elemento interativo — botão, campo, select,
textarea — tem no mínimo 44px de altura. Vale igual no desktop; não é uma
concessão ao toque, é o piso do produto.

**A Regra da Medida.** Texto corrido não passa de 68 caracteres por linha
(`p { max-width: 68ch }`). A página vai a 72rem, mas a linha de leitura não: num
monitor largo, um parágrafo de 1120px de largura é ilegível por mais correto que
esteja o contraste.

**A Regra do Ar Acima.** Um título pertence ao que vem depois dele, não ao que
veio antes: `h2` e `h3` em fluxo recebem mais espaço acima (32px e 24px) do que
abaixo (16px).

## Elevation & Depth

O sistema é **plano em repouso**. Não existe sombra ambiente, nem em card, nem
em lista, nem em barra de navegação, nem em campo de formulário. A profundidade
é feita de duas coisas: camada de cor (Folha em Branco → Papel de Caderno →
Papel Milimetrado, do mais ao menos "página") e linha de 1px em Papel
Milimetrado. Isso é coerente com a proibição de glow e gradiente do §7 e é o que
mantém o produto longe da aparência de dashboard.

Existe exatamente uma sombra no sistema, e ela pertence à única coisa que
realmente flutua sobre a página.

### Shadow Vocabulary

- **Elevação de modal** (`box-shadow: 0 8px 24px rgb(47 65 86 / 0.2)`): só no
  diálogo. A sombra é tingida de Tinta Permanente, não preta — ela pertence à
  paleta como todo o resto.
- **Fundo de modal** (`background: rgb(47 65 86 / 0.45)`): o escurecimento atrás
  do diálogo, também em Tinta Permanente.

### Named Rules

**A Regra do Plano em Repouso.** Uma superfície só ganha sombra se puder ser
fechada. Hoje isso significa: o diálogo, e nada mais. Se um elemento novo pedir
sombra, a pergunta é se ele deveria ser um diálogo — não qual sombra usar.

## Shapes

A linguagem de forma é quase ausente, de propósito. Dois raios, duas espessuras
de borda, nenhum recorte, nenhuma silhueta decorativa.

- **4px (`--radius-sm`)**: tudo que é controle — botão, campo, select,
  textarea, badge, aviso. Suaviza o canto sem chamar atenção.
- **6px (`--radius-md`)**: tudo que é recipiente — diálogo, estado vazio, bloco
  de entrar da Home, área de adicionar áudio.
- **1px (`--border-hairline`)**: a divisória universal, em Papel Milimetrado
  entre itens e em Grafite no contorno de campo.
- **2px (`--border-strong`)**: usada em um lugar só — a borda esquerda do aviso,
  que carrega a cor de estado (erro, acerto, atenção, informação). É a barra na
  margem do caderno.

### Named Rules

**A Regra dos Dois Raios.** Existem 4px e 6px. Não existe 8px, 12px, `9999px`
nem `border-radius: 50%`. Um pill, um avatar redondo ou um card de canto largo
está fora do sistema.

## Components

Caráter geral: **discreto e acolhedor**. O componente não disputa atenção com o
conteúdo — mas onde o professor lê e reflete, a superfície fica bege e o
espaçamento abre.

> **Estados de ponteiro:** `:hover` e `:active` existem e respeitam a Regra da
> Paleta Fechada — nenhum deles inventa uma cor.

### Buttons

Altura mínima de 44px, raio de 4px, 8px/24px de respiro interno, Ubuntu Medium
15px sem caixa alta, `inline-flex` com 8px de intervalo para acomodar um ícone
à esquerda. Todo botão tem borda de 1px transparente para que a variante
secundária não mude de tamanho ao ganhar contorno.

- **Primário:** fundo Tinta Permanente, texto Folha em Branco. Uma ação
  primária por tela.
  - *Hover:* fundo Azul de Anotação, texto Folha em Branco (4.50:1).
  - *Active:* `transform: translateY(1px)` — geometria, não cor.
- **Secundário:** fundo Folha em Branco, texto e borda de 1px em Azul de
  Anotação. É o botão de ação paralela: "Selecionar áudio", "Agir como",
  "Substituir áudio", "Salvar disciplina".
  - *Hover:* fundo Papel Milimetrado, texto **Tinta Permanente** — o texto
    troca junto, porque Azul de Anotação sobre Papel Milimetrado é par
    proibido.
- **Terciário:** sem fundo, texto Azul de Anotação, respiro lateral de 8px. É a
  ação de baixo peso: "Cancelar", "Excluir", "Redefinir senha", "Sair".
  - *Hover:* sublinhado com `text-underline-offset: 4px`, sem troca de cor.
  - **Atenção:** por não ter fundo próprio, o terciário herda a superfície.
    Sobre Papel de Caderno o texto passa a Tinta Permanente — ver Do's and
    Don'ts.
- **Desabilitado:** fundo Papel de Caderno, texto Grafite (5.13:1), borda de
  1px em Papel Milimetrado, `cursor: not-allowed`. **Sem `opacity`:** opacidade
  sobre Tinta Permanente produzia um cinza-azulado que não é nenhuma das dez
  cores, violando a Regra da Paleta Fechada.
- **Na barra de navegação:** o terciário é sobrescrito para Folha em Branco
  (`.topbar .btn--tertiary`), porque ali a superfície é Tinta Permanente.

### Inputs / Fields

Campo, select e textarea compartilham a mesma classe: 44px de altura mínima,
8px/12px de respiro, borda de 1px em Grafite, raio de 4px, fundo Folha em
Branco, `font: inherit`. Rótulo sempre visível acima do campo (Ubuntu Medium
14px), a 4px de distância, com `htmlFor` ligado a um `useId` — nunca
placeholder como rótulo.

- **Foco:** contorno de 3px em Azul de Anotação com 2px de deslocamento, vindo
  da regra global `:focus-visible`. Nunca removido.
- **Erro:** borda em Erro, `aria-invalid="true"`, e um parágrafo de 13px em Erro
  logo abaixo, ligado por `aria-describedby`. A cor nunca é o único sinal — a
  mensagem em texto sempre acompanha.
- **Espaçamento:** 16px abaixo de cada campo.

### Banner (avisos)

Fundo Papel de Caderno, raio de 4px, 12px/16px de respiro, e uma borda esquerda
de 2px que carrega a cor de estado: Informação, Erro, Atenção ou Acerto. O texto
permanece em Tinta Permanente em todas as variantes — a cor de estado vive na
barra, não na letra. `role="alert"` quando é erro, `role="status"` nos demais.

### Cards / Containers

O sistema não tem card genérico. Tem três recipientes nomeados, todos com raio
de 6px e fundo Papel de Caderno, sem sombra e sem borda:

- **Estado vazio** (`.empty`): 48px/24px de respiro, centralizado, título em
  Rokkitt, um parágrafo e uma ação opcional.
- **Bloco de entrar da Home** (`.home__login`): 32px de respiro.
- **Área de áudio / grupo de formulário** (`.audio-area`): 24px de respiro, 24px
  de margem vertical. É também onde vivem os formulários embutidos de nova turma
  e nova disciplina.

### Dialog

Fundo Folha em Branco, raio de 6px, 32px de respiro, largura máxima de 32rem,
centralizado por `display: grid; place-items: center` sobre um fundo em Tinta
Permanente a 45%. Título em `h2` (Rokkitt 26px) ligado por `aria-labelledby`,
`role="dialog"`, `aria-modal="true"`, foco movido para o diálogo na montagem e
Esc fechando. Ações alinhadas à direita, com 12px entre elas e `flex-wrap`.

### Navigation

Barra horizontal em Tinta Permanente com texto Folha em Branco, 12px/16px de
respiro, 24px entre grupos e `flex-wrap` — em 360px ela quebra em linhas em vez
de colapsar num menu sanduíche. A marca "FIAS-ED" é Rokkitt 600 em 1.5rem, sem
sublinhado. Os links de navegação são Folha em Branco sem sublinhado; o item
atual recebe `aria-current="page"` e sublinhado com 6px de deslocamento — **o
estado ativo é tipográfico, não uma pílula de fundo**.

- *Hover:* sublinhado com o mesmo deslocamento de 6px, para que o item atual e o
  item sob o ponteiro se distingam por permanência, não por cor.
- **Abaixo de 600px** a navegação ocupa a própria linha (`order: 3`,
  `flex-basis: 100%`), e a marca, o nome de quem entrou e "Sair" ficam na linha
  de cima. Antes, o nome caía no meio dos links e parecia mais um item de menu.

### StatusBadge (componente de assinatura)

O elemento mais característico do sistema e o que carrega a promessa de produto.
A aula tem 18 estados técnicos, de `DRAFT` a `REPORT_READY`; o badge nunca
mostra nenhum deles. Mostra a frase humana correspondente — "Áudio conferido",
"Confirme qual voz é a sua", "Aguardando a percepção dos estudantes", "Precisa
de atenção" — e escolhe um de três tons:

- **Em andamento:** fundo Papel Milimetrado, texto Tinta Permanente.
- **Precisa de atenção:** fundo Papel de Caderno, texto Tinta Permanente.
- **Concluído:** sem fundo e sem respiro lateral — texto puro.

Três tons, não dezoito cores. E nenhum deles é vermelho de alarme: o pior estado
do sistema se chama "Precisa de atenção" e usa Atenção, não Erro.

**Nenhum badge tem contorno.** Com borda de 1px e o mesmo raio dos botões, o
badge era lido como algo clicável ao lado de botões de verdade — e na lista de
aulas ele fica justamente alinhado à direita, onde o olho espera uma ação. A
distinção entre os três tons é por superfície, e "concluído" não recebe
tratamento nenhum: quando não há nada a fazer, o silêncio é a informação.

### Named Rules

**A Regra do Estado Legível.** Nenhum estado é comunicado só por cor. Toda
variação de tom carrega texto, borda ou posição junto. Um badge sem a frase
humana é um badge quebrado.

## Do's and Don'ts

### Do:

- **Do** usar exclusivamente as variáveis de `tokens.css`. Uma cor, um tamanho de
  fonte ou um espaçamento escrito literalmente no CSS é um erro, mesmo que o
  valor bata com o token.
- **Do** manter branco e Papel de Caderno em 65–75% da área de qualquer tela.
- **Do** dar a Papel de Caderno o papel de "aqui se lê e se reflete": estado
  vazio, aviso, área de áudio, e as seções de reflexão e sugestões da W2.
- **Do** usar Rokkitt só em título de 24px ou mais, e Ubuntu em todo o resto.
- **Do** escrever o estado da aula como frase de pessoa. `STATUS_TEXT` em
  `frontend/src/app/status.ts` é a fonte; um estado novo entra lá antes de
  aparecer na tela.
- **Do** deixar tudo quebrar em linha (`flex-wrap`) em telas estreitas, em vez de
  esconder, truncar ou colapsar num menu.
- **Do** manter o contorno de foco de 3px em Azul de Anotação em todo elemento
  interativo.
- **Do** acompanhar toda cor de estado de um texto que diga a mesma coisa.
- **Do** tematizar as superfícies do navegador (seleção, cursor, barra de
  rolagem) a partir da paleta.

### Don't:

- **Don't** pôr texto em Azul de Anotação sobre Papel de Caderno ou sobre Papel
  Milimetrado, nem texto em Papel Milimetrado sobre branco. **Cuidado
  específico:** o botão terciário e os links são Azul de Anotação e não têm
  fundo próprio — sobre qualquer superfície bege eles caem direto no par
  proibido. Ou o recipiente muda para branco, ou o texto muda para Tinta
  Permanente.
- **Don't** criar cor para estado. Sem navy escurecido, sem `filter:
  brightness()`, sem `opacity` sobre cor de marca. Estado troca de token.
- **Don't** usar sombra fora do diálogo. Profundidade é camada de cor e linha de
  1px.
- **Don't** introduzir raio fora de 4px e 6px — nada de pílula, círculo ou canto
  largo.
- **Don't** usar gradiente, glow, glassmorphism, blob, ícone de estrela, cérebro,
  robô ou sparkle, nem ilustração genérica ou gráfico decorativo (§7).
- **Don't** escrever "avaliação", "avaliar", "nota", "desempenho", "ranking" ou
  "iniciar avaliação" em qualquer texto de interface. O vocabulário permitido
  está em `PRODUCT.md`; essa restrição é de produto e a tipografia não a
  suaviza.
- **Don't** transformar a coleção de aulas numa grade de cards. Lista com
  divisória de 1px.
- **Don't** usar placeholder no lugar de rótulo, nem remover o contorno de foco.
- **Don't** usar `opacity` para exprimir estado desabilitado: opacidade sobre
  uma cor de marca produz um tom que não está na paleta.
- **Don't** dar contorno completo a um badge. Com borda de 1px e o raio dos
  botões ele vira um falso botão.
- **Don't** definir fonte dentro de um componente. Só `--font-interface` e
  `--font-editorial`.
- **Don't** usar atributo `style` inline. Tudo passa por classe e token.
