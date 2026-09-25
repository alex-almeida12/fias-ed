# FIAS-ED — Estado de validação

**Data:** 23 de setembro de 2026
**Autor:** Alex Almeida (alex.amaral@alunos.ufersa.edu.br)
**Finalidade:** separar, de forma explícita, o que o sistema **faz de modo verificado** do que ele **ainda não mede de modo validado**.

---

## Sumário para leitura rápida

O FIAS-ED processa o áudio de uma aula e devolve uma descrição dos padrões de interação segundo o sistema de Flanders (FIAS). O caminho completo — do envio do áudio ao resultado — está **implementado e verificado como engenharia**: roda de ponta a ponta, sem acesso à rede, com os modelos reais, e está coberto por 798 testes automatizados.

O que **não** está estabelecido é a acurácia desse resultado em uma aula brasileira real. Há cinco fontes de incerteza encadeadas, descritas na seção 4, e nenhuma delas foi medida sobre gravação autêntica de sala de aula. O classificador tem métricas publicadas (F1 macro 0,7246), mas obtidas sobre texto limpo de outro domínio — não sobre a saída de transcrição automática que ele recebe em operação.

**Advertência sobre os números desta versão.** Desde a versão anterior deste documento, três mudanças alteraram a codificação e a entrada do classificador: o par que o classificador recebe passou a ser montado como o conjunto de treino o monta (seção 4.2), o silêncio passou a ser medido em vez de sair sempre zerado (seção 3.3) e a codificação passou a registrar cada mudança de categoria, e não uma marca por intervalo de 3 segundos (seção 3.3). **Resultado obtido antes dessas mudanças não é comparável com resultado obtido depois.** A versão das regras de codificação subiu de 2.0.0 para 3.0.0 exatamente para que essa incomparabilidade seja detectável e não silenciosa: o sistema recusa-se a reunir na mesma tabela aulas carimbadas com versões diferentes. Nenhuma aula já processada foi reprocessada.

Este documento existe para que essa distinção não precise ser inferida.

---

## 1. O que o sistema se propõe a fazer

O FIAS-ED recebe a gravação de uma aula e produz uma descrição de como o tempo da aula se distribuiu entre quatro grupos de interação: influência indireta do professor, influência direta do professor, fala do estudante e silêncio. A codificação segue o protocolo de Flanders (1970): registra-se uma categoria **a cada 3 segundos e a cada mudança de categoria** — os 3 segundos são a taxa mínima de amostragem, e não um balde em que a categoria dominante vence o intervalo.

O sistema **não** atribui nota, não compara professores e não emite juízo de qualidade. Essa restrição é de projeto, não de implementação: o vocabulário da interface proíbe os termos "avaliação", "nota", "desempenho" e "ranking", e há verificação automatizada que falha se qualquer um deles aparecer em texto visível ao usuário.

O processamento ocorre inteiramente na máquina local, sem envio de áudio a serviços externos. Os modelos são baixados uma única vez, na instalação, e o sistema em operação roda com acesso à rede desabilitado — condição verificada experimentalmente.

A décima categoria de Flanders é "silêncio **ou** confusão". O sistema mede a primeira metade e não mede a segunda, pelas razões apresentadas na seção 4.3. Onde este documento fala em silêncio, trata-se de silêncio, e não de silêncio-ou-confusão.

---

## 2. O que está verificado como engenharia

| Verificação | Resultado |
|---|---|
| Percurso completo pela interface, com modelos reais | Confirmado: de áudio validado a resultado FIAS, sem intervenção no banco de dados |
| Operação sem acesso à rede | Confirmado: separação de vozes carregada e executada com a rede desabilitada |
| Testes automatizados | 404 (serviço) + 151 (interface) + 243 (motor científico) = 798, todos passando |
| Reprodutibilidade da transcrição | A mesma gravação reprocessada produz o mesmo texto (parâmetros fixos, processador fixo) |
| Integridade dos modelos | Cada artefato conferido por resumo criptográfico contra um registro versionado antes do uso |

Durante a construção desta etapa foram identificados **47 defeitos**, todos em especificação e planejamento, nenhum sobrevivendo à implementação. Quatro deles eram da mesma natureza e merecem registro metodológico: **código que passava em todos os testes e falharia em operação real** — etapas do processamento que nenhum caminho de produção acionava, porque apenas os testes as acionavam. Foram encontrados por inspeção da cadeia completa contra a especificação, não pelos testes.

**Um quinto defeito dessa família sobreviveu à implementação, e é o assunto da seção 4.2.** O classificador recebia sua entrada montada de um modo que o conjunto de treino não usa, e nenhum teste poderia detectá-lo: todos verificavam que o par era montado como o código o montava, que é precisamente a pergunta errada. Foi encontrado comparando o código de produção com o código que **construiu o conjunto de treino** — a mesma técnica de inspeção da cadeia contra a fonte, aplicada uma fronteira adiante: a fronteira entre o produto e o experimento que o originou. O registro importa porque corrige a afirmação anterior de que nenhum defeito dessa natureza havia sobrevivido à implementação. Um sobreviveu, e produziu números que tinham aparência de medida.

