# Análise dos modelos existentes

Este documento analisa os artefatos de modelo já treinados nos experimentos
da dissertação (`artigos selecionados/experimentos/`), explica a escolha do
modelo usado pelo FIAS-ED e registra as decisões de engenharia derivadas
dessa análise. Fonte primária: `experimentos/DOCUMENTACAO_EXPERIMENTOS.md`
(§1–7) e os `resultados.json`/`info_exportacao.json` de cada frente. Nenhum
modelo é retreinado neste subprojeto; os artefatos permanecem em
`experimentos/` e são apenas referenciados por caminho + SHA-256 (ver
`MODELS.md`).

## 1. Inventário de artefatos por frente

| Frente | Modelo | Dataset | Classes | F1 macro | Acc | Kappa | Plataforma |
|---|---|---|---|---|---|---|---|
| 1 (baseline EN) | bert-base-uncased | TalkMoves | 7 | 0,7666 | 0,8725 | 0,7506 | — (referência) |
| 1 (baseline EN) | electra-small | TalkMoves | 7 | 0,7606 | 0,8676 | 0,7397 | — (referência) |
| 2 (FIAS EN) | bert-base-uncased | TalkMoves-FIAS | 10 | 0,8544 | 0,8701 | 0,8306 | — (referência) |
| 2 (FIAS EN) | electra-small | TalkMoves-FIAS | 10 | 0,8437 | 0,8676 | 0,8278 | — (referência) |
| 3 (FIAS PT-BR) | **BERTimbau base** | TalkMoves-FIAS-PTBR | 10 | **0,7246** | 0,8231 | 0,7698 | Web (escolhido) |
| SLM LoRA 30k | llama3.2-1b | TalkMoves-FIAS-PTBR | 10 | 0,6500 | 0,8032 | 0,7400 | Android (avaliado) |
| SLM LoRA 100k | llama3.2-1b | TalkMoves-FIAS-PTBR | 10 | 0,7190 | 0,8225 | 0,7693 | Android (avaliado) |
| SLM LoRA 100k | gemma3-270m | TalkMoves-FIAS-PTBR | 10 | 0,7175 | 0,8195 | 0,7630 | Android (avaliado) |
| SLM prompting (zero-shot) | gemma3:1b (melhor da abordagem) | TalkMoves-FIAS-PTBR | 10 | 0,1777 | 0,2481 | 0,1830 | — (inviável) |
| ONNX mobile | BERTimbau int8 dinâmico | — | 10 | — | 0,78 (PC) / 0,7773–0,7915 (A06) | — | Android (exportado, escolhido) |

Fonte: `experimentos/DOCUMENTACAO_EXPERIMENTOS.md` §2.1, §3.2, §3.3, §4.

## 2. Modelo escolhido: BERTimbau PT-BR (Frente 3)

Artefatos em `resultados_bert_ptbr/frente3_ptbr/melhor_modelo/`:

| Arquivo | Tamanho |
|---|---|
| config.json | 1.433 B |
| model.safetensors | 435.746.832 B |
| tokenizer.json | 678.055 B |
| tokenizer_config.json | 395 B |
| training_args.bin (pickle — **nunca aberto**) | 4.920 B |

Base: `neuralmind/bert-base-portuguese-cased`. Config:
`BertForSequenceClassification`, 12 camadas, hidden 768, 12 cabeças,
`num_labels=10`, vocab 29.794, `max_position_embeddings=512`,
`type_vocab_size=2`, `problem_type="single_label_classification"`,
`transformers 5.8.1`. `safetensors`: 201 tensores F32; `classifier.weight`
shape `[10, 768]`; pooler presente.

### 2.1 Por que BERTimbau (teste de campo A06)

O teste de campo no Samsung Galaxy A06 (4 GB, ~R$ 700; Termux + onnxruntime,
211 turnos pré-tokenizados) mostrou latência de 713,4 ms/turno em média (p95
851,7 ms), pico de RAM de 182 MB e accuracy 0,7773 — "aprovado com folga em
todos os critérios": diagnostica uma aula de 500 turnos em 5,9 min, offline,
rodando até em aparelhos de 2 GB. Em contraste, gemma3-270m levou 1,9 s/turno
(15,9 min/aula, uso em lote) e llama3.2-1b levou 30,4 s/turno (4,2 h/aula,
inviável na prática), apesar de accuracy comparável (0,74–0,78 nos três).
Conclusão registrada em `DOCUMENTACAO_EXPERIMENTOS.md` §3.5: "pagar mais
computação não comprou qualidade" — o encoder (BERTimbau) é a arquitetura de
implantação escolhida para o contexto de restrições tecnológicas do FIAS-ED.

