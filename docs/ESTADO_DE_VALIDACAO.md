# FIAS-ED — Estado de validação

**Data:** 23 de setembro de 2026
**Autor:** Alex Almeida (alex.amaral@alunos.ufersa.edu.br)
**Finalidade:** separar, de forma explícita, o que o sistema **faz de modo verificado** do que ele **ainda não mede de modo validado**.

---

## Sumário para leitura rápida

O FIAS-ED processa o áudio de uma aula e devolve uma descrição dos padrões de interação segundo o sistema de Flanders (FIAS). O caminho completo — do envio do áudio ao resultado — está **implementado e verificado como engenharia**: roda de ponta a ponta, sem acesso à rede, com os modelos reais, e está coberto por 711 testes automatizados.

O que **não** está estabelecido é a acurácia desse resultado em uma aula brasileira real. Há cinco fontes de incerteza encadeadas, descritas na seção 4, e nenhuma delas foi medida sobre gravação autêntica de sala de aula. O classificador tem métricas publicadas (F1 macro 0,7246), mas obtidas sobre texto limpo de outro domínio — não sobre a saída de transcrição automática que ele recebe em operação.

Este documento existe para que essa distinção não precise ser inferida.

---

## 1. O que o sistema se propõe a fazer

O FIAS-ED recebe a gravação de uma aula e produz uma descrição de como o tempo da aula se distribuiu entre quatro grupos de interação: influência indireta do professor, influência direta do professor, fala do estudante e silêncio. A codificação segue o protocolo de Flanders, com intervalos de 3 segundos (Flanders, 1970).

O sistema **não** atribui nota, não compara professores e não emite juízo de qualidade. Essa restrição é de projeto, não de implementação: o vocabulário da interface proíbe os termos "avaliação", "nota", "desempenho" e "ranking", e há verificação automatizada que falha se qualquer um deles aparecer em texto visível ao usuário.

O processamento ocorre inteiramente na máquina local, sem envio de áudio a serviços externos. Os modelos são baixados uma única vez, na instalação, e o sistema em operação roda com acesso à rede desabilitado — condição verificada experimentalmente.

---

## 2. O que está verificado como engenharia

| Verificação | Resultado |
|---|---|
| Percurso completo pela interface, com modelos reais | Confirmado: de áudio validado a resultado FIAS, sem intervenção no banco de dados |
| Operação sem acesso à rede | Confirmado: separação de vozes carregada e executada com a rede desabilitada |
| Testes automatizados | 352 (serviço) + 151 (interface) + 208 (motor científico) = 711, todos passando |
| Reprodutibilidade da transcrição | A mesma gravação reprocessada produz o mesmo texto (parâmetros fixos, processador fixo) |
| Integridade dos modelos | Cada artefato conferido por resumo criptográfico contra um registro versionado antes do uso |

Durante a construção desta etapa foram identificados **47 defeitos**, todos em especificação e planejamento, nenhum sobrevivendo à implementação. Quatro deles eram da mesma natureza e merecem registro metodológico: **código que passava em todos os testes e falharia em operação real** — etapas do processamento que nenhum caminho de produção acionava, porque apenas os testes as acionavam. Foram encontrados por inspeção da cadeia completa contra a especificação, não pelos testes.

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

A versão embarcada para dispositivo móvel (`fias-bertimbau-ptbr-frente3-onnx-int8`) atinge acurácia de 0,7773 em aparelho de entrada, com latência média de 713 ms por segmento e pico de 182 MB de memória.

### 3.2 Transcrição e separação de vozes

Ambos os componentes estão registrados como **decisão de engenharia**, não como resultado medido — classificação que o próprio registro do projeto atribui a eles.

- **Transcrição** (`faster-whisper-small`): a taxa de erro de palavra não foi medida em áudio de sala de aula brasileira. A quantização em 8 bits, necessária para operar sem placa gráfica dedicada, degrada levemente o resultado em relação à precisão plena.
- **Separação de vozes** (`pyannote/speaker-diarization-3.1`): o erro de diarização não foi medido em áudio de sala de aula brasileira. O número de falantes não é fixado previamente, pois em uma sala não se sabe quantas vozes aparecerão; ele é estimado pelo próprio modelo.

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

### 4.1 Por que as medições existentes não fecham essa lacuna

As medições de custo computacional (seção 5) foram feitas com **fala sintetizada**, gerada por um sintetizador de voz cujo modelo acústico é de língua inglesa. Esse material serve para medir **custo** — tempo de processamento e consumo de memória são determinados pela duração do áudio e pelo tamanho do modelo, não pelo conteúdo. Ele **não** serve para medir **acerto**: a pronúncia não é português brasileiro, e qualquer taxa de erro calculada sobre ele seria artefato do método.

Essa distinção está registrada tanto no código de medição quanto na documentação técnica.

### 4.2 A confiança declarada pelo classificador, e por que a fração "incerta" não é uma medida