---

## 3. O que está validado cientificamente

### 3.1 Classificador FIAS

Modelo `fias-bertimbau-ptbr-frente3`, ajustado sobre o BERTimbau (`neuralmind/bert-base-portuguese-cased`).

| Métrica | Valor |
|---|---|
| F1 macro | 0,7246 |
| Acurácia | 0,8231 |
| Kappa de Cohen | 0,7698 |
| Coeficiente de correlação de Matthews | 0,77 |
| Conjunto de teste | TalkMoves-FIAS-PTBR, n = 32.869 |

**Três ressalvas declaradas pelo próprio registro do modelo**, e que devem acompanhar qualquer citação desses números:

1. **O melhor ponto de verificação foi selecionado sobre o próprio conjunto de teste**, sem conjunto de validação separado. As métricas são, portanto, levemente otimistas.
2. **Os dados de origem são aulas de matemática de educação básica dos Estados Unidos, traduzidas automaticamente para o português** por modelo de linguagem (Mistral Small). Há risco de deslocamento de domínio em aulas brasileiras reais.
3. **Os rótulos FIAS não são anotação nativa**: foram derivados do conjunto TalkMoves por mapeamento conceitual acrescido de heurísticas.

Às três convém acrescentar uma quarta observação, que não é ressalva sobre o valor do número e sim condição para citá-lo: **essas métricas só descrevem o comportamento em operação enquanto a entrada em operação tiver a mesma forma que a entrada de treino.** Até a correção relatada na seção 4.2 ela não tinha, e nesse período as métricas acima não descreviam o que o sistema fazia com uma aula real. O número não mudou; mudou o que ele passa a ter o direito de descrever.

A versão embarcada para dispositivo móvel (`fias-bertimbau-ptbr-frente3-onnx-int8`) atinge acurácia de 0,7773 em aparelho de entrada, com latência média de 713 ms por segmento e pico de 182 MB de memória.

### 3.2 Transcrição e separação de vozes

Ambos os componentes estão registrados como **decisão de engenharia**, não como resultado medido — classificação que o próprio registro do projeto atribui a eles.

- **Transcrição** (`faster-whisper-small`): a taxa de erro de palavra não foi medida em áudio de sala de aula brasileira. A quantização em 8 bits, necessária para operar sem placa gráfica dedicada, degrada levemente o resultado em relação à precisão plena.
- **Separação de vozes** (`pyannote/speaker-diarization-3.1`): o erro de diarização não foi medido em áudio de sala de aula brasileira. O número de falantes não é fixado previamente, pois em uma sala não se sabe quantas vozes aparecerão; ele é estimado pelo próprio modelo.

### 3.3 Fidelidade da codificação ao protocolo

Esta subseção é de natureza distinta das duas anteriores: aqui não se mede acerto contra a aula, mede-se **conformidade do procedimento ao texto do protocolo**, o que é verificável por leitura da fonte. Duas correções desta versão são desse tipo, e ambas foram medidas sobre a aula real de referência (24 minutos, 213 trechos de fala).

**Medição — o registro a cada mudança de categoria.** A regra 3 de Flanders (1970) determina que, havendo mais de uma categoria ativa num intervalo de 3 segundos, todas devem ser registradas, e que a repetição do mesmo número serial só ocorre quando nada muda depois de 3 segundos. O sistema emitia exatamente uma marca por intervalo, com a categoria de maior cobertura vencendo — o que descarta toda mudança mais rápida que a grade.

| Grandeza medida na aula real | Regra anterior | Regra atual |
|---|---|---|
| Trechos de categoria constante preservados na ordem (de 106) | 74 (69,8 %) | **106 (100 %)** |
| Segmentos sem marca alguma sobre o próprio tempo | 3 | 0 |
| Células povoadas na matriz de transições | 16 | **22** |

*Interpretação.* Nenhuma célula da matriz foi perdida: as seis novas são transições que ocorreram na aula e que a regra de balde apagava. Como a matriz de transições é o instrumento em que o FIAS lê **padrões** de interação — quem segue quem —, um quarto das mudanças da aula ausente dela não é imprecisão de valor: é ausência do objeto que se pretende observar. Os índices agregados quase não se moveram (a proporção de fala docente passa de 1,000 para 0,928), o que ilustra a diferença entre os dois tipos de resultado: proporções toleram a perda de mudanças rápidas, matrizes não.

