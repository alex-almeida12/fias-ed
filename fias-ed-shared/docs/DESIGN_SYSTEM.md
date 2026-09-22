# Design System (`design-tokens/tokens.json`)

Este documento descreve, em linguagem de produto, o sistema de design do
FIAS-ED — derivado de `design-tokens/tokens.json` (`tokens_version:
"1.0.0"`) e materializado em `design-tokens/build/tokens.css`. Todo valor
numérico ou hexadecimal abaixo é idêntico ao do token correspondente; se
um dia divergirem, `tokens.json` é a fonte de verdade e este documento
deve ser corrigido, não o contrário.

Contexto de produto: o FIAS-ED é a ferramenta em que um professor grava a
própria aula para entender padrões de interação (FIAS) e a percepção dos
estudantes (QTI), refletir e receber sugestões — "Grave sua aula. Melhore
sua prática docente." A interface deve parecer acadêmica, sóbria,
institucional e baseada em dado real, nunca um produto de IA genérico,
um chatbot ou um painel de avaliação/ranking. As referências que
sustentam essas escolhas estão em `UI_REFERENCES.md`.

## Cores

### Paleta

| Token | Hex | Papel de uso |
|---|---|---|
| Navy | `#2F4156` | Títulos, texto principal, navegação, botões primários, cabeçalhos, ícones importantes |
| Teal | `#567C8D` | Ações secundárias, seleção, destaques, links, séries de gráfico |
| Sky Blue | `#C8D9E6` | Superfícies informativas, seleção, séries de gráfico, fundos suaves |
| Beige | `#F5EFEB` | Fundo secundário, áreas pedagógicas, seção de sugestões, pontos de reflexão |
| White | `#FFFFFF` | Fundo principal, formulários, relatórios, conteúdo |

Cores semânticas (não fazem parte da paleta de marca; só para estado):

| Token | Hex | Uso |
|---|---|---|
| Error | `#9B3B3B` | Erro de processamento/formulário |
| Success | `#3E6B4F` | Confirmação de conclusão de etapa |
| Warning | `#7A5512` | Alerta não bloqueante |
| Info | `#3F6A8A` | Mensagem informativa neutra |
| Muted | `#5B6673` | Texto secundário, metadado |

Nenhuma outra cor deve aparecer na interface além destas dez. Não há
gradiente decorativo, `glow` (brilho/sombra luminosa) nem cor aleatória
fora desta lista.

### Papéis (`color.role`)

`text: navy`, `text-muted: muted`, `link: teal`, `surface: white`,
`surface-alt: beige`, `surface-info: sky`, `border: sky`,
`action-primary: navy`, `action-secondary: teal`. Grupos FIAS
(`color.fias_groups`): `indirect: teal`, `direct: navy`, `student: sky`,
`silence: beige` — reaproveitam a paleta de marca, sem criar uma paleta
paralela só para gráficos.

### Proporção de uso na tela

Em qualquer tela do produto, a área ocupada por cor deve seguir
aproximadamente:

- **Branco + Beige**: 65–75% da área (fundo, formulários, áreas de
  leitura).
- **Navy**: 10–15% (texto, navegação, ação primária).
- **Teal**: 8–12% (ação secundária, links, uma série de gráfico).
- **Sky Blue**: 5–10% (superfície informativa, seleção, segunda série de
  gráfico).

O produto é predominantemente claro. Uma tela em que Navy ou Teal
ultrapassem 20% da área (ex.: barra lateral cheia em navy sólido cobrindo
metade da tela) deve ser revista antes de seguir para implementação.

### Tabela de contraste e pares proibidos

`text_pairs` (permitidos, com contraste adequado para texto): `navy/white`,
`navy/beige`, `navy/sky`, `teal/white`, `muted/white`, `muted/beige`,
`white/navy`, `white/teal`, `error/white`, `success/white`, `warning/white`,
`info/white`, `error/beige`, `success/beige`, `warning/beige`, `info/beige`.

