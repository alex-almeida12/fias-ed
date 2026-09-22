# Referências de interface

Levantamento de referências públicas de UI para orientar o design do
FIAS-ED (telas reais ficam a cargo do subprojeto 2; este documento é
insumo para `DESIGN_SYSTEM.md`). Prioriza produtos que um professor ou
gestor escolar reconheceria como sóbrios e confiáveis, e não como um
produto de IA genérico.

- **Data da pesquisa**: 2026-09-21.
- **Fontes não consultadas**: Mobbin, Refero e Figma Community exigem
  login para navegação além da vitrine inicial; não foram acessadas para
  não violar a regra de "apenas páginas públicas, sem login". Nenhuma
  referência abaixo depende delas.
- **Método**: cada URL abaixo foi efetivamente acessada (via busca web) em
  2026-09-21. Páginas que retornaram erro (403/404) ou que não carregaram
  conteúdo analisável (ex.: uma tentativa em `play.grafana.org`, que
  devolveu apenas uma tela de erro de carregamento, e uma tentativa em
  `khanacademy.org/teacher`, sem conteúdo suficiente para análise) foram
  descartadas e substituídas por outra referência, em vez de registradas
  aqui — nenhuma URL não acessada aparece na lista.

## Síntese de princípios (5–8)

1. **Hierarquia editorial em relatórios de dados**: sistemas institucionais
   (GOV.UK, NHS, CDC) usam um único peso de destaque por página — título
   grande, o resto em texto corrido — em vez de múltiplos elementos
   competindo por atenção. O FIAS-ED deve reservar o peso editorial
   (Rokkitt) para o título da aula/relatório e manter o restante em
   tipografia de interface.
2. **Densidade de tabela sóbria**: nenhuma das referências institucionais
   usa cor de fundo em linha de tabela para indicar julgamento binário; usam texto
   neutro e, no máximo, um rótulo textual. Reforça a decisão de não usar
   semáforos de resultado no FIAS-ED.
3. **Estados vazios e mensagens humanas**: páginas de dados em saúde (WHO,
   CDC) descrevem o que ainda não existe em frase completa, sem ícone
   decorativo central nem tom de erro — modelo para os *empty states* do
   FIAS-ED (ex.: "Esta aula ainda não tem áudio enviado.").
4. **Ferramentas de observação de aula usam linha do tempo, não `nota`**:
   GoReact, TeachFX e Edthena estruturam feedback em torno de
   marcações no tempo do vídeo/áudio e de padrões de fala, nunca de uma
   pontuação única — confirma a escolha do FIAS-ED de não emitir `nota`
   nem rótulo de `desempenho`.
5. **Paleta contida em sistemas institucionais**: GOV.UK e NHS usam uma cor
   de marca e cinzas/neutros para o restante; cor é reservada a link,
   estado (erro/aviso) e ação primária — mesma lógica da paleta do
   FIAS-ED (Navy/Teal/Sky/Beige/Branco com semânticas separadas).
6. **Cards só quando agrupam dados, não como decoração**: nas páginas que
   listam muitos itens (WHO, CDC, PubMed), o card é usado para agrupar um
   conjunto de dados (um indicador, uma dashboard, um artigo) — nunca como
   moldura decorativa em torno de texto solto.
7. **Marketing "orientado a IA" tende à cor viva e ao vocabulário de
   "coach/assistente"**: a home da Edthena usa a frase "AI coaching for
   every K-12 teacher" com paleta mais colorida (verde, rosa, roxo) — é o
   contraponto exato do que o FIAS-ED deve evitar (ver "o que não copiar"
   abaixo).
8. **Filtro e busca densos, não decorativos**: PubMed concentra a busca em
   uma caixa central simples, com filtros textuais ao lado — sem
   ilustração ou gráfico de enfeite ao redor da ação principal.

## Referências

### 1. GOV.UK Design System — página de componentes
- **URL**: https://design-system.service.gov.uk/components/
- **Tela analisada**: índice de componentes (listagem alfabética com
  navegação lateral e busca).
- **Elemento relevante**: hierarquia clara com H1 único, links de
  componente em lista de texto (sem cards decorativos), breadcrumb
  simples (Home > Components).
- **Como inspira o FIAS-ED**: modelo de navegação lateral sóbria para o
  menu do professor (Minhas aulas, Relatórios, Perfil), e de usar lista de
  texto em vez de card quando o conteúdo já é uma lista homogênea.
- **O que não copiar**: o azul de marca do governo britânico e o tom
  fortemente institucional-burocrático do texto de rodapé (licenciamento
  MIT, avisos legais extensos) não cabem no tom pedagógico do FIAS-ED.