**Medição — a fonte do silêncio.** A regra 4 de Flanders determina registrar a categoria 10 quando o silêncio ultrapassa 3 segundos. Até esta versão a categoria saía zerada em toda aula, porque a não-fala era procurada nas lacunas **entre segmentos de transcrição** — e o detector de voz do transcritor cola as pausas para dentro dos segmentos, de modo que quase não resta lacuna a encontrar. A fonte passou a ser a atividade de fala da separação de vozes, com o mesmo limiar de 3 segundos do protocolo.

| Fonte da não-fala | Fala declarada | Silêncio medido na aula |
|---|---|---|
| Lacunas entre segmentos de transcrição | 98,6 % do áudio | 4 s (uma única lacuna alcança os 3 s do protocolo) |
| Atividade de fala da separação de vozes | 64,4 % do áudio | **78,2 s em 18 lacunas** (5,4 % da aula; a maior de 9,6 s) |

*Interpretação.* Duas medidas do mesmo fenômeno, na mesma aula, diferindo por uma ordem de grandeza. A diferença não é ruído: é a resposta à pergunta de qual sinal descreve ausência de fala. A extensão dos segmentos de transcrição descreve o que o transcritor decidiu agrupar; a atividade de fala descreve quando houve voz. Escolher a primeira produz um sistema que relata, de qualquer aula, que não houve silêncio. A escolha permanece registrada como **decisão de engenharia** — não há anotação humana de silêncio nesta gravação contra a qual conferi-la —, e o conjunto de dados exportado declara, por aula e em coluna própria, qual das duas fontes mediu aquela linha, para que médias entre aulas medidas de formas diferentes não passem despercebidas.

---

## 4. O que não está validado: a cadeia de erro não medida

Esta é a limitação central do trabalho no estado atual, e convém enunciá-la de forma direta.

O classificador foi avaliado sobre **texto**. Em operação, ele não recebe texto: recebe o resultado de uma transcrição automática, segmentada por uma separação automática de vozes. Entre o áudio da aula e o resultado FIAS há cinco fontes de incerteza, e **nenhuma foi medida sobre gravação autêntica de sala de aula brasileira**:

| # | Fonte de incerteza | Situação |
|---|---|---|
| 1 | Erro de transcrição (WER) | Não medido em áudio de aula brasileira |
| 2 | Erro de separação de vozes (DER) | Não medido em áudio de aula brasileira |
| 3 | Deslocamento de domínio do classificador (aulas dos EUA, traduzidas por máquina) | Declarado, não quantificado |
| 4 | Derivação dos rótulos FIAS por mapeamento conceitual, e não por anotação nativa | Declarado, não quantificado |
| 5 | Composição dos erros: o efeito de (1) e (2) sobre o desempenho de classificação | **Não medido** |

O item 5 merece destaque. Mesmo que o classificador mantivesse o F1 de 0,7246 sobre texto perfeito, o resultado que o professor vê depende de uma transcrição com erros e de uma atribuição de falantes com erros. **A acurácia de ponta a ponta do sistema em uma aula real é, hoje, desconhecida** — não estimada de forma otimista ou pessimista, mas simplesmente não medida.

Duas circunstâncias atenuam parcialmente o item 2 no desenho do produto, sem eliminá-lo: o professor confirma qual voz é a sua, e pode corrigir texto e atribuição de falante antes da classificação. A classificação sempre roda sobre o material que o professor aprovou. Isso desloca parte do erro para uma etapa humana revisável, mas não o mede.

**Por que o defeito descrito em 4.2 não acrescenta uma sexta linha.** A pergunta se impõe, porque aquele defeito produziu, em aula real, um desacordo maior do que qualquer uma das cinco fontes chegou a produzir em medição. A resposta é que ele não é da mesma espécie. As cinco linhas são propriedades do instrumento que ninguém mediu: taxas de erro desconhecidas e limitações declaradas da procedência dos rótulos. O formato de entrada violado não era propriedade desconhecida de coisa alguma — era discrepância entre o que o material de treino documenta e o que o código de produção fazia, com resposta certa disponível na própria fonte. Erro de emparelhamento tem conserto; incerteza não medida tem medição, que é outro verbo. Acrescentar uma sexta linha declararia aberta uma lacuna que está fechada.

*Convém registrar, porém, que a versão anterior deste documento sugeria o contrário.* Ao atribuir o desacordo de 55,4 % a alguma combinação dos itens 2 e 3 — separação de vozes ou deslocamento de domínio —, ela classificou como propriedade do domínio o que era defeito na montagem da entrada. A distinção não é acadêmica: deslocamento de domínio se enfrenta com dados de outro domínio, ao custo de meses; este defeito se enfrentava lendo o código que gerou o conjunto de treino. O que o episódio acrescenta à tabela não é uma linha, é uma advertência sobre como lê-la: **um número grande observado em aula real pode ser o rastro de um defeito de implementação, e não a medida da incerteza a que se atribui.** Nenhuma das cinco foi medida, e nenhuma delas explicava aquele número.