### 2.2 `id2label` e mapa de rótulos

`config.json` grava apenas `LABEL_0..LABEL_9` — **os nomes das categorias
FIAS não ficam gravados no checkpoint**. O mapa índice→FIAS foi reconstruído a
partir de `build_label_info` em
`experimentos/scripts/experimento_fias_ed_bert_ptbr.py` e verificado contra
100% do TSV de teste: **categoria FIAS = argmax(logits) + 1**. `fias_rules.json`
grava esse deslocamento em `classifier.logit_index_offset = 1`.

### 2.3 Tokenizer

WordPiece cased (`BertNormalizer`, `lowercase=false`, acentos preservados).
Tokens especiais: `[PAD]=0`, `[UNK]=100`, `[CLS]=101`, `[SEP]=102`,
`[MASK]=103`. `max_length=256`, truncation `LongestFirst` à direita, padding
`"max_length"` (sempre 256). Sem pré-processamento extra: sem lowercasing,
sem prefixo de identificação de falante no texto.

### 2.4 Formato de entrada: par de turnos

Entrada = par: `tokenizer(text_a, text_b)` → `[CLS] text_a [SEP] text_b
[SEP]`, onde `text_b` é o turno atual (o que está sendo classificado) e
`text_a` é o turno anterior (contexto). Para o professor (categorias 1–7),
`text_a` está vazio em 27–91% das linhas, variando por categoria; para o
aluno (8–9), `text_a` está sempre preenchido; para a categoria 10 (silêncio),
`text_b` está vazio em 100% das linhas. A coluna `tipo_turno` (papel do
falante) **não entra como feature do modelo** — o papel só é usado depois,
na restrição por papel (ver `FIAS.md` §"Restrição por papel"). Não há
ponderação de classes (`class weighting`) no treino.

### 2.5 Discrepância de `token_type_ids`

O treino nunca passa `token_type_ids` explicitamente — todos os valores
usados no treino são zero. Já o script de exportação
(`exportar_onnx_mobile.py`) grava os segmentos reais do tokenizer (1 no
segmento B) para o pacote de benchmark. Uma reanálise com onnxruntime nas
mesmas 211 amostras do benchmark comparou as duas convenções:

| `token_type_ids` | Accuracy | Confiança média |
|---|---|---|
| segmentos do tokenizer (= o que o pacote do celular usava) | 0,7773 | 0,896 |
| **zeros (fiel ao treino)** | **0,7915** | **0,914** |

**Decisão**: usar `token_type_ids` = zeros, por ser fiel ao que o modelo
efetivamente aprendeu no treino e por apresentar accuracy e confiança
melhores nesta reanálise. `fias_rules.json.classifier.token_type_ids =
"zeros"`, `validation_status: engineering_decision`.

### 2.6 Padding fixo

Logits com e sem padding para 256 diferem em até 0,156 no modelo int8 —
padding não é neutro sob quantização dinâmica. Por isso o `fias_ed_engine`
fixa `max_length=256` com padding `"max_length"` sempre, para reproduzir as
métricas medidas.

### 2.7 Exportação ONNX (`mobile_deploy/bertimbau/model_int8.onnx`)

109.688.107 B (o fp32 de 435,9 MB foi apagado após a exportação, registrado
em `info_exportacao.json`). Gerado com `optimum.main_export(task=
"text-classification", opset=17)` seguido de `quantize_dynamic(QInt8)`.

- Entradas: `input_ids`, `attention_mask`, `token_type_ids`, todos
  `int64[batch, seq]`.
- Saída: `logits`, `float32[batch, 10]`.
- **Softmax fica fora do grafo** — os scripts de referência só usam
  `argmax` sobre os logits; a confiança (softmax) é calculada depois, no
  `fias_ed_engine.classifier`.

`benchmark_inputs.json` documenta o pacote de benchmark: `{descricao, n=211,
max_seq=256, amostras: [{input_ids, attention_mask, token_type_ids, label
0–9, fias_cat 1–10}]}`, amostragem estratificada com seed 42, no mínimo 5
amostras por categoria, pré-tokenizado.

## 3. Hiperparâmetros de treino

Batch 16, learning rate 2e-5, 10 épocas, `max_seq_length=256`, warmup 1000
steps, weight decay 0,01, precisão fp16, seed 42. Hardware: GPU NVIDIA RTX
3050 (4 GB). Split: 186.955 turnos de treino / 32.869 de teste
(`mapeamento_meta.json`).

