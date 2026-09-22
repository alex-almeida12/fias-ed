# fias-ed-shared

Base científica, regras, schemas, motor de referência, design tokens e
documentação compartilhados pelos subprojetos `fias-ed-web` e
`fias-ed-android`. Visão geral do FIAS-ED e dos três subprojetos: veja o
[`README.md`](../README.md) e o [`ARCHITECTURE.md`](../ARCHITECTURE.md) na
raiz do repositório. Especificação completa:
[`docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md`](../docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md).

## Estrutura da pasta

```
fias-ed-shared/
├── rules/                  regras científicas versionadas (rules_version)
│   ├── fias_rules.json         categorias, mapeamento do classificador, índices
│   ├── qti_config.json         gerado por scripts/extract_qti.py — nunca editar à mão
│   ├── mtss_rules.json         regras descritivas do Tier 1
│   └── pedagogical_rules.json  textos de sugestão ligados às regras do Tier 1
├── schemas/                 JSON Schema (draft 2020-12)
│   ├── rules/*.schema.json     um por arquivo de regras
│   ├── entities/*.schema.json  20 entidades do modelo lógico de dados
│   └── export/*.schema.json    schema do dataset exportável de aulas
├── conformance/              casos entrada → saída esperada (cases/), README com o formato
├── scientific-config/
│   ├── models.json             registro dos modelos (caminho, SHA-256, licença, métricas)
│   └── metric_targets.json     metas de métricas (WER, DER, κ, F1…) com fonte
├── design-tokens/
│   ├── tokens.json              fonte única da paleta/tipografia
│   ├── fonts/                   Ubuntu e Rokkitt empacotadas localmente
│   └── build/                   tokens.css e FiasTokens.kt (gerados, versionados)
├── engine-py/                pacote fias_ed_engine (motor de referência em Python)
├── scripts/                  extração do QTI, geração de tokens, verificação de hashes/modelos
└── docs/                     documentação científica e de produto (ver lista abaixo)
```

Documentação em `docs/`: `RESEARCH_INVENTORY.md`, `ANALISE_MODELOS_EXISTENTES.md`,
`MODELS.md`, `FIAS.md`, `QTI.md`, `MTSS.md`, `SCIENTIFIC_TRACEABILITY.md`,
`SCIENTIFIC_REPRODUCIBILITY.md`, `DATABASE_MODEL.md`, `ENTITY_DICTIONARY.md`,
`PRIVACY.md`, `DESIGN_SYSTEM.md`, `UI_REFERENCES.md`, `FUTURE_SYNC.md`,
`FUTURE_SYNC_API.md`.

## Comandos

Instalar o ambiente e rodar a suíte de testes do motor de referência:

```bash
cd fias-ed-shared/engine-py
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,tools]"
.venv/Scripts/python -m pytest
```

Verificações adicionais, rodadas a partir de `fias-ed-shared/` (não de
`engine-py/`):

```bash
cd ..
engine-py/.venv/Scripts/python scripts/verify_models.py
engine-py/.venv/Scripts/python scripts/extract_qti.py --check
engine-py/.venv/Scripts/python scripts/build_tokens.py
```

- `verify_models.py` confere o SHA-256 de cada artefato de modelo listado
  em `scientific-config/models.json` contra os arquivos em `experimentos\`
  (fora deste repositório, nunca copiados nem carregados como pickle).
- `extract_qti.py --check` confirma, sem escrever nada, que
  `rules/qti_config.json` continua idêntico ao que seria gerado a partir da
  fonte congelada (`avalie-seu-professor`); retorna código de saída 1 e
  imprime "DIVERGENTE — rode extract_qti.py" se algo mudou.
- `build_tokens.py` gera `design-tokens/build/tokens.css` e `FiasTokens.kt`
  a partir de `design-tokens/tokens.json`, falhando se algum par de cor
  declarado como texto ficar abaixo do contraste mínimo (WCAG AA).

Para conferir que nenhuma fonte externa somente-leitura foi alterada, use
`scripts/source_snapshot.py` (grava e depois compara um snapshot de hashes
das árvores `artigos selecionados\` e do QTI):

```bash
engine-py/.venv/Scripts/python scripts/source_snapshot.py verify "<caminho-do-snapshot>.json"
```

## Como mudar uma regra

As regras científicas nunca são editadas "no motor" — sempre no JSON de
`rules/`, seguindo este procedimento:

1. **Editar o JSON** correspondente em `rules/` (ex.: `fias_rules.json`,
   `mtss_rules.json`, `pedagogical_rules.json`). Toda regra, índice ou
   parâmetro alterado precisa manter (ou atualizar) `source_reference` e
   `validation_status`.
2. **Subir o `rules_version`** (semver) do arquivo alterado.
3. Se a mudança afeta o QTI: a edição acontece no sistema
   `avalie-seu-professor` (fonte canônica, fora deste repositório) e depois
   se roda `engine-py/.venv/Scripts/python scripts/extract_qti.py` para
   regenerar `rules/qti_config.json` — ele nunca é editado à mão.
4. **Rodar `scripts/generate_conformance.py`** para regenerar os casos de
   `conformance/cases/` afetados pela mudança (`engine-py/.venv/Scripts/python
   scripts/generate_conformance.py`, a partir de `fias-ed-shared/`).
5. **Revisar o diff** dos casos de conformidade gerados: cada valor novo ou
   alterado precisa fazer sentido para a regra mudada; um diff inesperado
   em outro caso é sinal de efeito colateral não previsto.
6. **Rodar `pytest`** (`cd engine-py && .venv/Scripts/python -m pytest`) e
   confirmar que os testes de schema, rastreabilidade, linguagem e
   conformidade continuam passando.
7. **Commitar** o JSON de regras junto com os casos de conformidade
   regenerados e o motor (se algo em `engine-py` também mudou), em um único
   commit que descreva a regra alterada e sua nova versão.