### 4.1 Por que as medições existentes não fecham essa lacuna

As medições de custo computacional (seção 5) foram feitas com **fala sintetizada**, gerada por um sintetizador de voz cujo modelo acústico é de língua inglesa. Esse material serve para medir **custo** — tempo de processamento e consumo de memória são determinados pela duração do áudio e pelo tamanho do modelo, não pelo conteúdo. Ele **não** serve para medir **acerto**: a pronúncia não é português brasileiro, e qualquer taxa de erro calculada sobre ele seria artefato do método.

Essa distinção está registrada tanto no código de medição quanto na documentação técnica.

### 4.2 O que a fração "incerta" media, afinal: um defeito na montagem da entrada

A versão anterior deste documento registrava, em aula real, **58,2 % das falas marcadas como incertas, com confiança média de 0,3985**, e concluía que esse número não media incerteza do classificador, e sim a taxa de desacordo entre o classificador e a atribuição de falante — desacordo de 55,4 %, cuja causa declarava desconhecida entre os itens 2 e 3 da tabela acima. A conclusão de que o número não media incerteza permanece. **A causa do desacordo, que era o que faltava, foi encontrada, e não é nenhum dos dois itens: era um defeito na montagem da entrada do classificador.**

**O formato de entrada.** O classificador recebe um par: um campo de **contexto** e o **turno a classificar**. No conjunto de treino, o contexto não é "o turno anterior": é o turno anterior **de outro falante**, e fica vazio quando o mesmo falante continua. Isso não é inferência sobre os dados — está escrito no código que montou o conjunto, cujo ramo para professor depois de professor grava literalmente um contexto vazio. As taxas do conjunto de treino (186.955 linhas) confirmam: o contexto está vazio em 89,8 % das linhas de "dá instruções", em 83,5 % das de "expõe" e em apenas 33,2 % das de "aceita ou utiliza ideias dos alunos" — que é, por definição, a categoria que depende de haver ideia de aluno no contexto para o professor acolher.

Em produção, o contexto era preenchido **sempre** com o turno anterior, sem olhar quem havia falado. Numa aula expositiva isso significa o professor depois do próprio professor, configuração que no treino teria contexto vazio. Na aula de referência, **212 dos 213 pares** levavam um contexto que o treino nunca teria colocado ali.

**Medição — o efeito na aula real.** Os 213 trechos foram reclassificados pelo caminho de produção, antes e depois da correção. A revisão de vozes marcara os 213 como fala do professor.

| Grandeza | Antes | Depois |
|---|---|---|
| Segmentos em categoria de fala do estudante | 100 | 0 |
| Segmentos em categoria de silêncio | 18 | 0 |
| Desacordo entre classificação e papel do falante | 55,4 % | **0,0 %** |
| Classificações marcadas como incertas | 58,2 % | **0,5 %** |
| Confiança publicada (mediana) | 0,1073 | 0,9565 |
| Confiança bruta do modelo (média) | 0,8917 | 0,8990 |
| Confiança bruta do modelo (mediana) | 0,9668 | 0,9565 |

**A categoria crua de 138 dos 213 segmentos (64,8 %) mudou.**

*Interpretação.* As duas últimas linhas da tabela são as que mais importam, e são as que não melhoram. **A confiança bruta do modelo não subiu com a correção: ele sempre esteve confiante — estava confiante sobre a pergunta errada.** A confiança publicada despencava não porque o modelo hesitasse, mas porque ele depositava a massa de probabilidade numa categoria de aluno e a restrição por papel a arrastava de volta para a melhor categoria de professor, publicando o resíduo. A restrição por papel, que a versão anterior deste documento identificou como origem aparente da incerteza, não estava medindo dúvida: estava mascarando um defeito a montante. Vale notar que, ao mascará-lo, também o conteve — sem ela, aquela aula teria sido relatada ao professor como tendo quase metade do tempo em fala de estudante, numa aula sem um único turno de estudante.

**Consequência que altera um resultado.** A razão de influência indireta, com que o FIAS compara a influência indireta e a direta do professor, **cai de 0,5375 para 0,3575** — queda de 34 %. A causa é localizada: a categoria "aceita ou utiliza ideias dos alunos" passa de 22 segmentos a zero, e essa categoria sustenta metade do numerador do índice. Numa aula em que não houve um só turno de estudante não existe ideia de estudante para o professor acolher; as 22 marcas anteriores eram **fabricadas pelo contexto indevido**, que apresentava ao modelo a fala anterior do próprio professor como se fosse contribuição alheia. Num cenário com alternância real de falantes a categoria continua permitida e continua a ser escolhida — poucas vezes, e agora por haver de fato fala de outro no contexto. A correção não elimina a categoria: faz com que ela seja merecida.