Para cada trecho de fala o sistema publica um número de confiança e marca como "incerta" toda classificação abaixo de 0,5. Uma leitura preliminar desse material em uma aula real havia registrado **58,2 % das falas marcadas como incertas, com confiança média de 0,3985**. A reclassificação descrita a seguir reproduz esses dois números exatamente — e mostra que eles não medem o que aparentam medir.

**Procedência do limiar.** O valor de 0,5 **não tem origem declarada**. O registro científico do projeto o classifica como decisão de engenharia, e a referência de fonte associada ao classificador remete ao roteiro do experimento original apenas para o índice de rótulo, o tokenizador e o comprimento máximo de sequência — o limiar não é mencionado em ponto algum. É uma linha convencional, e nenhuma afirmação deve repousar sobre ela.

**Medição.** Os 213 trechos de fala de uma gravação autêntica de 24 minutos foram reclassificados pelo modelo de produção, todos atribuídos ao professor — que foi o que a separação de vozes produziu na execução real daquela aula. A distribuição da confiança publicada:

| Estatística | Valor |
|---|---|
| Mínimo | 0,0001 |
| Primeiro quartil | 0,0018 |
| Mediana | 0,1073 |
| Terceiro quartil | 0,8930 |
| Máximo | 0,9984 |
| Média | 0,3985 |
| Desvio-padrão | 0,4253 |

*Interpretação.* A distribuição não tem centro: 47,9 % das falas ficam abaixo de 0,05 e 17,8 % ficam acima de 0,95, enquanto apenas 20 das 213 (9,4 %) caem entre 0,30 e 0,70. **A média de 0,3985 não descreve fala nenhuma** — é o resultado de somar duas populações separadas, e citá-la como "a confiança do classificador nesta aula" descreve um valor que o sistema praticamente nunca produz.

**Medição — sensibilidade ao limiar.** A fração marcada como incerta, variando a linha de corte:

| Limiar | Falas abaixo | Fração |
|---|---|---|
| 0,30 | 113 de 213 | 53,1 % |
| 0,40 | 116 de 213 | 54,5 % |
| 0,50 | 124 de 213 | **58,2 %** |
| 0,60 | 130 de 213 | 61,0 % |
| 0,70 | 133 de 213 | 62,4 % |

*Interpretação.* Ao contrário do que a arbitrariedade do limiar faria supor, **a fração quase não depende dele**: dobrar o limiar, de 0,30 para 0,60, move o resultado em oito pontos percentuais. A razão é a forma da distribuição — não há massa na faixa intermediária para a linha atravessar. A fragilidade dessa estatística, portanto, não está na escolha do limiar. Está no que o número conta.

**Medição — antes e depois da restrição por papel.** O sistema aplica, após a classificação, uma restrição que impede que uma fala atribuída ao professor receba categoria de aluno. Comparando a confiança na escolha livre do modelo com a confiança publicada após essa restrição:

| Grandeza | Média | Mediana | Mínimo |
|---|---|---|---|
| Confiança na escolha livre do modelo | 0,8917 | 0,9668 | 0,3920 |
| Confiança publicada, após a restrição | 0,3985 | 0,1073 | 0,0001 |

Em **118 dos 213 trechos (55,4 %)** a categoria que o modelo escolheu por conta própria não era categoria de professor: 95 vezes "resposta do aluno", 18 vezes "silêncio ou confusão" e 5 vezes "iniciativa do aluno". Nesses casos a restrição substitui a escolha pela categoria de professor mais provável, e a confiança publicada passa a ser a probabilidade que o modelo havia deixado como resíduo — de mediana 0,0019. Nos outros 95 trechos, em que o modelo já havia escolhido uma categoria de professor, a confiança tem média 0,8507 e apenas 6 (6,3 %) ficam abaixo de 0,5. Nos 118 restantes, ficam todos os 118.

*Interpretação.* **A incerteza não é do modelo: é produzida pela restrição por papel.** O classificador, nesta aula, é confiante — sua confiança mediana na própria escolha é 0,9668, e em nenhum dos 213 trechos cai abaixo de 0,39. A fração "incerta" é, quase inteiramente, a taxa de divergência entre o classificador e a atribuição de falante, grandeza que o sistema já registra em separado e que nesta execução vale exatamente 0,5540. Dito de outro modo: dos 58,2 %, cerca de 55,4 pontos são divergência e menos de 3 pontos são hesitação do modelo.

Convém registrar que essa reatribuição não redistribui a probabilidade entre as sete categorias admitidas ao professor — publica a probabilidade original da categoria escolhida. Como exercício contrafactual sobre as mesmas saídas, se houvesse redistribuição a confiança teria mediana 0,7742 e 16,4 % das falas ficariam abaixo de 0,5, em vez de 58,2 %. O número muda por uma convenção de cálculo, não por uma propriedade da aula — mais uma razão para não citá-lo como medida.