`forbidden_text_pairs` (contraste insuficiente para texto — nunca usar
texto de uma cor sobre fundo da outra): `teal/beige`, `sky/white`,
`teal/sky`. Estes três pares podem coexistir na mesma tela como blocos
adjacentes (ex.: um card sky ao lado de um card beige), mas nunca um como
texto sobre o outro.

## Tipografia

Duas famílias, ambas empacotadas localmente em `design-tokens/fonts/`
(arquivos `.woff2`/`.ttf`, funcionam offline — sem chamada a fonte
externa): **Ubuntu** (`--font-interface`) para tudo que é interface, e
**Rokkitt** (`--font-editorial`) para conteúdo editorial. No Android, o
equivalente é `FIASTypography` — nunca a fonte padrão do sistema
(Roboto).

- **Ubuntu** (pesos 400, 500, 700 — evitar excesso de negrito): menus,
  barra lateral, botões, campos de formulário, rótulos, tabelas, filtros,
  números e indicadores, navegação, mensagens do sistema, texto corrido
  curto.
- **Rokkitt** (pesos 500, 600, 700): títulos principais, grandes
  destaques, cabeçalhos de relatório, frases pedagógicas, seções de
  reflexão. Rokkitt só é usada em texto ≥ 24 px — **nunca** em tabelas
  longas, campos de formulário, texto técnico longo, números pequenos ou
  rótulos muito pequenos.

### Escala (`type_scale`)

| Nível | Fonte | Tamanho | Peso | Linha | Uso |
|---|---|---|---|---|---|
| Display | editorial (Rokkitt) | 44px / 2.75rem | 600 | 1.1 | Frase de abertura de tela, ex. mensagem de boas-vindas |
| H1 | editorial (Rokkitt) | 34px / 2.125rem | 600 | 1.15 | Título de página/relatório |
| H2 | editorial (Rokkitt) | 26px / 1.625rem | 600 | 1.2 | Título de seção |
| H3 | interface (Ubuntu Bold) | 19px / 1.188rem | 700 | 1.3 | Subtítulo de bloco; em contexto editorial pode usar Rokkitt Medium, nunca abaixo de 24px |
| Body | interface (Ubuntu) | 16px / 1rem | 400 | 1.55 | Texto corrido |
| Label | interface (Ubuntu) | 14px / 0.875rem | 500 | 1.4 | Rótulo de campo, rótulo de gráfico |
| Button | interface (Ubuntu) | 15px / 0.9375rem | 500 | 1.2 | Texto de botão |
| Caption | interface (Ubuntu) | 13px / 0.8125rem | 400 | 1.4 | Legenda, metadado, observação de rodapé de tabela |

Note que "H3" pode usar Ubuntu Bold (subtítulo funcional, ex. dentro de
uma tabela ou painel de filtro) ou Rokkitt Medium (subtítulo editorial,
ex. dentro de uma seção de reflexão) dependendo do contexto — a decisão é
sempre "isto é conteúdo pedagógico de leitura ou é interface operacional?".
Na dúvida, usar Ubuntu.

## Spacing

Escala em pixels (`space_px`), múltiplos de 4: `1: 4px`, `2: 8px`,
`3: 12px`, `4: 16px`, `5: 24px`, `6: 32px`, `7: 48px`, `8: 64px`. Nenhum
espaçamento fora desta escala deve ser usado em CSS novo.

## Grid

12 colunas em telas ≥ 900px (`breakpoints_px.md`); 4 colunas abaixo de
600px (`breakpoints_px.sm`). No celular, gutter lateral fixo de 16px
(`space_px.4`) — o conteúdo nunca toca a borda da tela.

## Radius

`radius_px`: `sm: 4px` (padrão para botão, input, badge), `md: 6px`
(padrão para card, dialog). Nunca radius maior que 6px — evita a
aparência de "app" excessivamente arredondado.

## Borders

`border_px`: `hairline: 1px` (divisórias, borda padrão de input/tabela),
`strong: 2px` (borda de foco, borda de estado de erro). Cor de borda
padrão: `--color-border` (sky).

## Shadows

Sombra é usada apenas em dois casos: **foco de teclado** (contorno
visível ao navegar por Tab) e **diálogos modais** (para destacar a
camada sobre o conteúdo). Nenhum outro elemento — card, botão, header —
recebe sombra decorativa. Não há `glow` nem sombra colorida.