A influência indireta medida até aqui, portanto, estava inflada. Os índices que não dependem de **qual** categoria de professor foi atribuída quase não se movem — a proporção de fala docente vai de 0,9275 a 0,9266 —, porque quem os governa é a restrição por papel e a atividade de fala do separador de vozes, e não a escolha livre do modelo. O que muda é a distribuição **dentro** da fala do professor, que é de onde saem a razão de influência indireta e a matriz de transições: exatamente as duas leituras que o FIAS existe para produzir.

**Procedência do limiar.** Registro que permanece válido, e que a correção não torna dispensável: o valor de 0,5 abaixo do qual uma classificação é marcada como incerta **não tem origem declarada**. O registro científico do projeto o classifica como decisão de engenharia, e a referência de fonte associada ao classificador remete ao roteiro do experimento original apenas para o índice de rótulo, o tokenizador e o comprimento máximo de sequência — o limiar não é mencionado em ponto algum. É uma linha convencional. A queda de 58,2 % para 0,5 % nas classificações marcadas como incertas não a legitima: apenas retira dela a ocasião de ser citada.

**O que esta medição autoriza dizer.** Que o sistema violava, em toda aula, o formato de entrada com que o classificador foi treinado; que a violação alterava a categoria de dois terços dos segmentos de uma aula real e um índice publicado em 34 %; e que o número lido até aqui como incerteza do modelo era o rastro dessa violação.

**O que esta medição não resolve, e é a maior parte.** Nenhuma das cinco lacunas da tabela da seção 4. Confiança não é acerto, e uma confiança bruta de 0,90 é tão compatível com um modelo certo quanto com um modelo seguro e errado — antes da correção ela já valia 0,89, sobre classificações que hoje se sabem erradas. A aula de referência continua sem transcrição de referência e sem anotação FIAS nativa, de modo que **não se sabe se as 213 categorias atribuídas depois da correção estão certas**; sabe-se apenas que agora são perguntadas na forma em que o modelo foi treinado a responder, e que não contradizem mais a atribuição de falante. Um defeito encontrado e corrigido é mérito do procedimento de verificação — inspeção da cadeia contra a fonte —, e não evidência sobre a acurácia do sistema, que segue desconhecida pelas mesmas cinco razões de antes.

### 4.3 O que o instrumento atual não consegue medir: a confusão

A décima categoria de Flanders é "silêncio **ou** confusão", definida esta última como comunicação que o observador não consegue compreender. O sistema implementa o silêncio (seção 3.3) e **não** implementa a confusão. A ausência não é omissão: foi medida, e o resultado é negativo. Resultado negativo é resultado, e convém registrá-lo com os números que o sustentam.

Detectar confusão exigiria duas condições simultâneas: sobreposição de falantes **e** ininteligibilidade. A primeira a separação de vozes fornece. A segunda dependeria dos sinais de qualidade da decodificação do transcritor, e estes não servem, por dois motivos independentes.

**Medição — resolução.** Os três sinais de qualidade do transcritor não descrevem o segmento: descrevem a **janela de decodificação de 30 segundos** que o produziu, e são idênticos em todos os segmentos nascidos da mesma janela. Os 213 segmentos da aula vieram de 51 janelas, com mediana de 28,0 segundos de aula por janela e máximo de 48,5. A sobreposição de vozes, por sua vez, é nesta aula um fenômeno de **0,7 segundo** (mediana de 658 ms; máximo de 1.957 ms; 13 ocorrências, 0,6 % do tempo). Um limiar aplicado a um sinal que descreve 28 segundos arrastaria a janela inteira para a categoria 10 — meio minuto de aula marcado como confusão por 0,7 segundo de sobreposição.

**Medição — separação.** No nível da janela, que é a unidade que o sinal de fato descreve, os trechos com sobreposição não se distinguem do resto da aula em nenhum dos três sinais (teste de Mann-Whitney bilateral: p = 0,62; 0,74; 0,23), e suas faixas de valores ficam inteiramente contidas nas faixas dos trechos sem sobreposição. No nível do segmento um dos sinais chegaria a p = 0,037, mas é pseudorreplicação: 4 das 13 ocorrências de sobreposição caem num único segmento. O outro sinal considerado — segmento com duração e sem texto — não ocorreu uma única vez nesta aula (0 de 213).

*Interpretação qualitativa, e é ela que fecha o caso.* A janela com a **pior** qualidade de decodificação da aula inteira é fala perfeitamente inteligível do professor dando instruções em frases curtas. Ali o sinal mede ritmo e vocabulário, não ininteligibilidade. Um limiar extraído desses números seria um valor inventado com aparência de medida, e uma categoria do protocolo passaria a ser governada por ele.

**Consequência declarada.** A categoria 10 recebe só silêncio nesta versão, e o índice correspondente mede silêncio. Um resultado deste sistema autoriza dizer "confusão não foi medida"; **não** autoriza dizer "esta aula não teve confusão". A distinção está registrada no próprio arquivo de regras, junto da medição que a sustenta.