**Medição — o piso do acaso.** A confiança publicada é a probabilidade que o modelo atribui a uma categoria entre as **dez** que ele distingue, sem redistribuição. O piso do acaso aplicável a esse número é, portanto, 1/10 = **0,100** — e não 1/7 ≈ 0,143, que valeria apenas se houvesse redistribuição entre as sete categorias de professor. A média de 0,3985 é 4,0 vezes esse piso; a mediana, 0,1073, é 1,07 vez. **106 das 213 falas (49,8 %) ficam abaixo do piso do acaso.**

*Interpretação.* Confiança abaixo do acaso não é confiança baixa — é sinal de que, para aquelas falas, o número não está em escala de confiança. Nos 95 trechos em que está, a média de 0,8507 é 8,5 vezes o piso.

**Medição — por categoria.** Das sete categorias de professor, apenas quatro foram atribuídas nesta aula; "aceita sentimentos", "elogia ou encoraja" e "critica ou justifica autoridade" não aparecem uma única vez. Entre as quatro atribuídas, a confiança publicada difere bastante (média 0,3214 em "expõe" contra 0,6788 em "dá instruções"), mas a diferença desaparece quando se olham apenas os 95 trechos não reatribuídos:

| Categoria atribuída | Confiança média (todas as falas) | Confiança média (só as não reatribuídas) |
|---|---|---|
| Aceita ou usa ideias | 0,2836 (n = 22) | 0,7168 (n = 8) |
| Faz perguntas | 0,6372 (n = 49) | 0,8878 (n = 34) |
| Expõe | 0,3214 (n = 137) | 0,8473 (n = 49) |
| Dá instruções | 0,6788 (n = 5) | 0,8440 (n = 4) |

*Interpretação.* **Não há categoria sistematicamente incerta.** A aparência de que "expõe" e "aceita ou usa ideias" seriam categorias frágeis é efeito de destino: 88 dos 118 trechos reatribuídos caem em "expõe". Onde o modelo decide sozinho, as quatro categorias ficam entre 0,72 e 0,89, sem padrão que distinga uma das outras.

**O que esta medição autoriza dizer.** A distribuição acima é medida e pode ser citada, com a ressalva de que provém de uma única aula. A frase "58,2 % das categorias foram marcadas como incertas" **não deve ser citada como medida de incerteza do classificador**: ela é quase inteiramente a taxa de divergência entre classificador e atribuição de falante, expressa numa escala em que metade dos valores fica abaixo do acaso. A grandeza correspondente, quando for necessário citá-la, é a própria taxa de divergência — 55,4 % nesta aula —, que é o que de fato foi observado.

**O que esta medição não resolve.** Nenhuma das cinco lacunas da tabela acima. Confiança não é acerto: um modelo confiante e errado produz exatamente os números da coluna da escolha livre. Esta gravação não tem transcrição de referência nem anotação FIAS nativa, de modo que não se sabe qual das duas fontes da divergência de 55,4 % predomina — se a separação de vozes atribuiu ao professor falas que eram de aluno (item 2 da tabela), se o classificador erra fora do domínio em que foi treinado (item 3), ou ambas. O que a medição acrescenta é que essa divergência **existe e é grande em aula real**, e que o número que vinha sendo lido como incerteza do modelo é, na verdade, o rastro dela.

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
2. **Anotação FIAS nativa de ao menos uma aula brasileira**, para verificar se o mapeamento conceitual derivado do TalkMoves se sustenta fora do domínio de origem.
3. **Conjunto de validação separado do conjunto de teste**, caso o classificador venha a ser retreinado, eliminando o viés otimista declarado na seção 3.1.

O item 1 é o de melhor relação entre esforço e retorno: é o único que, isoladamente, transforma "o sistema funciona" em "o sistema mede o que afirma medir".

---

## Anexo — Procedência e reprodutibilidade

Cada modelo utilizado está declarado em um registro versionado (`fias-ed-shared/scientific-config/models.json`) com identificador, revisão fixada, licença, métricas quando existem, limitações e referência à fonte.

O sistema recusa-se a executar com modelo que o registro não declare — **e também com modelo que o registro declare sem ter adotado**. A distinção importa: alguns pesos constam do registro apenas para preservar a procedência de uma medição publicada, e não por terem sido validados para uso. É o caso dos dois tamanhos menores de modelo de transcrição que aparecem na tabela da seção 5.2. A autorização de uso é uma lista de estados explicitamente permitidos, de modo que um estado novo entra recusado por padrão, e não adotado por omissão.

As fontes científicas — documentação dos experimentos e pesos treinados — são conferidas por instantâneo criptográfico a cada verificação, de modo que alteração silenciosa é detectável.

As referências de licença dos componentes de terceiros, incluindo as atribuições exigidas pelas licenças Creative Commons, estão em `THIRD_PARTY_LICENSES.md`, na raiz do repositório.

---

*Documento gerado a partir do registro de execução da etapa W2 e do registro científico versionado do projeto. Os números apresentados correspondem a execuções reais, com as saídas preservadas no histórico do repositório.*