### 2. U.S. Web Design System (USWDS) — página de componentes
- **URL**: https://designsystem.digital.gov/components/overview/
- **Tela analisada**: catálogo de componentes com grade filtrável e busca
  por palavra-chave.
- **Elemento relevante**: cabeçalho com aviso institucional, navegação em
  múltiplos níveis, cartões de componente com descrição de 2–3 linhas.
- **Como inspira o FIAS-ED**: grade de cards com descrição curta é um bom
  modelo para a tela "Minhas aulas" (uma aula por card, com data, duração e
  status de processamento).
- **O que não copiar**: fundo de navegação azul-marinho escuro contínuo —
  o FIAS-ED deve manter navegação clara (branco/bege), reservando o navy
  para texto e ações, não para grandes blocos de fundo.

### 3. NHS Digital Service Manual — página de componentes
- **URL**: https://service-manual.nhs.uk/design-system/components
- **Tela analisada**: listagem de componentes organizada em três
  categorias (elementos de formulário, apresentação de conteúdo,
  navegação).
- **Elemento relevante**: agrupamento por categoria funcional (formulário
  / conteúdo / navegação) em vez de ordem alfabética pura, com breadcrumb
  e tipografia acessível de alto contraste.
- **Como inspira o FIAS-ED**: agrupar os componentes do próprio
  `DESIGN_SYSTEM.md` por função (o que este documento já faz) e priorizar
  contraste alto em textos de relatório, já que o sistema é usado por
  professores com pouco tempo entre aulas.
- **O que não copiar**: a extensão do texto explicativo de cada componente
  (parágrafos longos de diretriz de acessibilidade) é adequada a um manual
  de serviço público, mas pesada demais para o dia a dia de uso do
  FIAS-ED — a interface do professor deve preferir rótulos curtos.

### 4. GoReact — página de produto
- **URL**: https://get.goreact.com/
- **Tela analisada**: página inicial com seção de destaque, navegação por
  público (ensino superior, K12, formação profissional) e depoimentos.
- **Elemento relevante**: o produto descreve feedback em vídeo com
  marcação no tempo exato da gravação ("pausar o vídeo no momento exato")
  e comentários em texto ou vídeo vinculados a esse instante.
- **Como inspira o FIAS-ED**: reforça o padrão de vincular
  interpretações/sugestões a um trecho específico da aula gravada (linha
  do tempo), em vez de um resumo solto sem referência temporal.