**Seleção do melhor checkpoint no próprio conjunto de teste**
(`eval_dataset=test_dataset`, seleção por F1 macro): não houve um conjunto de
validação separado do teste. Isso significa que as métricas relatadas têm um
viés otimista — o checkpoint foi escolhido pelo mesmo conjunto em que foi
avaliado. Essa ressalva deve acompanhar qualquer divulgação das métricas.

## 4. Métricas do teste completo (n = 32.869)

F1 macro 0,7246; accuracy 0,8231; kappa de Cohen 0,7698; MCC 0,77.

F1 por categoria:

| Cat. | Nome | n | F1 |
|---|---|---|---|
| 1 | Aceita sentimentos | 46 | 0,439 |
| 2 | Elogia ou encoraja | 767 | 0,843 |
| 3 | Aceita ou usa ideias | 1.174 | 0,566 |
| 4 | Faz perguntas | 6.428 | 0,785 |
| 5 | Expõe | 12.704 | 0,839 |
| 6 | Dá instruções | 1.920 | 0,689 |
| 7 | Critica ou justifica autoridade | 211 | 0,578 |
| 8 | Resposta do aluno | 4.205 | 0,795 |
| 9 | Iniciativa do aluno | 414 | 0,715 |
| 10 | Silêncio ou confusão | 5.000 | 0,997 |

Confusões principais: categorias 4↔5 (971/804 casos), categoria 8→3 (405),
categoria 8→5 (396) — coerente com a fronteira conceitual difusa entre
"perguntar" e "expor" (4/5) e entre "responder" e "usar ideias do aluno"
(8/3), como também observado nos runs estendidos dos SLMs
(`DOCUMENTACAO_EXPERIMENTOS.md` §3.3: "Cat3 (F1 ~0,51 em ambos) reflete a
fronteira difusa com Cat4/Cat5").

## 5. Métricas em produção

| Ambiente | Latência média | p95 | Accuracy | Pico RAM |
|---|---|---|---|---|
| PC, CPU int8 (n=100) | 47,7 ms | 54,1 ms | 0,78 | — |
| Galaxy A06 4 GB, Termux+onnxruntime (n=211) | 713,4 ms | 851,7 ms | 0,7773 (tokenizer com segmentos) / 0,7915 (zeros) | 182 MB |

Carga do modelo no A06: 1,71 s. Débito: cerca de 1,4 turnos/s, ~5,9 min para
500 turnos.

## 6. Licenças

- TalkMoves (dataset de origem, antes da tradução): `CC BY-NC-SA 4.0`
  (`TalkMoves-main/LICENSE`) — o dataset PT-BR derivado e, discutivelmente, o
  modelo BERTimbau fine-tuned sobre ele, herdam a restrição não comercial
  (`NC-SA`).
- BERTimbau base: MIT (model card no Hugging Face — licença não verificada
  diretamente em disco neste inventário).
- Tradução do dataset feita com o modelo Mistral (Mistral Small); os termos
  de uso da API devem ser conferidos separadamente pelo pesquisador.

## 7. Arquivos pickle proibidos

`training_args.bin` (nos artefatos do melhor modelo) e, nos checkpoints
intermediários (`checkpoints/*/`), `optimizer.pt`, `rng_state.pth`,
`scaler.pt`, `scheduler.pt`, `training_args.bin` são arquivos pickle do
PyTorch — **nunca devem ser carregados nem distribuídos** (regra de
segurança dos global-constraints do projeto). Nenhum `.pkl`/`.joblib` foi
gerado por este projeto. `scripts/.env` (chaves de API dos experimentos)
também não deve ser versionado.

## 8. Riscos de domain shift

O corpus de origem (TalkMoves) é composto por aulas de matemática K-12 dos
Estados Unidos, traduzidas por LLM para PT-BR; os rótulos FIAS foram
derivados do esquema de talk moves por mapeamento conceitual e heurísticas
textuais, não por recodificação humana FIAS de aulas reais. Isso representa
um risco de deslocamento de domínio (domain shift) ao aplicar o modelo a
aulas brasileiras reais, de qualquer disciplina, gravadas em sala de aula.

## 9. Recomendação

**Não treinar um novo modelo antes de avaliar as métricas do BERTimbau
atual em aulas brasileiras reais.** O F1 macro de 0,7246 já supera a meta de
referência (F1 ≥ 0,65, valor relatado por Foster 2024 na tabela comparativa
de CAP4, não uma meta formal do FIAS-ED — ver `RESEARCH_INVENTORY.md` §8), e
o teste de campo no Galaxy A06 confirma viabilidade de implantação offline.
O próximo passo de validação científica é medir a métrica em dados de sala
de aula reais coletados pelo próprio estudo, não retreinar com mais dados
sintéticos/traduzidos.