## Botões

- **Primário**: fundo navy, texto branco. Uma ação primária por tela
  (ex.: "Analisar minha aula").
- **Secundário**: fundo teal com texto branco, ou contorno teal com texto
  teal sobre fundo branco/bege.
- **Terciário**: apenas texto (navy ou teal), sem fundo nem contorno —
  para ações de baixa ênfase (ex.: "Cancelar").

Texto de botão sempre em Ubuntu Medium (token `button`), nunca Rokkitt.

## Inputs

Fundo branco, borda `hairline` sky, radius `sm`. Rótulo (`label`) acima
do campo, sempre em Ubuntu. Foco: borda `strong` navy + sombra de foco.
Erro: borda `strong` na cor `error`, com mensagem abaixo do campo em
Ubuntu Caption cor `error`. Nunca Rokkitt em campo de formulário.

## Tabelas

Cabeçalho em Ubuntu Medium/Bold, corpo em Ubuntu Regular. Linhas com
divisória `hairline` sky; sem cor de fundo por linha para indicar
julgamento — cor de fundo em linha é reservada a seleção (sky) e a
estado de processamento (ver Badges). Números alinhados à direita,
sempre Ubuntu (nunca Rokkitt), inclusive em tabelas curtas.

## Cards

Card é usado somente quando agrupa um conjunto de dados relacionados
(uma aula, um indicador, uma sugestão com seu contexto) — nunca como
moldura decorativa em torno de um único ícone ou frase solta. Fundo
branco ou bege, radius `md`, borda `hairline` sky, sem sombra fora do
padrão de foco/dialog.

## Dialogs

Fundo branco, radius `md`, sombra de camada (único uso de sombra além do
foco). Título em H2 (Rokkitt) quando o diálogo é de confirmação
pedagógica de conteúdo longo, ou H3/Ubuntu Bold quando é confirmação
operacional curta (ex.: "Excluir esta aula?").

## Tabs

Texto Ubuntu Medium; aba ativa marcada por sublinhado navy de 2px
(`border-strong`) e cor de texto navy; abas inativas em `text-muted`.
Sem fundo colorido na aba ativa.

## Badges

Badges no FIAS-ED indicam **apenas status de processamento** — nunca
resultado, avaliação ou rótulo de julgamento sobre o professor. Exemplos
válidos: "Processando áudio", "Transcrição concluída", "Aguardando
revisão de falantes". Cores: `info` (em andamento), `success` (etapa
concluída), `warning` (atenção não bloqueante), `error` (falha de
processamento). Nunca um badge do tipo `bom/regular/ruim` ou similar.

## Gráficos

Cor por grupo FIAS (`color.fias_groups`): indireta = teal, direta = navy,
aluno = sky, silêncio = beige — mesma paleta de marca, sem paleta
paralela. Rótulo direto (nome + valor junto da barra/fatia), evitando
legenda separada sempre que couber no espaço. Sem gráfico 3D, sem
efeito de profundidade, sem animação decorativa de entrada. Gráfico
sempre acompanhado de uma frase descritiva do que ele mostra, antes da
visualização (ver referência CDC em `UI_REFERENCES.md`).

## Loading

Mensagens humanas e específicas da etapa em curso, nunca um spinner
genérico sem texto ou "Carregando...":

"Preparando sua aula...", "Transformando áudio em texto...",
"Identificando os momentos de fala...", "Organizando as interações...",
"Analisando padrões da aula...", "Integrando as respostas dos
estudantes...", "Preparando a interpretação pedagógica...", "Gerando
sugestões...", "Preparando seu relatório...".

## Empty states

Um empty state bem escrito é uma frase completa e humana explicando o que ainda não existe e, quando
fizer sentido, a próxima ação possível — nunca apenas um ícone central
genérico. Exemplos: "Esta aula ainda não tem áudio enviado. Envie o
áudio da aula para começar a análise.", "Nenhuma sugestão foi gerada
ainda para esta aula." Sem ilustração decorativa; no máximo um ícone
pequeno e discreto, nunca robô, estrela, cérebro ou faísca.