- **O que não copiar**: o vocabulário comercial da home ("Building Skills
  for Brighter Futures", múltiplos CTAs de teste grátis) é tom de venda de
  SaaS — o FIAS-ED não deve replicar linguagem de conversão comercial nas
  telas de uso.

### 5. TeachFX — página inicial
- **URL**: https://www.teachfx.com/
- **Tela analisada**: página inicial com demonstração do fluxo "como o
  TeachFX funciona" e exemplo de gravação de aula com métricas de fala.
- **Elemento relevante**: visualização de proporção de fala por grupo
  (estudante, grupo, professor, silêncio) em minutos, associada a uma
  gravação identificada por turma e período — estrutura de dado muito
  próxima da que o FIAS-ED produz (grupos FIAS: direta/indireta/aluno/
  silêncio).
- **Como inspira o FIAS-ED**: confirma o formato de gráfico por grupo com
  rótulo direto (nome + valor, sem legenda separada) para a tela "Ver
  padrões de interação".
- **O que não copiar**: os números de resultado exibidos como conquista
  percentual ("+31% de aumento na fala do estudante") soam a métrica de
  produto de crescimento; o FIAS-ED deve apresentar a mesma informação
  como observação descritiva, não como resultado a ser comemorado ou
  comparado entre professores.

### 6. Edthena — página inicial
- **URL**: https://edthena.com/
- **Tela analisada**: página inicial com diálogo simulado entre professor,
  "AI coach", colegas e direção, e seção de estatísticas de uso.
  Explicitamente rotulada pelo próprio site como página de marketing de IA.
- **Elemento relevante**: estrutura de oferta por público (redes, escolas,
  formação inicial) e uso de citação de imprensa como prova social.
- **Como inspira o FIAS-ED**: serve principalmente como contraexemplo (ver
  abaixo) — mas a organização por público (rede/escola/professor) pode
  orientar como documentar, no próprio `DESIGN_SYSTEM.md`, diferentes
  contextos de uso da interface.
- **O que não copiar**: vocabulário de "AI coaching" e paleta mais viva
  (verde, rosa, roxo) na home é exatamente o padrão de "produto de IA"
  que o FIAS-ED precisa evitar; nenhum termo desse tipo (ex.: "assistente
  inteligente") deve aparecer na interface do FIAS-ED.

### 7. PubMed
- **URL**: https://pubmed.ncbi.nlm.nih.gov/
- **Tela analisada**: página inicial de busca, com caixa de pesquisa
  central e seções "Trending Articles" e "PubMed Updates" abaixo.
- **Elemento relevante**: densidade equilibrada — uma ação principal (a
  busca) centralizada, sem ilustração decorativa ao redor, com conteúdo
  secundário organizado em listas de texto simples.
- **Como inspira o FIAS-ED**: modelo para a tela inicial do professor —
  uma ação primária clara ("Adicionar aula") sem elementos decorativos
  competindo com ela, e uma lista simples de aulas recentes abaixo.
- **O que não copiar**: a quantidade de siglas e metadados técnicos
  (PMID, filtros avançados de indexação bibliográfica) é apropriada a um
  público de pesquisadores, não ao professor da educação básica que é o
  usuário do FIAS-ED.

### 8. WHO Global Health Observatory
- **URL**: https://www.who.int/data/gho
- **Tela analisada**: página de entrada de dados de saúde, com cards
  temáticos (ex.: poluição do ar, tuberculose) e cards de painel/dataset
  com imagem de prévia.
- **Elemento relevante**: uso de card exclusivamente para agrupar um
  conjunto de dados (um tema, um painel), nunca como moldura decorativa
  em torno de texto isolado; ícone pequeno e discreto por tema.
- **Como inspira o FIAS-ED**: modelo direto para a seção "Pontos para
  reflexão" e "Sugestões para próximas aulas" — cada card deve conter um
  conjunto de conteúdo relacionado, não um único ícone grande e frase
  curta.
- **O que não copiar**: a quantidade de temas simultâneos (mais de 40
  cards na mesma tela) geraria excesso de densidade para a interface do
  FIAS-ED, que deve mostrar poucos pontos por vez.

### 9. Panopto
- **URL**: https://www.panopto.com/
- **Tela analisada**: página inicial do produto, com seção de destaque,
  logos de instituições clientes e segmentação por público (educação
  superior, empresas, treinamento).
- **Elemento relevante**: métricas de resultado apresentadas como
  contexto de estudo de caso ("4,5x mais visualizações de conteúdo"),
  associadas a um link para o caso completo, não como número solto na
  tela principal.
- **Como inspira o FIAS-ED**: confirma que resultados quantitativos devem
  vir acompanhados de contexto textual explicativo, não como número
  isolado; e reforça o uso de logo/identidade de instituição parceira em
  vez de ilustração genérica.
- **O que não copiar**: a ausência de qualquer prévia real de gravação ou
  transcrição na home — para o FIAS-ED, a tela inicial deve mostrar a
  aula real do professor, não apenas texto de proposta de valor.

### 10. CDC — National Center for Health Statistics, Data Visualization
- **URL**: https://www.cdc.gov/nchs/data-visualization/index.htm
- **Tela analisada**: galeria de painéis de dados de mortalidade,
  natalidade e dados provisórios, com miniatura de imagem e descrição por
  painel.
- **Elemento relevante**: cada painel é descrito em uma frase objetiva
  (escopo do dado, período coberto) antes de qualquer imagem, em registro
  formal e sem linguagem promocional.
- **Como inspira o FIAS-ED**: modelo de legenda textual objetiva para os
  gráficos de "Ver padrões de interação" — uma frase descritiva acima do
  gráfico, explicando o que ele mostra, antes da própria visualização.
- **O que não copiar**: os painéis são de acesso a mapas e séries
  históricas de décadas — complexidade de filtro maior do que o professor
  do FIAS-ED precisa para revisar uma única aula.

### 11. Canvas LMS (Instructure)
- **URL**: https://www.instructure.com/canvas
- **Tela analisada**: página de produto com carrossel de funcionalidades
  (SpeedGrader, Gradebook, cursos-modelo, relatórios) e estatísticas de
  adoção.
- **Elemento relevante**: menção a "relatórios integrados" (*in-app
  reporting*) como funcionalidade de primeira classe, ao lado da correção
  de atividades — não como módulo separado de analytics.
- **Como inspira o FIAS-ED**: reforça manter o relatório da aula dentro
  do mesmo fluxo em que o professor já está (upload → processamento →
  relatório), sem exigir navegação a um módulo de "analytics" à parte.
- **O que não copiar**: paleta de destaque em vermelho/bordô e a
  quantidade de módulos comerciais cruzados (Mastery Connect, Parchment)
  citados na mesma página — o FIAS-ED deve permanecer um produto único e
  focado, sem sugerir um ecossistema de múltiplos produtos.