**O que mudaria isso.** Um sinal com resolução de segmento ou menor — alinhamento por palavra do próprio transcritor, com probabilidade por palavra, ou um detector de fala sobreposta treinado —, calibrado contra um trecho anotado por um humano como "não dá para saber quem está falando". Sem esse trecho de referência não há limiar calibrável, até porque a sobreposição desta aula, 13 ocorrências em 24 minutos, não chega a ser amostra. Nesta versão a confiança de decodificação passou a ser **gravada** por segmento, o que antes não acontecia; gravar não é detectar, e nenhuma regra de codificação lê esse campo. Sem ele, porém, nem esta medição se repetiria sem reprocessar o áudio.

### 4.4 O único corte arbitrado do sistema: quando FIAS e QTI "concordam"

O MTSS é a ferramenta pedagógica do estudo, e nesta versão passou a considerar as duas medidas: as recomendações continuam sendo **disparadas pelo FIAS**, e o resultado do QTI entra depois, qualificando cada recomendação como concordante, discordante ou inconclusiva. O QTI não entra nas condições das regras, e nenhuma regra nova foi criada — a correspondência entre recomendação e par de triangulação emerge do fato que os dois já compartilham (`ID_RATIO` com `TRI_INFLUENCE`; categoria 2 e 3 com `TRI_WARMTH`; categoria 7 com `TRI_TENSION`; categorias 8 e 9 com `TRI_STUDENT_VOICE`, cujo índice `PIR` é cat. 9/(cat. 8+cat. 9)).

Isso obrigou a comparar grandezas de naturezas diferentes, e é aí que está o corte arbitrado.

**O lado do FIAS não recebeu faixa nenhuma, e essa é a parte defensável.** As regras do MTSS não usam proporção: usam presença (`count_cat_7 > 0`), ausência (`count_cat_2 == 0` com `count_cat_8 > 0`) e um limiar de razão (`ID_RATIO < 1`), todas com referência à literatura — a tabela `art2-fias-tier1` do capítulo 4 e, para a razão, SIMB. Quando a regra dispara, o FIAS já disse o que tinha a dizer, e disse com fundamentação; classificá-lo de novo seria redundante.

Faixas no FIAS foram consideradas e **rejeitadas com motivo mensurável**: dividir a proporção da categoria em terços do intervalo teórico exigiria, para a faixa "alta", que a categoria ocupasse mais de 66,7% da aula. Elogio numa aula real ocupa entre 1% e 5%. Nenhuma categoria de baixa frequência cairia ali, metade do critério nunca dispararia, e o sistema pareceria funcionar enquanto estivesse morto.

**O lado do QTI recebeu faixas, e este é o único número inventado.** Sobre o intervalo teórico da escala Likert de 1 a 5: baixa abaixo de 2,33, média entre 2,33 e 3,67, alta acima de 3,67. É decisão de engenharia declarada, **não achado da literatura** — a literatura do QTI interpreta por tipologia de perfis e comparação relativa, sem faixas absolutas. O que sustenta a divisão em três é apenas o fato de a Likert ter intervalo teórico fechado e conhecido, ao contrário da proporção do FIAS, que não tem teto prático.

Duas restrições de desenho acompanham o corte. O octante "Liderança" **não participa** da decisão em `TRI_INFLUENCE`, por efeito de teto — tem quase nenhuma variância entre professores, e incluí-lo empurraria quase toda aula para "concorda"; continua exibido como dado de contexto. E três regras habilitadas não têm par (`MTSS_QUESTIONS_PRESENT`, `MTSS_EXPOSITIVE_PREDOMINANCE`, `MTSS_INSTRUCTIONS_PREDOMINANCE`), porque nenhum par cobre a categoria 4 nem a categoria modal: saem só com evidência do FIAS, e a tela diz isso, em vez de forçar correspondência que a literatura não sustenta.

**Limitação conhecida — a definição operacional do zero.** "Zero" significa zero ocorrências na transcrição, sem limiar de tolerância. A regra herda, portanto, a taxa de erro da transcrição e da classificação, que é justamente a cadeia não medida da seção 4. O erro é assimétrico: um elogio que o reconhecimento de fala não captou, ou que o classificador rotulou noutra categoria, produz um "zero" que não corresponde à sala — enquanto o excesso de elogio é bem mais difícil de fabricar por engano.

**Dois níveis de validação, e o mais fraco é o que o professor lê.** Os pares de triangulação e as regras do MTSS estão marcados `PENDING_SCIENTIFIC_VALIDATION`. As recomendações — o texto que de fato aparece na tela para o professor — estão um degrau abaixo: `draft_pending_researcher_review`, rascunho aguardando revisão do pesquisador. A distinção não é cosmética. Significa que a regra que dispara a recomendação tem fundamentação na literatura e aguarda validação empírica, enquanto a redação da recomendação em si ainda não passou por revisão de ninguém. Um resultado deste sistema autoriza dizer "esta regra derivou da tabela do capítulo 4"; não autoriza apresentar o texto da recomendação como orientação pedagógica revisada.

