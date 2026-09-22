# FIAS-ED

**Grave sua aula. Melhore sua prática docente.**

FIAS-ED é um sistema de apoio à prática docente para professores da educação
básica. O professor grava o áudio de uma aula; o sistema transcreve, diariza
os falantes, classifica a interação turno a turno pelo **FIAS** (Flanders
Interaction Analysis System) e cruza esse resultado com respostas de alunos
ao **QTI-24** (Questionnaire on Teacher Interaction). Os dois retratos —
o que aconteceu na aula e como os alunos percebem a relação com o professor —
são triangulados e interpretados segundo dimensões descritivas do **MTSS
Tier 1**, gerando um relatório com sugestões pedagógicas em linguagem de
apoio ("Considere…", "Você pode experimentar…"), nunca de julgamento.

Este projeto é a base de uma dissertação de mestrado (PPGCC UFERSA/UERN) e
segue um protocolo estrito de rastreabilidade científica: toda regra, índice
ou parâmetro tem uma fonte citada e um status de validação explícito (ver
`fias-ed-shared/docs/SCIENTIFIC_TRACEABILITY.md`).

## Os três subprojetos

O FIAS-ED é um monorepo dividido em três subprojetos, cada um com sua
própria especificação, plano e implementação, nesta ordem de dependência:

| Subprojeto | O que é | Estado |
|---|---|---|
| [`fias-ed-shared/`](fias-ed-shared/) | Base científica: regras declarativas (JSON), schemas, motor de referência em Python, vetores de conformidade, design tokens e documentação | **Concluído** |
| `fias-ed-web/` | FastAPI + PostgreSQL + pipeline de áudio (ASR, diarização) + React, para uso em PC local do pesquisador (Docker Compose, sem exposição à internet) | Próximo |
| `fias-ed-android/` | App Kotlin/Compose offline-first, com motor de inferência local (ONNX) reutilizando as regras e schemas do `shared` | Próximo |

A ideia central do `shared` é que **Web e Android produzam exatamente os
mesmos resultados a partir das mesmas entradas**: as regras científicas
vivem uma única vez, em JSON versionado, e cada motor (Python no Web,
Kotlin no Android) é validado contra o mesmo conjunto de casos de
conformidade. Detalhes da arquitetura em [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Fontes científicas e modelos (somente leitura)

O repositório **nunca** contém dados sensíveis de pesquisa, pesos de modelo
nem cópias de sistemas de terceiros. Duas árvores fora deste monorepo são
usadas como fonte e nunca são modificadas por nenhum subprojeto:

- `Documents\mestrado\artigos selecionados\` — textos da dissertação
  (CAP4, CAP5, lista de símbolos), experimentos e modelos treinados
  (`experimentos\resultados_bert_ptbr\...`, `experimentos\mobile_deploy\...`).
- `Documents\mestrado\Adaptação para o Português Brasileiro do Questionário
  sobre a Interação do Professor (QTI)\` — material de adaptação do QTI.

Os artefatos de modelo (`*.safetensors`, `*.onnx`, `config.json`,
`tokenizer*.json`) são referenciados por caminho e hash SHA-256 em
[`fias-ed-shared/scientific-config/models.json`](fias-ed-shared/scientific-config/models.json)
e conferidos por `scripts/verify_models.py`. Arquivos pickle
(`*.pt`, `*.pth`, `training_args.bin`) nunca são carregados. A fonte do
QTI-24 é o sistema `avalie-seu-professor` (arquivos TypeScript congelados,
extraídos por `scripts/extract_qti.py`, nunca editados à mão).

## Como rodar os testes do `shared`

```bash
cd fias-ed-shared/engine-py
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,tools]"
.venv/Scripts/python -m pytest
```

Verificações adicionais (rodar de `fias-ed-shared/`, veja
[`fias-ed-shared/README.md`](fias-ed-shared/README.md) para o passo a passo
completo, incluindo o procedimento para alterar uma regra):

```bash
engine-py/.venv/Scripts/python scripts/verify_models.py
engine-py/.venv/Scripts/python scripts/extract_qti.py --check
engine-py/.venv/Scripts/python scripts/build_tokens.py
```

## Documentação

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — visão geral dos três subprojetos, fluxos, decisões e futuro.
- Especificação do `shared`: [`docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md`](docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md).
- Plano de implementação do `shared`: [`docs/superpowers/plans/2026-09-21-fias-ed-shared.md`](docs/superpowers/plans/2026-09-21-fias-ed-shared.md).
- Documentação científica e de produto do `shared`: [`fias-ed-shared/docs/`](fias-ed-shared/docs/) (inventário de pesquisa, análise dos modelos, FIAS, QTI, MTSS, rastreabilidade, reprodutibilidade, modelo de dados, dicionário de entidades, privacidade, design system, referências de interface, sincronização futura).

Especificações e planos dos subprojetos `web` e `android` ainda não
existem — serão criados quando cada um for iniciado, seguindo o mesmo
protocolo (spec → plano → implementação).
