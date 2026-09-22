# Registro de modelos

Este documento explica como o registro de modelos (`scientific-config/models.json`)
funciona, para quem precisa localizar, conferir ou trocar um artefato de
modelo do FIAS-ED. Para a análise científica de por que o BERTimbau foi
escolhido, ver `ANALISE_MODELOS_EXISTENTES.md`.

## Como o registro funciona

Os pesos de modelo **não ficam versionados no Git**. `models.json` referencia
cada artefato por um caminho relativo a `FIAS_ED_EXPERIMENTS_DIR`
(`scientific-config/models.json.base_dir_env`) mais um SHA-256 e um tamanho em
bytes. Por padrão, `FIAS_ED_EXPERIMENTS_DIR` aponta para
`artigos selecionados/experimentos/` (`fias_ed_engine.paths.experiments_dir()`),
mas pode ser sobrescrita por variável de ambiente — por exemplo, se os
artefatos forem copiados para outra máquina.

## Tabela dos artefatos registrados

| model_id | Papel | Caminho relativo | SHA-256 | Tamanho |
|---|---|---|---|---|
| `fias-bertimbau-ptbr-frente3` | weights | `resultados_bert_ptbr/frente3_ptbr/melhor_modelo/model.safetensors` | `625d32a2c0d7c26fe4c44d98f63d05e3be409b2d0504247b086ff47862942ded` | 435.746.832 B |
| `fias-bertimbau-ptbr-frente3` | tokenizer | `resultados_bert_ptbr/frente3_ptbr/melhor_modelo/tokenizer.json` | `b22b95acf8d863293658d68a3996f22ee077bc792415c976e632049e1e399466` | 678.055 B |
| `fias-bertimbau-ptbr-frente3` | tokenizer_config | `resultados_bert_ptbr/frente3_ptbr/melhor_modelo/tokenizer_config.json` | `a350de5ef4f35840047a6ecbbdb93380cc424fc9cde8ecf6306c34071da1378d` | 395 B |
| `fias-bertimbau-ptbr-frente3` | config | `resultados_bert_ptbr/frente3_ptbr/melhor_modelo/config.json` | `e43872df3352131d301742c0331c1385ca3ae11d725ce3cc9a7bd7815a8e5279` | 1.433 B |
| `fias-bertimbau-ptbr-frente3-onnx-int8` | weights | `mobile_deploy/bertimbau/model_int8.onnx` | `cdeb8ccb2dc7c9bdfc643ad1ff3fb66a76901b270f57a4e08aef2458399abcd4` | 109.688.107 B |

Cada entrada em `models.json` também registra `metrics` (F1 macro, accuracy,
kappa, MCC, e os benchmarks de latência/RAM), `license` (pesos e dados de
treino), `limitations` (viés de seleção no teste, domain shift) e
`forbidden_files` (pickles que não devem ser carregados). Ver
`ANALISE_MODELOS_EXISTENTES.md` para o detalhamento científico de cada campo.

## `verify_models.py`

`scripts/verify_models.py [caminho/models.json]` percorre `models.json`,
resolve cada `relative_path` sob `experiments_dir()` e confere tamanho em
bytes e SHA-256. Uso:

```
engine-py/.venv/Scripts/python scripts/verify_models.py
```

Saída: uma linha `ERRO: ...` por artefato ausente ou divergente, e
`OK — todos os modelos conferem` (código de saída 0) ou `N erro(s)` (código
de saída 1) ao final. É a forma recomendada de confirmar, antes de qualquer
execução, que os artefatos apontados em `models.json` ainda existem e não
foram alterados desde o registro.

## Política de modelos

- **Não baixar modelos silenciosamente.** Todo artefato precisa estar
  presente localmente e ser referenciado por caminho + hash; não há download
  automático embutido no motor de referência.
- **Não carregar arquivos pickle** (`*.bin` de `training_args`, `*.pt`,
  `*.pth`, `*.pkl`, `*.joblib`). Ver a lista de `forbidden_files` por modelo
  em `models.json` e a seção correspondente em `ANALISE_MODELOS_EXISTENTES.md`.
- **Preferir formatos seguros de serialização**: `safetensors` para pesos de
  treino (Web) e `onnx` para inferência embarcada (Android). Nenhum modelo do
  registro atual usa `ggml`.
- Nenhum artefato de modelo é copiado para dentro deste repositório Git —
  apenas caminho + hash.

## ASR e diarização (reservado)

Nenhum modelo de ASR ou diarização é nomeado nas fontes da dissertação (ver
`RESEARCH_INVENTORY.md` §7). A escolha e o registro de modelos de ASR e de
diarização ficam a cargo dos subprojetos 2 (pipeline Web) e 3 (app Android),
cujos documentos (`PIPELINE.md`, `ANDROID_DIARIZATION_FEASIBILITY.md`,
`ANDROID_BENCHMARK.md`) tratam dessa escolha em seus próprios specs. Este
registro (`models.json`) está preparado para receber entradas de ASR/diarização
no mesmo formato (`model_id`, `artifacts[]` com `sha256`/`size_bytes`,
`metrics`, `license`, `limitations`) quando esses subprojetos as definirem.