**Consequência declarada.** Quando o QTI cai na faixa média, ou quando a coleta não é exibível, o sistema **não conclui nada** e a recomendação sai sem marca. Em discordância, mostra as duas medidas e faz uma pergunta, nunca uma afirmação — e a pergunta reconhece o limite do instrumento, porque o FIAS capta apenas comportamento verbal. Proximidade docente também se manifesta por olhar, postura e disponibilidade, e nada disso entra num áudio transcrito. Um resultado deste sistema autoriza dizer "as duas medidas divergiram"; não autoriza dizer qual delas está certa.

---

## 5. Custo computacional medido

Medições em máquina sem placa gráfica dedicada, com 16 núcleos de processamento e 15,5 GB de memória disponível.

### 5.1 Execução completa, medida no processo real

Uma aula de 46 minutos foi processada de ponta a ponta pela interface, com os modelos reais, e o consumo do processo de trabalho foi amostrado ao longo da execução:

| Etapa | Tempo | Proporção da duração do áudio | Memória acumulada no processo |
|---|---|---|---|
| Validação e preparo | 0,5 s | ≈ 0 | — |
| Transcrição (5 trechos) | 387,6 s | 0,140× | 1,54 GB |
| Separação de vozes | 1.451,7 s | 0,526× | 2,73 GB |
| Classificação FIAS | 45,9 s | 0,017× | **4,75 GB** |
| **Total** | **31,6 min** | **0,683×** | **4,75 GB (31 % da memória disponível)** |

**O pico é da classificação, e nessa execução esse estágio não tinha teto.** O classificador processava todos os segmentos da aula em uma única passagem, sem divisão em lotes, de modo que o consumo crescia linearmente com o número de segmentos — isto é, com a duração da aula **e** com o quanto a fala é fragmentada. Uma aula da mesma duração, porém com mais trocas de turno, consumiria proporcionalmente mais.

**A divisão em lotes foi implementada depois desta medição, e o teto passou a existir.** O classificador processa 16 segmentos por passagem. Medido no modelo real, isoladamente e com o mesmo método das demais seções: 381 segmentos — a quantidade desta aula — custavam 4,23 GB de pico em passagem única e passaram a custar **1,07 GB**; 762 segmentos custavam 7,65 GB e custam os mesmos 1,07 GB. O consumo máximo do estágio deixou de ser função do material processado, e o tempo de processamento não piorou. A execução completa da tabela acima não foi repetida, de modo que o número de 4,75 GB registra o comportamento anterior à correção, não o atual.

**A correção não altera a classificação de nenhuma fala.** A entrada do modelo é idêntica linha a linha, porque cada par de turnos é preenchido até 256 tokens independentemente dos demais. A saída difere apenas na última casa da representação em float32, cuja ordem de redução depende da dimensão do lote: 1,9 × 10⁻⁶ no pior dos 381 segmentos, contra uma margem mínima de 0,231 entre o maior e o segundo maior logit de cada fala — nenhuma categoria muda. O que a exigência de reprodutibilidade pede é que a mesma aula reprocessada produza o mesmo resultado, e isso o lote de tamanho fixo garante integralmente.

### 5.2 Medições por etapa, em laboratório

Extrapoladas para uma aula de 90 minutos, medindo cada etapa isoladamente:

| Etapa | Tempo | Proporção da duração do áudio | Pico isolado |
|---|---|---|---|
| Transcrição | ≈ 15 min | 0,17× | 1,14 GB |
| Separação de vozes | ≈ 54 min | 0,60× | 2,58 GB |

Estes números medem cada etapa sozinha e **não somam ao consumo real**, pelo motivo da seção anterior: as três etapas compartilham um mesmo processo, e a memória já solicitada não retorna ao sistema entre elas.

Três observações metodológicas:

1. **A linha de 90 minutos da separação de vozes é medida, não extrapolada.** Diferentemente da transcrição, essa etapa não divide o áudio em trechos, de modo que uma aula longa é o caso real e foi executada integralmente (53,8 minutos de relógio).
2. **A transcrição de 90 minutos é uma extrapolação declarada.** A linearidade entre duração e tempo de processamento foi testada e **não se confirmou**. A extrapolação apoia-se em outro fato: o produto divide o áudio em trechos de 10 minutos e processa cada um independentemente, de modo que o caso longo é o trecho de 10 minutos — este sim medido — repetido. A unidade repetida é medida; apenas o número de repetições é inferido.
3. **O custo dominante é a separação de vozes**, que consome 3,6 vezes o tempo da transcrição. Caso o tempo total precise ser reduzido, é nessa etapa que a intervenção tem efeito; trocar o modelo de transcrição por um menor economizaria cerca de 13 dos 69 minutos.