## Error states

Mensagem objetiva do que falhou e, quando souber, o que fazer a seguir
— nunca linguagem alarmista nem termo técnico cru sem explicação (ex.:
não expor um código de exceção sozinho). Cor `error` no texto/ícone da
mensagem, nunca em blocos grandes de fundo vermelho.

## Breakpoints

`breakpoints_px`: `sm: 600px`, `md: 900px`, `lg: 1200px`. Abaixo de 600px:
1 coluna, grid de 4 colunas internas, gutter lateral de 16px. De 600px a
899px: transição, ainda densidade reduzida. A partir de 900px: grid de 12
colunas completo.

## Vocabulário

### Usar

"Adicionar aula", "Enviar áudio da aula", "Analisar minha aula",
"Entender minha aula", "Ver padrões de interação", "Conhecer a percepção
dos estudantes", "Pontos para reflexão", "Sugestões para próximas
aulas", "Melhorar minha prática".

Linguagem de interpretação/sugestão (dentro do conteúdo gerado, não só
nos rótulos de tela): "Considere...", "Você pode experimentar...", "Uma
possibilidade é...", "Este padrão pode indicar...".

### Evitar

Termos de avaliação/ranking/punição, nunca usados na interface:
`Iniciar avaliação`, `Avaliar professor`, `Professor inadequado`,
`Desempenho ruim`, `Nota do professor`. Também evitar, por soarem a
produto de IA genérico: "AI powered", "Insights inteligentes",
"Assistente inteligente", "Transforme sua jornada", "Potencialize sua
experiência", "Desbloqueie seu potencial".

Evitar também, fora de conteúdo científico do próprio motor (onde o
termo é técnico e não é rótulo de tela): `conforme` / `não conforme`,
`reprovado/a`, `avaliação docente` — ver lista completa de termos
proibidos em `fias_ed_engine.language.FORBIDDEN_PATTERNS`.

## Checklist visual final

Antes de aprovar qualquer tela nova ou revisada, perguntar: **"Esta
interface parece um produto criado especificamente para professores ou
parece um template gerado por IA?"** Conferir, nesta ordem:

1. Hierarquia — há um único elemento de maior destaque por tela?
2. Espaçamento — segue a escala `space_px` (4 a 64px), sem valor solto?
3. Tipografia — Rokkitt só em conteúdo editorial ≥ 24px; Ubuntu em todo
   o resto?
4. Contraste — todo par texto/fundo está na lista `text_pairs`, nenhum
   nos `forbidden_text_pairs`?
5. Consistência — os mesmos componentes (botão, badge, card) têm a mesma
   aparência em todas as telas?
6. Uso da paleta — proporção aproximada de 65–75% branco/bege, 10–15%
   navy, 8–12% teal, 5–10% sky?
7. Ubuntu correta — pesos 400/500/700, sem negrito em excesso?
8. Rokkitt editorial — usada só onde há leitura pedagógica de fato, nunca
   em número, tabela ou campo?
9. Responsividade — a tela funciona nos três breakpoints (600/900/1200px)
   sem quebrar o grid?
10. Densidade — a tela não está nem vazia demais nem sobrecarregada?
11. Legibilidade — texto longo em Ubuntu, com altura de linha (`line`)
    do token correspondente?
12. Sem gradiente decorativo, sem `glow`, sem blob, sem excesso de card,
    sem radius exagerado?
13. Sem ícone de estrela, cérebro, robô ou faísca, sem ilustração
    genérica de estoque?

## Revisões com Impeccable

O plugin Impeccable é usado para revisão visual automatizada, mas atua
sobre **telas reais** — isto é, sobre a implementação de interface do
subprojeto 2 (fora do escopo do `fias-ed-shared`), nunca sobre este
documento de tokens isoladamente. O `fias-ed-shared` define os valores
(`tokens.json`) e as regras (este documento); a instalação do Impeccable
(`npx impeccable install --global --providers=claude -y`) e a revisão
tela a tela acontecem quando o subprojeto 2 implementar componentes e
páginas a partir destes tokens.