Quanto à memória, as etapas se comportam de forma oposta, e convém não generalizar de uma para a outra. Na separação de vozes o consumo quase não depende da duração (2,41 GB para 2,5 minutos contra 2,58 GB para 90 minutos), pois é dominado pelo modelo carregado. Na classificação o consumo crescia com a quantidade de segmentos, pela razão descrita na seção 5.1; com a divisão em lotes ele passou a ser constante (1,07 GB, medidos tanto para 381 quanto para 762 segmentos), de modo que nenhum dos três estágios tem mais consumo proporcional ao tamanho da aula.

---

## 6. Restrição de uso não comercial

O classificador FIAS foi ajustado sobre o conjunto **TalkMoves**, cuja licença é **CC BY-NC-SA 4.0**. A cláusula *NC* é de uso não comercial.

| Uso | Situação |
|---|---|
| Pesquisa acadêmica, incluindo esta dissertação | Permitido |
| Publicação de resultados e de código | Permitido, mantendo atribuição e a mesma licença |
| Comercialização, licenciamento a rede de ensino, ou uso em serviço pago | **Não permitido** sem retreinar o classificador com outros dados |

A restrição decorre dos **dados de treino**, não do código: os pesos base do BERTimbau são MIT. Um classificador treinado do zero com dados próprios removeria a limitação — e removeria também, convém notar, as ressalvas de deslocamento de domínio da seção 3.1.

---

## 7. O que falta para fechar as lacunas

Em ordem de valor científico:

1. **Obter gravação autêntica de aula brasileira com transcrição de referência**, ainda que de 10 a 15 minutos. Com ela é possível medir, pela primeira vez, a taxa de erro de transcrição, o erro de separação de vozes e — o mais importante — o efeito da composição desses erros sobre a classificação FIAS. Esse único insumo converte três lacunas em três resultados.
2. **Anotação FIAS nativa de ao menos uma aula brasileira**, para verificar se o mapeamento conceitual derivado do TalkMoves se sustenta fora do domínio de origem. É também a única forma de saber se as categorias atribuídas depois da correção da seção 4.2 estão certas: hoje sabe-se apenas que a pergunta feita ao modelo passou a ter a forma com que ele foi treinado.
3. **Conjunto de validação separado do conjunto de teste**, caso o classificador venha a ser retreinado, eliminando o viés otimista declarado na seção 3.1.
4. **Trecho de aula anotado por humano como ininteligível**, com alinhamento por palavra ou detector de fala sobreposta, caso se pretenda medir a metade "confusão" da categoria 10. Sem ele não há limiar calibrável, e a categoria continua recebendo só silêncio (seção 4.3).

O item 1 é o de melhor relação entre esforço e retorno: é o único que, isoladamente, transforma "o sistema funciona" em "o sistema mede o que afirma medir".

---

## Anexo — Procedência e reprodutibilidade

Cada modelo utilizado está declarado em um registro versionado (`fias-ed-shared/scientific-config/models.json`) com identificador, revisão fixada, licença, métricas quando existem, limitações e referência à fonte.

O sistema recusa-se a executar com modelo que o registro não declare — **e também com modelo que o registro declare sem ter adotado**. A distinção importa: alguns pesos constam do registro apenas para preservar a procedência de uma medição publicada, e não por terem sido validados para uso. É o caso dos dois tamanhos menores de modelo de transcrição que aparecem na tabela da seção 5.2. A autorização de uso é uma lista de estados explicitamente permitidos, de modo que um estado novo entra recusado por padrão, e não adotado por omissão.

As regras de codificação também são versionadas, e pelo mesmo motivo. A versão vigente é **3.0.0**; a anterior, 2.0.0, produziu resultados que **não são comparáveis** com os atuais, porque a entrada do classificador mudou de forma e dois terços das categorias de uma aula real mudaram com ela. O sistema recusa reunir na mesma tabela aulas carimbadas com versões diferentes, e a recusa nomeia quais aulas estão em qual versão. Não há conversão entre as versões, e inventar uma seria o mesmo defeito com outra roupa. As aulas já gravadas sob 2.0.0 permanecem como estão: o que fazer com elas é decisão de pesquisa, e não de engenharia.

As fontes científicas — documentação dos experimentos e pesos treinados — são conferidas por instantâneo criptográfico a cada verificação, de modo que alteração silenciosa é detectável.

As referências de licença dos componentes de terceiros, incluindo as atribuições exigidas pelas licenças Creative Commons, estão em `THIRD_PARTY_LICENSES.md`, na raiz do repositório.

---

*Documento gerado a partir do registro de execução da etapa W2 e do registro científico versionado do projeto. Os números apresentados correspondem a execuções reais, com as saídas preservadas no histórico do repositório.*
