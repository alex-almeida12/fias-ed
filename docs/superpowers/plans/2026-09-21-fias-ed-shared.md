# fias-ed-shared Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a base compartilhada do FIAS-ED: regras científicas versionadas e rastreáveis (FIAS, QTI-24, triangulação, MTSS Tier 1, sugestões), JSON Schemas, motor de referência em Python, vetores de conformidade, registro de modelos, design tokens e documentação.

**Architecture:** Regras declarativas em JSON validadas por JSON Schema; um pacote Python puro (`fias_ed_engine`, sem torch) implementa os cálculos; casos em `conformance/` (entrada → saída esperada) são a fonte da verdade que o motor Kotlin do Android também executará. QTI-24 é extraído por script do sistema `avalie-seu-professor` (textos congelados). Modelos permanecem em `experimentos\` e são referenciados por SHA-256.

**Tech Stack:** Python 3.13 (compatível ≥3.11), `jsonschema` 4.x, `pytest`, `fonttools`+`brotli` (só scripts de fontes). Sem dependências de rede em runtime.

**Spec:** `docs/superpowers/specs/2026-09-21-fias-ed-shared-design.md`

## Global Constraints

- Raiz do repositório: `C:\Users\Alex Almeida\Documents\mestrado\sistemas` (monorepo Git, branch `main`). Todos os caminhos abaixo são relativos a ela.
- **NUNCA** modificar nada em `C:\Users\Alex Almeida\Documents\mestrado\artigos selecionados\` nem em `C:\Users\Alex Almeida\Documents\mestrado\Adaptação para o Português Brasileiro do Questionário sobre a Interação do Professor (QTI)\`. Só leitura.
- **NUNCA** carregar `*.bin`, `*.pt`, `*.pth`, `*.pkl`, `*.joblib` (pickle). Não copiar modelos para o repositório.
- Toda regra/índice/parâmetro científico tem `source_reference` (string não vazia) e `validation_status` ∈ {`validated`, `PENDING_SCIENTIFIC_VALIDATION`, `engineering_decision`, `draft_pending_researcher_review`}.
- Todo arquivo de regras tem `rules_version` = `"1.0.0"`.
- Linguagem de interpretações/sugestões: usar "Considere…", "Você pode experimentar…", "Uma possibilidade é…", "Este padrão pode indicar…". Proibido (regex por palavra inteira, case-insensitive): `errado`, `errada`, `ruim`, `inadequad[oa]`, `nota`, `desempenho`, `fracasso`, `deveria ter`, `conforme`, `não conforme`, `reprovad[oa]`, `avaliação docente`.
- Nunca emitir "conforme/parcialmente conforme/não conforme", notas, semáforos ou rótulos de desempenho.
- Paleta exata: Navy `#2F4156`, Teal `#567C8D`, Sky Blue `#C8D9E6`, Beige `#F5EFEB`, White `#FFFFFF`.
- Fontes: Ubuntu (interface), Rokkitt (editorial), empacotadas localmente.
- Python: usar `py -3.13`. Venv em `fias-ed-shared/engine-py/.venv`. Comandos pytest rodam de `fias-ed-shared/engine-py`.
- Commits terminam com a linha: `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- Abreviações de fonte: CAP4 = `Dissertacao Qualificação/2-textuais/4-artigo-fias-ed.tex`; CAP5 = `.../5-validacao.tex`; SIMB = `.../1-pre-textuais/lista-de-simbolos.tex`; FU = `Formas_de_Uso_Tier1.docx` (todos sob `artigos selecionados\`).

---

## File Structure

```
fias-ed-shared/
├── rules/
│   ├── fias_rules.json            Task 2
│   ├── qti_config.json            Task 5 (gerado)
│   ├── mtss_rules.json            Task 8
│   └── pedagogical_rules.json     Task 8 (sugestões) + Task 9 (pares de triangulação)
├── schemas/
│   ├── rules/fias_rules.schema.json, qti_config.schema.json,
│   │         mtss_rules.schema.json, pedagogical_rules.schema.json
│   └── entities/_base.schema.json + 20 entidades       Task 11
├── scientific-config/models.json, metric_targets.json  Task 3
├── conformance/cases/*.json                            Task 10
├── design-tokens/tokens.json, build/, fonts/           Task 12
├── scripts/
│   ├── source_snapshot.py     Task 1
│   ├── verify_models.py       Task 3
│   ├── extract_qti.py         Task 5
│   ├── build_tokens.py        Task 12
│   └── fetch_fonts.py         Task 12
├── engine-py/
│   ├── pyproject.toml
│   ├── src/fias_ed_engine/
│   │   ├── __init__.py
│   │   ├── paths.py           caminhos do repo e fontes externas
│   │   ├── rules.py           carregar + validar regras (Task 2)
│   │   ├── traceability.py    varredura de metadados (Task 2)
│   │   ├── intervals.py       segmentos → intervalos, matriz (Task 4)
│   │   ├── indices.py         índices FIAS (Task 6)
│   │   ├── classifier.py      softmax + restrição por papel (Task 7)
│   │   ├── qti.py             pontuação + importação CSV (Task 5)
│   │   ├── mtss.py            fatos, avaliação, sugestões, evidências (Task 8)
│   │   ├── language.py        verificação de linguagem (Task 8)
│   │   ├── triangulation.py   pares FIAS×QTI (Task 9)
│   │   └── export.py          dataset da(s) aula(s): JSON e ZIP de CSVs (Task 11B)
│   └── tests/ (um arquivo por módulo + test_conformance.py + test_entities.py + test_tokens.py)
└── docs/ (Tasks 13–14)
README.md, ARCHITECTURE.md na raiz (Task 15)
```

---

### Task 1: Scaffold do pacote e snapshot de integridade das fontes

**Files:**
- Create: `fias-ed-shared/engine-py/pyproject.toml`
- Create: `fias-ed-shared/engine-py/src/fias_ed_engine/__init__.py`
- Create: `fias-ed-shared/engine-py/src/fias_ed_engine/paths.py`
- Create: `fias-ed-shared/scripts/source_snapshot.py`
- Test: `fias-ed-shared/engine-py/tests/test_paths.py`

**Interfaces:**
- Produces: `fias_ed_engine.paths.SHARED_ROOT: Path`, `RULES_DIR`, `SCHEMAS_DIR`, `CONFORMANCE_DIR`, `SCIENTIFIC_CONFIG_DIR`, `DESIGN_TOKENS_DIR`, `experiments_dir() -> Path`, `qti_system_dir() -> Path`. `scripts/source_snapshot.py {create|verify} <out.json>`.

- [ ] **Step 1: Criar pyproject e venv**

`fias-ed-shared/engine-py/pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "fias-ed-engine"
version = "1.0.0"
description = "Motor de referência das regras FIAS-ED (FIAS, QTI-24, triangulação, MTSS Tier 1)"
requires-python = ">=3.11"
dependencies = ["jsonschema>=4.23,<5"]

[project.optional-dependencies]
dev = ["pytest>=8"]
tools = ["fonttools>=4.53", "brotli>=1.1"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Run (em `fias-ed-shared/engine-py`):
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,tools]"
```

- [ ] **Step 2: Teste falhando para paths**

`tests/test_paths.py`:
```python
from fias_ed_engine import paths


def test_shared_root_contains_expected_dirs():
    for d in (paths.RULES_DIR, paths.SCHEMAS_DIR, paths.CONFORMANCE_DIR,
              paths.SCIENTIFIC_CONFIG_DIR, paths.DESIGN_TOKENS_DIR):
        assert d.parent == paths.SHARED_ROOT
    assert paths.SHARED_ROOT.name == "fias-ed-shared"


def test_external_dirs_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("FIAS_ED_EXPERIMENTS_DIR", str(tmp_path))
    monkeypatch.setenv("FIAS_ED_QTI_SYSTEM_DIR", str(tmp_path))
    assert paths.experiments_dir() == tmp_path
    assert paths.qti_system_dir() == tmp_path
```
Run: `.venv/Scripts/python -m pytest tests/test_paths.py -v` → FAIL (`ModuleNotFoundError`/`AttributeError`).

- [ ] **Step 3: Implementar**

`src/fias_ed_engine/__init__.py`:
```python
"""Motor de referência FIAS-ED. Puro Python; sem torch, sem rede."""

__version__ = "1.0.0"
```

`src/fias_ed_engine/paths.py`:
```python
"""Caminhos do repositório e das fontes externas (somente leitura)."""
import os
from pathlib import Path

SHARED_ROOT = Path(__file__).resolve().parents[3]
RULES_DIR = SHARED_ROOT / "rules"
SCHEMAS_DIR = SHARED_ROOT / "schemas"
CONFORMANCE_DIR = SHARED_ROOT / "conformance"
SCIENTIFIC_CONFIG_DIR = SHARED_ROOT / "scientific-config"
DESIGN_TOKENS_DIR = SHARED_ROOT / "design-tokens"

_MESTRADO = SHARED_ROOT.parents[1]
_DEFAULT_EXPERIMENTS = _MESTRADO / "artigos selecionados" / "experimentos"
_DEFAULT_QTI_SYSTEM = (
    _MESTRADO
    / "Adaptação para o Português Brasileiro do Questionário sobre a Interação do Professor (QTI)"
    / "sistema" / "avalie-seu-professor"
)


def experiments_dir() -> Path:
    return Path(os.environ.get("FIAS_ED_EXPERIMENTS_DIR", _DEFAULT_EXPERIMENTS))


def qti_system_dir() -> Path:
    return Path(os.environ.get("FIAS_ED_QTI_SYSTEM_DIR", _DEFAULT_QTI_SYSTEM))
```
(`parents[3]` de `engine-py/src/fias_ed_engine/paths.py` = `fias-ed-shared`; `SHARED_ROOT.parents[1]` = `mestrado`.)

Run: `.venv/Scripts/python -m pytest tests/test_paths.py -v` → PASS.

- [ ] **Step 4: Script de snapshot de integridade**

`fias-ed-shared/scripts/source_snapshot.py` — registra (caminho relativo, tamanho, mtime_ns) de todos os arquivos das duas fontes externas, ignorando `.venv`, `node_modules`, `.next`, `test-results`. Não calcula hash de tudo (≈10 GB); tamanho+mtime detecta qualquer escrita.
```python
"""Snapshot de integridade das fontes externas (somente leitura).

Uso:
  python source_snapshot.py create snapshot.json
  python source_snapshot.py verify snapshot.json   # exit 1 se algo mudou
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.paths import experiments_dir, qti_system_dir  # noqa: E402

IGNORED = {".venv", "node_modules", ".next", "test-results", "__pycache__"}


def scan(root: Path) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for p in root.rglob("*"):
        if any(part in IGNORED for part in p.relative_to(root).parts):
            continue
        if p.is_file():
            st = p.stat()
            out[p.relative_to(root).as_posix()] = [st.st_size, st.st_mtime_ns]
    return out


def snapshot() -> dict:
    return {"experiments": scan(experiments_dir()), "qti_system": scan(qti_system_dir())}


def main() -> int:
    cmd, out = sys.argv[1], Path(sys.argv[2])
    if cmd == "create":
        out.write_text(json.dumps(snapshot()), encoding="utf-8")
        return 0
    old = json.loads(out.read_text(encoding="utf-8"))
    new = snapshot()
    changed = [f"{k}:{f}" for k in old for f in set(old[k]) | set(new[k])
               if old[k].get(f) != new[k].get(f)]
    for c in changed[:50]:
        print("ALTERADO:", c)
    print("OK — nenhuma alteração" if not changed else f"{len(changed)} alterações")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
```

Run (de `fias-ed-shared`):
```bash
engine-py/.venv/Scripts/python scripts/source_snapshot.py create "$TEMP/fias_sources_before.json"
engine-py/.venv/Scripts/python scripts/source_snapshot.py verify "$TEMP/fias_sources_before.json"
```
Expected: `OK — nenhuma alteração`. **Guarde o arquivo; a Task 15 o usa.**

- [ ] **Step 5: Commit**
```bash
git add fias-ed-shared/engine-py fias-ed-shared/scripts/source_snapshot.py
git commit -m "feat(shared): scaffold do motor de referência e snapshot das fontes"
```

---

### Task 2: `fias_rules.json`, schema, carregador e verificação de rastreabilidade

**Files:**
- Create: `fias-ed-shared/rules/fias_rules.json`
- Create: `fias-ed-shared/schemas/rules/common.schema.json`
- Create: `fias-ed-shared/schemas/rules/fias_rules.schema.json`
- Create: `engine-py/src/fias_ed_engine/rules.py`
- Create: `engine-py/src/fias_ed_engine/traceability.py`
- Test: `engine-py/tests/test_rules.py`

**Interfaces:**
- Produces: `rules.load_rules(name: str) -> dict` (name ∈ `fias_rules|qti_config|mtss_rules|pedagogical_rules`; valida contra `schemas/rules/<name>.schema.json`, lança `jsonschema.ValidationError`). `rules.RULE_FILES: tuple[str, ...]`. `traceability.find_untraced(obj) -> list[str]` (caminhos JSON de objetos com `source_reference` ausente/vazio ou `validation_status` inválido, considerando todo dict que tenha qualquer uma das chaves `source_reference`, `validation_status`, `rule_id`, `id` dentro de listas de regras).
- `fias_rules` shape usado adiante: `categories[i] = {id:int, name, group: "teacher"|"student"|"silence", influence: "indirect"|"direct"|null, aliases, source_reference, validation_status}`; `indices[i] = {id, name, kind: "proportion"|"ratio", numerator: list[int]|null, denominator: "all"|list[int]|null, enabled, source_reference, validation_status, notes?}`; `coding.interval_seconds`, `aggregation.gap_category`, `matrix.pad_category`, `classifier.{logit_index_offset, max_length, token_type_ids, padding, uncertain_below, role_categories}`.

- [ ] **Step 1: Escrever `common.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/rules/common.schema.json",
  "$defs": {
    "validation_status": {
      "enum": ["validated", "PENDING_SCIENTIFIC_VALIDATION", "engineering_decision", "draft_pending_researcher_review"]
    },
    "trace": {
      "type": "object",
      "required": ["source_reference", "validation_status"],
      "properties": {
        "source_reference": {"type": "string", "minLength": 3},
        "validation_status": {"$ref": "#/$defs/validation_status"}
      }
    },
    "rules_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "category": {"type": "integer", "minimum": 1, "maximum": 10}
  }
}
```

- [ ] **Step 2: Escrever `fias_rules.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/rules/fias_rules.schema.json",
  "type": "object",
  "required": ["rules_version", "coding", "aggregation", "matrix", "classifier", "categories", "indices"],
  "properties": {
    "rules_version": {"$ref": "common.schema.json#/$defs/rules_version"},
    "coding": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["interval_seconds"], "properties": {"interval_seconds": {"type": "number", "exclusiveMinimum": 0}}}]},
    "aggregation": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["method", "tie_break", "gap_category"],
      "properties": {"method": {"const": "largest_coverage"}, "tie_break": {"const": "earliest_start"},
                     "gap_category": {"$ref": "common.schema.json#/$defs/category"}}}]},
    "matrix": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["pad_category"], "properties": {"pad_category": {"$ref": "common.schema.json#/$defs/category"}}}]},
    "classifier": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["logit_index_offset", "input_format", "max_length", "token_type_ids", "padding", "uncertain_below", "role_categories"],
      "properties": {
        "logit_index_offset": {"const": 1},
        "input_format": {"const": "pair:previous_turn,current_turn"},
        "max_length": {"const": 256},
        "token_type_ids": {"const": "zeros"},
        "padding": {"const": "max_length"},
        "uncertain_below": {"type": "number", "minimum": 0, "maximum": 1},
        "role_categories": {"type": "object", "required": ["PROFESSOR", "ALUNO"],
          "additionalProperties": {"type": "array", "items": {"$ref": "common.schema.json#/$defs/category"}, "minItems": 1}}
      }}]},
    "categories": {"type": "array", "minItems": 10, "maxItems": 10, "items": {"allOf": [
      {"$ref": "common.schema.json#/$defs/trace"},
      {"required": ["id", "name", "group", "influence", "aliases"],
       "properties": {"id": {"$ref": "common.schema.json#/$defs/category"}, "name": {"type": "string"},
         "group": {"enum": ["teacher", "student", "silence"]},
         "influence": {"enum": ["indirect", "direct", null]},
         "aliases": {"type": "array", "items": {"type": "string"}}}}]}},
    "indices": {"type": "array", "items": {"allOf": [
      {"$ref": "common.schema.json#/$defs/trace"},
      {"required": ["id", "name", "kind", "numerator", "denominator", "enabled"],
       "properties": {"id": {"type": "string", "pattern": "^[A-Z_]+$"}, "name": {"type": "string"},
         "kind": {"enum": ["proportion", "ratio"]},
         "numerator": {"oneOf": [{"type": "null"}, {"type": "array", "items": {"$ref": "common.schema.json#/$defs/category"}, "minItems": 1}]},
         "denominator": {"oneOf": [{"type": "null"}, {"const": "all"}, {"type": "array", "items": {"$ref": "common.schema.json#/$defs/category"}, "minItems": 1}]},
         "enabled": {"type": "boolean"}, "notes": {"type": "string"}},
       "if": {"properties": {"enabled": {"const": true}}},
       "then": {"properties": {"numerator": {"type": "array"}, "denominator": {"not": {"type": "null"}}}}}]}}
  }
}
```

- [ ] **Step 3: Escrever `fias_rules.json`**

```json
{
  "rules_version": "1.0.0",
  "coding": {"interval_seconds": 3, "source_reference": "CAP4 l.56 (protocolo de codificação a cada 3 s; Flanders 1970)", "validation_status": "validated"},
  "aggregation": {"method": "largest_coverage", "tie_break": "earliest_start", "gap_category": 10,
    "source_reference": "Spec 2026-09-21 §4.3 — regra turno→intervalo não definida nas fontes (inventário item 11)",
    "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
  "matrix": {"pad_category": 10, "source_reference": "CAP4 l.52 e l.279 (\"Convenciona-se acrescentar 10 no início e no fim da sequência\")", "validation_status": "validated"},
  "classifier": {
    "logit_index_offset": 1,
    "input_format": "pair:previous_turn,current_turn",
    "max_length": 256,
    "token_type_ids": "zeros",
    "padding": "max_length",
    "uncertain_below": 0.5,
    "role_categories": {"PROFESSOR": [1, 2, 3, 4, 5, 6, 7], "ALUNO": [8, 9]},
    "source_reference": "experimentos/scripts/experimento_fias_ed_bert_ptbr.py (build_label_info: idx=cat-1; tokenizer(text_a,text_b), max_seq 256); ANALISE_MODELOS_EXISTENTES.md §token_type_ids; restrição por papel = spec §4.2",
    "validation_status": "engineering_decision"
  },
  "categories": [
    {"id": 1, "name": "Aceita sentimentos", "group": "teacher", "influence": "indirect", "aliases": ["Aceita Sentimentos"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 2, "name": "Elogia ou encoraja", "group": "teacher", "influence": "indirect", "aliases": ["Elogia ou Encoraja"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 3, "name": "Aceita ou usa ideias", "group": "teacher", "influence": "indirect", "aliases": ["Aceita ou Utiliza Ideias dos Alunos", "Aceita/Utiliza Ideias"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 4, "name": "Faz perguntas", "group": "teacher", "influence": "indirect", "aliases": ["Faz Perguntas"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 5, "name": "Expõe", "group": "teacher", "influence": "direct", "aliases": ["Expõe/Explica", "Expõe (lecture)"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 6, "name": "Dá instruções", "group": "teacher", "influence": "direct", "aliases": ["Dá Direções"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 7, "name": "Critica ou justifica autoridade", "group": "teacher", "influence": "direct", "aliases": ["Critica/Autoridade", "Critica ou Justifica Autoridade"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 8, "name": "Resposta do aluno", "group": "student", "influence": null, "aliases": ["Resposta do Aluno"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 9, "name": "Iniciativa do aluno", "group": "student", "influence": null, "aliases": ["Iniciativa do Aluno"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"},
    {"id": 10, "name": "Silêncio ou confusão", "group": "silence", "influence": null, "aliases": ["Silêncio/Confusão", "Silêncio ou Confusão"], "source_reference": "CAP4 tab:art2-categorias-fias l.37-46; grupos CAP4 l.26", "validation_status": "validated"}
  ],
  "indices": [
    {"id": "TT", "name": "Fala docente", "kind": "proportion", "numerator": [1, 2, 3, 4, 5, 6, 7], "denominator": "all", "enabled": true, "source_reference": "SIMB l.4-15; CAP4 l.279 (Flanders 1970)", "validation_status": "validated"},
    {"id": "PT", "name": "Fala discente", "kind": "proportion", "numerator": [8, 9], "denominator": "all", "enabled": true, "source_reference": "SIMB l.4-15; CAP4 l.279 (Flanders 1970)", "validation_status": "validated"},
    {"id": "SC", "name": "Silêncio ou confusão", "kind": "proportion", "numerator": [10], "denominator": "all", "enabled": true, "source_reference": "SIMB l.4-15; CAP4 l.279 (Flanders 1970)", "validation_status": "validated"},
    {"id": "ID_RATIO", "name": "Razão influência indireta/direta (I/D)", "kind": "ratio", "numerator": [1, 2, 3, 4], "denominator": [5, 6, 7], "enabled": true, "source_reference": "SIMB l.4-15 (r_id: cat. 1–4 / cat. 5–7); CAP4 l.279", "validation_status": "validated"},
    {"id": "PIR", "name": "Razão de iniciativa discente", "kind": "ratio", "numerator": [9], "denominator": [8, 9], "enabled": true, "source_reference": "SIMB l.4-15 (PIR: cat. 9 / fala discente)", "validation_status": "validated"},
    {"id": "PUPIL_RESPONSE_RATIO", "name": "Razão de resposta discente", "kind": "ratio", "numerator": [8], "denominator": [8, 9], "enabled": true, "source_reference": "SIMB l.4-15 (definição: cat. 8 / fala discente)", "validation_status": "validated", "notes": "SIMB usa a sigla PTR (Pupil Talk Ratio), que diverge da definição; o id adotado segue a definição. Ver FIAS.md."},
    {"id": "ID_REVISED", "name": "Razão I/D revisada", "kind": "ratio", "numerator": null, "denominator": null, "enabled": false, "source_reference": "CAP4 l.279 (citada, sem fórmula)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "notes": "Fórmula a confirmar em Flanders (1970) pelo pesquisador."},
    {"id": "TRR", "name": "Razão de resposta docente", "kind": "ratio", "numerator": [1, 2, 3], "denominator": null, "enabled": false, "source_reference": "SIMB l.4-15 (denominador 'fala docente reativa' não definido)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "I_A", "name": "Índice de Acolhimento", "kind": "proportion", "numerator": [1, 2, 3], "denominator": null, "enabled": false, "source_reference": "SIMB (apenas lista de símbolos)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "I_E", "name": "Índice de Estímulo ao Raciocínio", "kind": "proportion", "numerator": [4], "denominator": null, "enabled": false, "source_reference": "SIMB (apenas lista de símbolos)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "I_C", "name": "Índice de Controle", "kind": "proportion", "numerator": [5, 6, 7], "denominator": null, "enabled": false, "source_reference": "SIMB (apenas lista de símbolos)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "I_P", "name": "Índice de Protagonismo Discente", "kind": "proportion", "numerator": [8, 9], "denominator": null, "enabled": false, "source_reference": "SIMB (apenas lista de símbolos)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "R_PA", "name": "Razão de fala professor/aluno", "kind": "ratio", "numerator": null, "denominator": null, "enabled": false, "source_reference": "SIMB (sem definição)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"}
  ]
}
```

- [ ] **Step 4: Testes falhando**

`tests/test_rules.py`:
```python
import copy

import jsonschema
import pytest

from fias_ed_engine.rules import load_rules
from fias_ed_engine.traceability import find_untraced


def test_fias_rules_valid_and_versioned():
    r = load_rules("fias_rules")
    assert r["rules_version"] == "1.0.0"
    assert [c["id"] for c in r["categories"]] == list(range(1, 11))


def test_groups_match_cap4():
    r = load_rules("fias_rules")
    by = {c["id"]: c for c in r["categories"]}
    assert {i for i in by if by[i]["influence"] == "indirect"} == {1, 2, 3, 4}
    assert {i for i in by if by[i]["influence"] == "direct"} == {5, 6, 7}
    assert {i for i in by if by[i]["group"] == "student"} == {8, 9}
    assert by[10]["group"] == "silence"


def test_pending_indices_are_disabled():
    r = load_rules("fias_rules")
    for idx in r["indices"]:
        if idx["validation_status"] == "PENDING_SCIENTIFIC_VALIDATION":
            assert idx["enabled"] is False, idx["id"]


def test_enabled_index_requires_formula():
    r = copy.deepcopy(load_rules("fias_rules"))
    bad = next(i for i in r["indices"] if i["id"] == "TRR")
    bad["enabled"] = True
    from fias_ed_engine.rules import validate
    with pytest.raises(jsonschema.ValidationError):
        validate("fias_rules", r)


def test_everything_traced():
    assert find_untraced(load_rules("fias_rules")) == []


def test_find_untraced_detects_missing():
    assert find_untraced({"indices": [{"id": "X", "validation_status": "validated"}]}) == ["$.indices[0]"]
    assert find_untraced({"a": {"source_reference": "ok", "validation_status": "bogus"}}) == ["$.a"]
```
Run: `.venv/Scripts/python -m pytest tests/test_rules.py -v` → FAIL (módulo inexistente).

- [ ] **Step 5: Implementar `rules.py` e `traceability.py`**

`src/fias_ed_engine/rules.py`:
```python
"""Carregamento e validação das regras compartilhadas."""
import json
from functools import lru_cache
from typing import Any

import jsonschema
from referencing import Registry, Resource

from .paths import RULES_DIR, SCHEMAS_DIR

RULE_FILES = ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules")


def _read(path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _registry() -> Registry:
    resources = []
    for p in (SCHEMAS_DIR / "rules").glob("*.schema.json"):
        schema = _read(p)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def validate(name: str, data: Any) -> None:
    schema = _read(SCHEMAS_DIR / "rules" / f"{name}.schema.json")
    jsonschema.Draft202012Validator(schema, registry=_registry()).validate(data)


def load_rules(name: str) -> dict:
    if name not in RULE_FILES:
        raise ValueError(f"Arquivo de regras desconhecido: {name}")
    data = _read(RULES_DIR / f"{name}.json")
    validate(name, data)
    return data
```

`src/fias_ed_engine/traceability.py`:
```python
"""Verifica que todo objeto científico declara fonte e status de validação."""
from typing import Any

STATUSES = {"validated", "PENDING_SCIENTIFIC_VALIDATION",
            "engineering_decision", "draft_pending_researcher_review"}
_MARKERS = ("source_reference", "validation_status", "rule_id")


def _needs_trace(obj: dict, in_list: bool) -> bool:
    return any(k in obj for k in _MARKERS) or (in_list and "id" in obj)


def find_untraced(obj: Any, path: str = "$", in_list: bool = False) -> list[str]:
    bad: list[str] = []
    if isinstance(obj, dict):
        if _needs_trace(obj, in_list):
            ok = (isinstance(obj.get("source_reference"), str)
                  and len(obj["source_reference"].strip()) >= 3
                  and obj.get("validation_status") in STATUSES)
            if not ok:
                bad.append(path)
        for k, v in obj.items():
            bad += find_untraced(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += find_untraced(v, f"{path}[{i}]", in_list=True)
    return bad
```

Run: `.venv/Scripts/python -m pytest tests/test_rules.py -v` → PASS (6 testes).

Nota: os itens do QTI (Task 5) têm `id` dentro de lista mas herdam a rastreabilidade do objeto `instrument`; por isso a Task 5 grava `source_reference`/`validation_status` também em cada item.

- [ ] **Step 6: Commit**
```bash
git add fias-ed-shared/rules/fias_rules.json fias-ed-shared/schemas/rules fias-ed-shared/engine-py
git commit -m "feat(shared): regras FIAS versionadas, schema e verificação de rastreabilidade"
```

---

### Task 3: Registro de modelos e metas de métricas

**Files:**
- Create: `fias-ed-shared/scientific-config/models.json`
- Create: `fias-ed-shared/scientific-config/metric_targets.json`
- Create: `fias-ed-shared/scripts/verify_models.py`
- Test: `engine-py/tests/test_models_registry.py`

**Interfaces:**
- Produces: `models.json` `{registry_version, models:[{model_id, name, task, base_model, platform: "web"|"android", artifacts:[{role, relative_path, sha256, size_bytes}], label_map, metrics, license, limitations, forbidden_files, source_reference, validation_status}]}`. `verify_models.py` → exit 0 se todos os hashes conferem; 1 caso contrário. Função reutilizável `verify(models_path) -> list[str]` (lista de erros).

- [ ] **Step 1: Escrever `models.json`**

```json
{
  "registry_version": "1.0.0",
  "base_dir_env": "FIAS_ED_EXPERIMENTS_DIR",
  "models": [
    {
      "model_id": "fias-bertimbau-ptbr-frente3",
      "name": "BERTimbau base fine-tuned FIAS (Frente 3)",
      "task": "fias_utterance_classification",
      "base_model": "neuralmind/bert-base-portuguese-cased",
      "platform": "web",
      "format": "safetensors",
      "artifacts": [
        {"role": "weights", "relative_path": "resultados_bert_ptbr/frente3_ptbr/melhor_modelo/model.safetensors", "sha256": "625d32a2c0d7c26fe4c44d98f63d05e3be409b2d0504247b086ff47862942ded", "size_bytes": 435746832},
        {"role": "tokenizer", "relative_path": "resultados_bert_ptbr/frente3_ptbr/melhor_modelo/tokenizer.json", "sha256": "b22b95acf8d863293658d68a3996f22ee077bc792415c976e632049e1e399466", "size_bytes": 678055},
        {"role": "tokenizer_config", "relative_path": "resultados_bert_ptbr/frente3_ptbr/melhor_modelo/tokenizer_config.json", "sha256": "a350de5ef4f35840047a6ecbbdb93380cc424fc9cde8ecf6306c34071da1378d", "size_bytes": 395},
        {"role": "config", "relative_path": "resultados_bert_ptbr/frente3_ptbr/melhor_modelo/config.json", "sha256": "e43872df3352131d301742c0331c1385ca3ae11d725ce3cc9a7bd7815a8e5279", "size_bytes": 1433}
      ],
      "label_map": "fias_category = argmax(logits) + 1 (fias_rules.classifier.logit_index_offset)",
      "metrics": {"dataset": "TalkMoves-FIAS-PTBR test (n=32869)", "f1_macro": 0.7246, "accuracy": 0.8231, "cohen_kappa": 0.7698, "mcc": 0.77, "seed": 42, "max_length": 256},
      "license": {"weights_base": "MIT (neuralmind/bert-base-portuguese-cased, model card HF)", "training_data": "CC BY-NC-SA 4.0 (TalkMoves) — uso não comercial"},
      "limitations": [
        "Melhor checkpoint selecionado no próprio conjunto de teste (sem validação separada): métricas levemente otimistas.",
        "Domínio: aulas de matemática K-12 dos EUA traduzidas por LLM (Mistral Small); risco de domain shift em aulas brasileiras reais.",
        "Rótulos FIAS derivados de TalkMoves por mapeamento conceitual + heurísticas (mapeamento_meta.json)."
      ],
      "forbidden_files": ["training_args.bin", "optimizer.pt", "rng_state.pth", "scaler.pt", "scheduler.pt"],
      "source_reference": "experimentos/DOCUMENTACAO_EXPERIMENTOS.md §2; resultados_bert_ptbr/frente3_ptbr/resultados.json",
      "validation_status": "validated"
    },
    {
      "model_id": "fias-bertimbau-ptbr-frente3-onnx-int8",
      "name": "BERTimbau FIAS ONNX int8 dinâmico",
      "task": "fias_utterance_classification",
      "base_model": "neuralmind/bert-base-portuguese-cased",
      "platform": "android",
      "format": "onnx",
      "artifacts": [
        {"role": "weights", "relative_path": "mobile_deploy/bertimbau/model_int8.onnx", "sha256": "cdeb8ccb2dc7c9bdfc643ad1ff3fb66a76901b270f57a4e08aef2458399abcd4", "size_bytes": 109688107}
      ],
      "onnx": {"opset": 17, "inputs": {"input_ids": "int64[batch,seq]", "attention_mask": "int64[batch,seq]", "token_type_ids": "int64[batch,seq]"}, "outputs": {"logits": "float32[batch,10]"}, "softmax_in_graph": false},
      "label_map": "fias_category = argmax(logits) + 1",
      "metrics": {
        "pc_cpu": {"accuracy": 0.78, "latency_ms_mean": 47.7, "n": 100},
        "galaxy_a06": {"accuracy_tokenizer_segments": 0.7773, "latency_ms_mean": 713.4, "latency_ms_p95": 851.7, "peak_ram_mb": 182, "load_s": 1.71, "n": 211},
        "reanalysis_token_type_zeros": {"accuracy": 0.7915, "mean_confidence": 0.914, "n": 211, "note": "mesmas 211 amostras, onnxruntime PC"}
      },
      "license": {"weights_base": "MIT", "training_data": "CC BY-NC-SA 4.0 — uso não comercial"},
      "limitations": ["Tokenização precisa ser reproduzida no app (WordPiece cased, tokenizer.json do modelo web).", "Padding fixo 256 para reproduzir métricas (int8 dinâmico sensível ao padding)."],
      "forbidden_files": [],
      "source_reference": "experimentos/DOCUMENTACAO_EXPERIMENTOS.md §3.4–3.5; mobile_deploy/bertimbau/info_exportacao.json; mobile_deploy/resultados_celular/benchmark_resultado_bertimbau_A06.json",
      "validation_status": "validated"
    }
  ]
}
```

- [ ] **Step 2: Escrever `metric_targets.json`** (todas vindas de CAP5; as marcadas "conforme literatura" sem citação ficam PENDING)

```json
{
  "rules_version": "1.0.0",
  "targets": [
    {"id": "WER", "definition": "(S+D+I)/N", "target": "<= 0.25", "source_reference": "CAP5 sec:val-metricas; tab:val-criterios-sintese (\"conforme literatura\", sem citação)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "DER", "target": "<= 0.25", "source_reference": "CAP5 tab:val-criterios-sintese (sem citação)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "KAPPA_MODEL", "target": ">= 0.60 (esperado 0.65–0.80)", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
    {"id": "KAPPA_HUMAN", "target": ">= 0.70", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "validated"},
    {"id": "F1_AXIS", "target": ">= 0.70", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "validated"},
    {"id": "OCR_ACCURACY", "target": ">= 0.95", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "validated"},
    {"id": "PIPELINE_COMPLETION", "target": ">= 0.90 das aulas", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "validated"},
    {"id": "CLOUD_OFFLINE_DEGRADATION", "target": "<= 10 p.p. de F1", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "validated"},
    {"id": "SUS", "target": ">= 70", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "validated"},
    {"id": "TAM", "target": ">= 4.0", "source_reference": "CAP5 tab:val-criterios-sintese", "validation_status": "validated"}
  ]
}
```

- [ ] **Step 3: Teste falhando**

`tests/test_models_registry.py`:
```python
import hashlib
import json
import sys
from pathlib import Path

import pytest

from fias_ed_engine.paths import SCIENTIFIC_CONFIG_DIR, SHARED_ROOT, experiments_dir
from fias_ed_engine.traceability import find_untraced

sys.path.insert(0, str(SHARED_ROOT / "scripts"))
import verify_models  # noqa: E402

MODELS = SCIENTIFIC_CONFIG_DIR / "models.json"


def test_registry_traced():
    data = json.loads(MODELS.read_text(encoding="utf-8"))
    assert find_untraced(data["models"]) == []
    targets = json.loads((SCIENTIFIC_CONFIG_DIR / "metric_targets.json").read_text(encoding="utf-8"))
    assert find_untraced(targets["targets"]) == []


def test_no_pickle_artifacts_registered():
    data = json.loads(MODELS.read_text(encoding="utf-8"))
    for m in data["models"]:
        for a in m["artifacts"]:
            assert not a["relative_path"].endswith((".bin", ".pt", ".pth", ".pkl", ".joblib"))


def test_verify_detects_mismatch(tmp_path, monkeypatch):
    f = tmp_path / "x" / "w.onnx"
    f.parent.mkdir()
    f.write_bytes(b"abc")
    reg = {"models": [{"model_id": "t", "artifacts": [
        {"role": "weights", "relative_path": "x/w.onnx", "size_bytes": 3,
         "sha256": hashlib.sha256(b"abd").hexdigest()}]}]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setenv("FIAS_ED_EXPERIMENTS_DIR", str(tmp_path))
    errors = verify_models.verify(p)
    assert len(errors) == 1 and "sha256" in errors[0]


@pytest.mark.skipif(not experiments_dir().exists(), reason="experimentos indisponíveis")
def test_real_models_match_registry():
    assert verify_models.verify(MODELS) == []
```
Run: `.venv/Scripts/python -m pytest tests/test_models_registry.py -v` → FAIL (`verify_models` inexistente).

- [ ] **Step 4: Implementar `scripts/verify_models.py`**

```python
"""Confere SHA-256 e tamanho dos modelos registrados. Somente leitura.

Uso: python verify_models.py [caminho/models.json]
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.paths import SCIENTIFIC_CONFIG_DIR, experiments_dir  # noqa: E402


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(models_path: Path) -> list[str]:
    registry = json.loads(Path(models_path).read_text(encoding="utf-8"))
    base = experiments_dir()
    errors: list[str] = []
    for model in registry["models"]:
        for art in model["artifacts"]:
            p = base / art["relative_path"]
            if not p.is_file():
                errors.append(f"{model['model_id']}: ausente {art['relative_path']}")
                continue
            if p.stat().st_size != art["size_bytes"]:
                errors.append(f"{model['model_id']}: tamanho divergente {art['relative_path']}")
            if sha256_of(p) != art["sha256"]:
                errors.append(f"{model['model_id']}: sha256 divergente {art['relative_path']}")
    return errors


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else SCIENTIFIC_CONFIG_DIR / "models.json"
    errs = verify(target)
    for e in errs:
        print("ERRO:", e)
    print("OK — todos os modelos conferem" if not errs else f"{len(errs)} erro(s)")
    sys.exit(1 if errs else 0)
```

Nota: no teste de divergência o tamanho confere (3 bytes) e só o hash diverge, gerando exatamente 1 erro.

Run: `.venv/Scripts/python -m pytest tests/test_models_registry.py -v` → PASS (4 testes; o último lê ~550 MB, leva alguns segundos).

- [ ] **Step 5: Commit**
```bash
git add fias-ed-shared/scientific-config fias-ed-shared/scripts/verify_models.py fias-ed-shared/engine-py/tests/test_models_registry.py
git commit -m "feat(shared): registro de modelos com SHA-256 e metas de métricas"
```

---

### Task 4: Segmentos → intervalos de 3 s e matriz 10×10

**Files:**
- Create: `engine-py/src/fias_ed_engine/intervals.py`
- Test: `engine-py/tests/test_intervals.py`

**Interfaces:**
- Consumes: `load_rules("fias_rules")` (Task 2).
- Produces:
  - `@dataclass(frozen=True) class CodedSegment: start_ms: int; end_ms: int; category: int` (categoria já restrita por papel).
  - `segments_to_intervals(segments: list[CodedSegment], total_ms: int, rules: dict) -> list[int]`
  - `transition_matrix(intervals: list[int], rules: dict) -> list[list[int]]` (10×10; `m[i-1][j-1]` = transições i→j).

- [ ] **Step 1: Testes falhando**

`tests/test_intervals.py`:
```python
import pytest

from fias_ed_engine.intervals import CodedSegment as S, segments_to_intervals, transition_matrix
from fias_ed_engine.rules import load_rules

R = load_rules("fias_rules")


def test_empty_audio_is_all_silence():
    assert segments_to_intervals([], 9000, R) == [10, 10, 10]


def test_partial_last_interval_counts():
    assert len(segments_to_intervals([], 7000, R)) == 3


def test_largest_coverage_wins():
    segs = [S(0, 1000, 5), S(1000, 3000, 4)]
    assert segments_to_intervals(segs, 3000, R) == [4]


def test_tie_goes_to_earliest_start():
    segs = [S(0, 1500, 5), S(1500, 3000, 8)]
    assert segments_to_intervals(segs, 3000, R) == [5]


def test_segment_spanning_intervals():
    segs = [S(500, 7000, 5)]
    assert segments_to_intervals(segs, 9000, R) == [5, 5, 5]


def test_gap_interval_is_silence():
    segs = [S(0, 3000, 4), S(6000, 9000, 8)]
    assert segments_to_intervals(segs, 9000, R) == [4, 10, 8]


def test_invalid_segment_rejected():
    with pytest.raises(ValueError):
        segments_to_intervals([S(3000, 1000, 5)], 9000, R)
    with pytest.raises(ValueError):
        segments_to_intervals([S(0, 1000, 11)], 9000, R)


def test_matrix_pads_with_10():
    m = transition_matrix([4, 8], R)
    assert m[10 - 1][4 - 1] == 1   # 10→4 (padding inicial)
    assert m[4 - 1][8 - 1] == 1    # 4→8
    assert m[8 - 1][10 - 1] == 1   # 8→10 (padding final)
    assert sum(map(sum, m)) == 3


def test_matrix_empty_sequence():
    m = transition_matrix([], R)
    assert m[9][9] == 1 and sum(map(sum, m)) == 1
```
Run: `.venv/Scripts/python -m pytest tests/test_intervals.py -v` → FAIL.

- [ ] **Step 2: Implementar**

`src/fias_ed_engine/intervals.py`:
```python
"""Agregação turno → intervalos de codificação e matriz de transições FIAS."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CodedSegment:
    start_ms: int
    end_ms: int
    category: int


def _check(seg: CodedSegment) -> None:
    if seg.end_ms <= seg.start_ms or seg.start_ms < 0:
        raise ValueError(f"Segmento com tempo inválido: {seg}")
    if not 1 <= seg.category <= 10:
        raise ValueError(f"Categoria FIAS inválida: {seg.category}")


def segments_to_intervals(segments: list[CodedSegment], total_ms: int, rules: dict) -> list[int]:
    step = int(rules["coding"]["interval_seconds"] * 1000)
    gap = rules["aggregation"]["gap_category"]
    for s in segments:
        _check(s)
    ordered = sorted(segments, key=lambda s: s.start_ms)
    out: list[int] = []
    for k in range(math.ceil(total_ms / step)):
        lo, hi = k * step, min((k + 1) * step, total_ms)
        best, best_cov = gap, 0
        for s in ordered:  # ordem de início garante desempate pelo mais antigo
            cov = min(hi, s.end_ms) - max(lo, s.start_ms)
            if cov > best_cov:
                best, best_cov = s.category, cov
        out.append(best)
    return out


def transition_matrix(intervals: list[int], rules: dict) -> list[list[int]]:
    pad = rules["matrix"]["pad_category"]
    seq = [pad, *intervals, pad]
    m = [[0] * 10 for _ in range(10)]
    for a, b in zip(seq, seq[1:]):
        m[a - 1][b - 1] += 1
    return m
```

Run: `.venv/Scripts/python -m pytest tests/test_intervals.py -v` → PASS (9 testes).

- [ ] **Step 3: Commit**
```bash
git add fias-ed-shared/engine-py
git commit -m "feat(shared): intervalos de 3 s e matriz de transições FIAS"
```

---

### Task 5: QTI-24 — extração da fonte congelada, pontuação e importação

**Files:**
- Create: `fias-ed-shared/scripts/extract_qti.py`
- Create: `fias-ed-shared/rules/qti_config.json` (gerado)
- Create: `fias-ed-shared/schemas/rules/qti_config.schema.json`
- Create: `engine-py/src/fias_ed_engine/qti.py`
- Test: `engine-py/tests/test_qti.py`

**Interfaces:**
- Consumes: `load_rules`, `paths.qti_system_dir()`.
- Produces:
  - `qti_config.json`: `{rules_version, instrument:{name, version, stem, likert:{min,max,min_label,max_label}, weights:{a,b}, min_responses, source_reference, validation_status, sources:[{path, sha256}]}, octants:[{code, label_pt_br, label_en, agency_weight, communion_weight, source_reference, validation_status}], items:[{order, id, text_pt_br, octant, source_reference, validation_status}]}`.
  - `qti.score_response(answers: dict[int, int], cfg: dict) -> dict` → `{"octants": {"oc1": float,…}, "agency": float, "communion": float}`; lança `IncompleteResponseError`.
  - `qti.aggregate(responses: list[dict[int,int]], cfg: dict) -> dict` → `{"response_count": int, "displayable": bool, "octants": {...}|None, "agency": float|None, "communion": float|None}`.
  - `qti.parse_export_csv(text: str, cfg: dict) -> list[dict[int,int]]`; lança `QtiImportError` se faltar coluna `q1..q24`, valor fora de 1–5, ou se colunas `oc*/agency/communion` presentes divergirem do recálculo (> 1e-9).

- [ ] **Step 1: Schema**

`schemas/rules/qti_config.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/rules/qti_config.schema.json",
  "type": "object",
  "required": ["rules_version", "instrument", "octants", "items"],
  "properties": {
    "rules_version": {"$ref": "common.schema.json#/$defs/rules_version"},
    "instrument": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["name", "version", "stem", "likert", "weights", "min_responses", "sources"],
      "properties": {
        "likert": {"type": "object", "required": ["min", "max", "min_label", "max_label"],
                   "properties": {"min": {"const": 1}, "max": {"const": 5}}},
        "weights": {"type": "object", "required": ["a", "b"],
                    "properties": {"a": {"const": 0.92388}, "b": {"const": 0.382683}}},
        "min_responses": {"type": "integer", "minimum": 1},
        "sources": {"type": "array", "minItems": 4, "items": {"type": "object", "required": ["path", "sha256"],
                    "properties": {"sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}}}
      }}]},
    "octants": {"type": "array", "minItems": 8, "maxItems": 8, "items": {"allOf": [
      {"$ref": "common.schema.json#/$defs/trace"},
      {"required": ["code", "label_pt_br", "label_en", "agency_weight", "communion_weight"],
       "properties": {"code": {"pattern": "^oc[1-8]$"}}}]}},
    "items": {"type": "array", "minItems": 24, "maxItems": 24, "items": {"allOf": [
      {"$ref": "common.schema.json#/$defs/trace"},
      {"required": ["order", "id", "text_pt_br", "octant"],
       "properties": {"order": {"type": "integer", "minimum": 1, "maximum": 24},
                      "text_pt_br": {"type": "string", "minLength": 3},
                      "octant": {"pattern": "^oc[1-8]$"}}}]}}
  }
}
```

- [ ] **Step 2: Script de extração**

`scripts/extract_qti.py` — lê os arquivos TypeScript **sem executá-los**, por regex, e grava o JSON. Somente leitura na fonte.
```python
"""Gera rules/qti_config.json a partir do sistema avalie-seu-professor (fonte congelada).

Uso: python extract_qti.py [--check]   (--check: falha se o JSON atual divergir do extraído)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.paths import RULES_DIR, qti_system_dir  # noqa: E402

QTI_DIR = Path("src") / "domain" / "qti"
FILES = ["qtiItems.ts", "QtiOctant.ts", "qtiWeights.ts", "likertScale.ts"]
SRC = "avalie-seu-professor/src/domain/qti/"


def _read(name: str) -> str:
    return (qti_system_dir() / QTI_DIR / name).read_text(encoding="utf-8")


def _sha(name: str) -> str:
    return hashlib.sha256((qti_system_dir() / QTI_DIR / name).read_bytes()).hexdigest()


def build() -> dict:
    items_ts, oct_ts, w_ts, lik_ts = (_read(f) for f in FILES)
    a = float(re.search(r"WEIGHT_A\s*=\s*([0-9.]+)", w_ts).group(1))
    b = float(re.search(r"WEIGHT_B\s*=\s*([0-9.]+)", w_ts).group(1))
    sign = {"WEIGHT_A": a, "-WEIGHT_A": -a, "WEIGHT_B": b, "-WEIGHT_B": -b}
    weights = {m[0]: (sign[m[1]], sign[m[2]]) for m in re.findall(
        r"(oc[1-8]):\s*\{\s*agency:\s*(-?WEIGHT_[AB]),\s*communion:\s*(-?WEIGHT_[AB])\s*\}", w_ts)}
    octants = [{
        "code": code, "label_pt_br": pt, "label_en": en,
        "agency_weight": weights[code][0], "communion_weight": weights[code][1],
        "source_reference": SRC + "QtiOctant.ts; qtiWeights.ts (manual VIL-24, jan. 2013)",
        "validation_status": "validated",
    } for code, pt, en in re.findall(
        r'code:\s*"(oc[1-8])",\s*labelPtBr:\s*"([^"]+)",\s*labelEn:\s*"([^"]+)"', oct_ts)]
    items = [{
        "order": int(order), "id": f"qti24-item-{int(order):02d}", "text_pt_br": text, "octant": octant,
        "source_reference": SRC + "qtiItems.ts (textos congelados)",
        "validation_status": "PENDING_SCIENTIFIC_VALIDATION",
    } for order, octant, text in re.findall(r'item\((\d+),\s*"(oc[1-8])",\s*"([^"]+)"\)', items_ts)]
    stem = re.search(r'ITEM_STEM_PT_BR\s*=\s*"([^"]+)"', items_ts).group(1)
    min_label = re.search(r'LIKERT_MIN_LABEL_PT_BR\s*=\s*"([^"]+)"', lik_ts).group(1)
    max_label = re.search(r'LIKERT_MAX_LABEL_PT_BR\s*=\s*"([^"]+)"', lik_ts).group(1)
    if len(items) != 24 or len(octants) != 8 or len(weights) != 8:
        raise SystemExit(f"Extração incompleta: itens={len(items)} octantes={len(octants)}")
    return {
        "rules_version": "1.0.0",
        "instrument": {
            "name": "QTI-24 (Questionnaire on Teacher Interaction) — versão preliminar PT-BR",
            "version": "VIL-24 jan. 2013",
            "stem": stem,
            "likert": {"min": 1, "max": 5, "min_label": min_label, "max_label": max_label},
            "weights": {"a": a, "b": b},
            "min_responses": 10,
            "min_responses_note": "engineering_decision herdada de avalie-seu-professor (MIN_RESPONSES_FOR_PUBLIC_RESULT)",
            "license_note": "Instrumento de Wubbels e colegas (Universidade de Utrecht); uso não comercial; autorização formal pendente.",
            "sources": [{"path": SRC + f, "sha256": _sha(f)} for f in FILES],
            "source_reference": SRC + "* ; README.md §Cálculo do QTI-24 (fiel ao manual VIL-24, jan. 2013)",
            "validation_status": "PENDING_SCIENTIFIC_VALIDATION",
        },
        "octants": octants,
        "items": sorted(items, key=lambda i: i["order"]),
    }


def main() -> int:
    out = RULES_DIR / "qti_config.json"
    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        same = out.exists() and out.read_text(encoding="utf-8") == text
        print("OK — qti_config.json idêntico à fonte" if same else "DIVERGENTE — rode extract_qti.py")
        return 0 if same else 1
    out.write_text(text, encoding="utf-8")
    print(f"Gerado {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run (de `fias-ed-shared`): `engine-py/.venv/Scripts/python scripts/extract_qti.py` → `Gerado …qti_config.json`. Abrir o JSON e conferir: item 1 = "sabe conduzir bem a turma" (oc1); item 24 = "mantém a disciplina com rigor" (oc8); oc5 = "Inseguro"; `sources[0].sha256` = `5d0105f3b1a355be1c4112a1d1f538566a7e380ee46ef78fceef187b2c56bcb6`.

Observação: a regex de `weights` só casa as linhas de `OCTANT_DIMENSION_WEIGHTS` (formato `oc1: { agency: WEIGHT_A, communion: WEIGHT_B }`), que é exatamente o formato atual do arquivo.

- [ ] **Step 3: Testes falhando para pontuação e importação**

`tests/test_qti.py` (valores de referência copiados de `avalie-seu-professor/tests/unit/qtiCalculations.test.ts`):
```python
import math
import subprocess
import sys

import pytest

from fias_ed_engine.paths import SHARED_ROOT, qti_system_dir
from fias_ed_engine.qti import IncompleteResponseError, QtiImportError, aggregate, parse_export_csv, score_response
from fias_ed_engine.rules import load_rules
from fias_ed_engine.traceability import find_untraced

CFG = load_rules("qti_config")
A, B = 0.923880, 0.382683


def all_(v):
    return {i: v for i in range(1, 25)}


def where(orders, v, rest):
    return {i: (v if i in orders else rest) for i in range(1, 25)}


def test_config_shape_and_trace():
    assert len(CFG["items"]) == 24
    assert CFG["items"][0]["text_pt_br"] == "sabe conduzir bem a turma"
    assert {o["code"]: o["label_pt_br"] for o in CFG["octants"]}["oc7"] == "Irritável"
    assert find_untraced(CFG) == []


@pytest.mark.skipif(not qti_system_dir().exists(), reason="sistema QTI indisponível")
def test_config_identical_to_frozen_source():
    r = subprocess.run([sys.executable, str(SHARED_ROOT / "scripts" / "extract_qti.py"), "--check"])
    assert r.returncode == 0


def test_octants_extremes():
    assert all(v == 0 for v in score_response(all_(1), CFG)["octants"].values())
    assert all(v == 1 for v in score_response(all_(5), CFG)["octants"].values())
    assert all(math.isclose(v, 0.5) for v in score_response(all_(3), CFG)["octants"].values())


def test_oc1_mixed():
    ans = all_(1) | {1: 5, 9: 4, 17: 3}
    s = score_response(ans, CFG)
    assert math.isclose(s["octants"]["oc1"], 0.75) and s["octants"]["oc2"] == 0


def test_neutral_profile_dimensions_zero():
    s = score_response(all_(3), CFG)
    assert abs(s["agency"]) < 1e-12 and abs(s["communion"]) < 1e-12


def test_only_oc1():
    s = score_response(where([1, 9, 17], 5, 1), CFG)
    assert math.isclose(s["agency"], B * A, abs_tol=1e-12)
    assert math.isclose(s["communion"], B * B, abs_tol=1e-12)


def test_only_oc6():
    s = score_response(where([6, 14, 22], 5, 1), CFG)
    assert math.isclose(s["agency"], -B * B, abs_tol=1e-12)
    assert math.isclose(s["communion"], -B * A, abs_tol=1e-12)


def test_hand_computed_spss_case():
    lik = {1: 5, 2: 3, 3: 2, 4: 1, 5: 1, 6: 2, 7: 3, 8: 5}
    ans = {i: lik[(i - 1) % 8 + 1] for i in range(1, 25)}
    s = score_response(ans, CFG)
    exp_ag = B * (A * 1 + B * 0.5 - B * 0.25 - A * 0 - A * 0 - B * 0.25 + B * 0.5 + A * 1)
    exp_co = B * (B * 1 + A * 0.5 + A * 0.25 + B * 0 - B * 0 - A * 0.25 - A * 0.5 - B * 1)
    assert math.isclose(s["agency"], exp_ag, abs_tol=1e-12)
    assert math.isclose(s["communion"], exp_co, abs_tol=1e-12)


def test_incomplete_rejected():
    ans = all_(2)
    del ans[13]
    with pytest.raises(IncompleteResponseError):
        score_response(ans, CFG)
    with pytest.raises(IncompleteResponseError):
        score_response(all_(2) | {3: 6}, CFG)


def test_aggregate_mean_and_threshold():
    agg = aggregate([all_(1), all_(5)], CFG)
    assert agg["response_count"] == 2 and agg["displayable"] is False
    assert math.isclose(agg["octants"]["oc3"], 0.5)
    agg10 = aggregate([all_(3)] * 10, CFG)
    assert agg10["displayable"] is True


def test_aggregate_empty():
    agg = aggregate([], CFG)
    assert agg == {"response_count": 0, "displayable": False, "octants": None, "agency": None, "communion": None}


def _csv(rows, with_scores=True):
    head = ["response_id", "discipline"] + [f"q{i}" for i in range(1, 25)]
    if with_scores:
        head += [f"oc{i}" for i in range(1, 9)] + ["agency", "communion"]
    lines = [",".join(head)]
    for rid, ans in rows:
        vals = [rid, "Matemática"] + [str(ans[i]) for i in range(1, 25)]
        if with_scores:
            s = score_response(ans, CFG)
            vals += [repr(s["octants"][f"oc{i}"]) for i in range(1, 9)] + [repr(s["agency"]), repr(s["communion"])]
        lines.append(",".join(vals))
    return "\n".join(lines) + "\n"


def test_parse_export_roundtrip():
    rows = [("r1", all_(3)), ("r2", where([1, 9, 17], 5, 1))]
    parsed = parse_export_csv(_csv(rows), CFG)
    assert parsed == [all_(3), where([1, 9, 17], 5, 1)]


def test_parse_export_without_score_columns():
    assert parse_export_csv(_csv([("r1", all_(4))], with_scores=False), CFG) == [all_(4)]


def test_parse_export_detects_tampered_scores():
    text = _csv([("r1", all_(3))]).replace(",0.5,", ",0.9,", 1)
    with pytest.raises(QtiImportError):
        parse_export_csv(text, CFG)


def test_parse_export_missing_column():
    text = _csv([("r1", all_(3))], with_scores=False).replace("q24", "qX")
    with pytest.raises(QtiImportError):
        parse_export_csv(text, CFG)
```
Run: `.venv/Scripts/python -m pytest tests/test_qti.py -v` → FAIL (`fias_ed_engine.qti` inexistente).

- [ ] **Step 4: Implementar `qti.py`**

```python
"""Pontuação determinística do QTI-24 (manual VIL-24) e importação do dataset exportado."""
import csv
import io
import math


class IncompleteResponseError(ValueError):
    pass


class QtiImportError(ValueError):
    pass


def _validate(answers: dict[int, int], cfg: dict) -> None:
    lo, hi = cfg["instrument"]["likert"]["min"], cfg["instrument"]["likert"]["max"]
    n = len(cfg["items"])
    if set(answers) != set(range(1, n + 1)):
        raise IncompleteResponseError(f"Resposta incompleta: esperados {n} itens, recebidos {len(answers)}.")
    for order, v in answers.items():
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise IncompleteResponseError(f"Item {order} fora da escala {lo}–{hi}.")


def score_response(answers: dict[int, int], cfg: dict) -> dict:
    _validate(answers, cfg)
    b = cfg["instrument"]["weights"]["b"]
    octants: dict[str, float] = {}
    for o in cfg["octants"]:
        vals = [answers[i["order"]] for i in cfg["items"] if i["octant"] == o["code"]]
        octants[o["code"]] = (sum(vals) / len(vals) - 1) / 4
    agency = b * sum(o["agency_weight"] * octants[o["code"]] for o in cfg["octants"])
    communion = b * sum(o["communion_weight"] * octants[o["code"]] for o in cfg["octants"])
    return {"octants": octants, "agency": agency, "communion": communion}


def aggregate(responses: list[dict[int, int]], cfg: dict) -> dict:
    n = len(responses)
    if n == 0:
        return {"response_count": 0, "displayable": False, "octants": None, "agency": None, "communion": None}
    scores = [score_response(r, cfg) for r in responses]
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return {
        "response_count": n,
        "displayable": n >= cfg["instrument"]["min_responses"],
        "octants": {o["code"]: mean([s["octants"][o["code"]] for s in scores]) for o in cfg["octants"]},
        "agency": mean([s["agency"] for s in scores]),
        "communion": mean([s["communion"] for s in scores]),
    }


def parse_export_csv(text: str, cfg: dict) -> list[dict[int, int]]:
    reader = csv.DictReader(io.StringIO(text))
    n = len(cfg["items"])
    needed = [f"q{i}" for i in range(1, n + 1)]
    missing = [c for c in needed if c not in (reader.fieldnames or [])]
    if missing:
        raise QtiImportError(f"Colunas ausentes: {', '.join(missing)}")
    out: list[dict[int, int]] = []
    for line_no, row in enumerate(reader, start=2):
        try:
            ans = {i: int(row[f"q{i}"]) for i in range(1, n + 1)}
            s = score_response(ans, cfg)
        except (ValueError, IncompleteResponseError) as exc:
            raise QtiImportError(f"Linha {line_no}: {exc}") from exc
        checks = {**s["octants"], "agency": s["agency"], "communion": s["communion"]}
        for col, expected in checks.items():
            if row.get(col) not in (None, "") and not math.isclose(float(row[col]), expected, abs_tol=1e-9):
                raise QtiImportError(f"Linha {line_no}: coluna {col} diverge do recálculo")
        out.append(ans)
    return out
```

Run: `.venv/Scripts/python -m pytest tests/test_qti.py -v` → PASS (15 testes).

- [ ] **Step 5: Commit**
```bash
git add fias-ed-shared/scripts/extract_qti.py fias-ed-shared/rules/qti_config.json fias-ed-shared/schemas/rules/qti_config.schema.json fias-ed-shared/engine-py
git commit -m "feat(shared): QTI-24 extraído da fonte congelada, pontuação VIL-24 e importação CSV"
```

---

### Task 6: Índices FIAS com evidências

**Files:**
- Create: `engine-py/src/fias_ed_engine/indices.py`
- Test: `engine-py/tests/test_indices.py`

**Interfaces:**
- Consumes: `load_rules("fias_rules")`; lista de intervalos (Task 4).
- Produces:
  - `category_counts(intervals: list[int]) -> dict[int, int]` (chaves 1..10 sempre presentes).
  - `compute_indices(intervals: list[int], rules: dict, n_segments: int = 0, confidences: list[float] | None = None) -> dict[str, dict]` → para cada índice **habilitado**: `{"id", "value": float|None, "reason": None|"insufficient_data", "numerator_count": int, "denominator_count": int, "evidence": {"n_intervals": int, "n_segments": int, "mean_confidence": float|None}, "validation_status", "source_reference"}`.

- [ ] **Step 1: Testes falhando**

`tests/test_indices.py`:
```python
import math

from fias_ed_engine.indices import category_counts, compute_indices
from fias_ed_engine.rules import load_rules

R = load_rules("fias_rules")


def test_counts_have_all_categories():
    c = category_counts([5, 5, 10])
    assert c[5] == 2 and c[10] == 1 and c[1] == 0 and set(c) == set(range(1, 11))


def test_proportions():
    iv = [1, 4, 5, 5, 8, 9, 10, 10]
    r = compute_indices(iv, R)
    assert math.isclose(r["TT"]["value"], 4 / 8)
    assert math.isclose(r["PT"]["value"], 2 / 8)
    assert math.isclose(r["SC"]["value"], 2 / 8)


def test_ratios():
    iv = [1, 4, 5, 5, 8, 9, 10, 10]
    r = compute_indices(iv, R)
    assert math.isclose(r["ID_RATIO"]["value"], 2 / 2)
    assert math.isclose(r["PIR"]["value"], 1 / 2)
    assert math.isclose(r["PUPIL_RESPONSE_RATIO"]["value"], 1 / 2)
    assert r["ID_RATIO"]["numerator_count"] == 2 and r["ID_RATIO"]["denominator_count"] == 2


def test_division_by_zero_is_null_with_reason():
    r = compute_indices([4, 4, 10], R)
    assert r["ID_RATIO"]["value"] is None and r["ID_RATIO"]["reason"] == "insufficient_data"
    assert r["PIR"]["value"] is None


def test_empty_lesson():
    r = compute_indices([], R)
    assert r["TT"]["value"] is None and r["TT"]["reason"] == "insufficient_data"


def test_disabled_indices_not_computed():
    r = compute_indices([1, 5], R)
    assert "TRR" not in r and "ID_REVISED" not in r and "I_A" not in r


def test_evidence_attached():
    r = compute_indices([1, 5, 8], R, n_segments=3, confidences=[0.9, 0.7, 0.8])
    ev = r["TT"]["evidence"]
    assert ev["n_intervals"] == 3 and ev["n_segments"] == 3 and math.isclose(ev["mean_confidence"], 0.8)
    assert r["TT"]["validation_status"] == "validated" and r["TT"]["source_reference"]
```
Run: `.venv/Scripts/python -m pytest tests/test_indices.py -v` → FAIL.

- [ ] **Step 2: Implementar**

`src/fias_ed_engine/indices.py`:
```python
"""Índices FIAS fundamentados (apenas os habilitados em fias_rules.json)."""
from collections import Counter


def category_counts(intervals: list[int]) -> dict[int, int]:
    c = Counter(intervals)
    return {k: c.get(k, 0) for k in range(1, 11)}


def compute_indices(intervals: list[int], rules: dict, n_segments: int = 0,
                    confidences: list[float] | None = None) -> dict[str, dict]:
    counts = category_counts(intervals)
    total = len(intervals)
    mean_conf = sum(confidences) / len(confidences) if confidences else None
    out: dict[str, dict] = {}
    for idx in rules["indices"]:
        if not idx["enabled"]:
            continue
        num = sum(counts[c] for c in idx["numerator"])
        den = total if idx["denominator"] == "all" else sum(counts[c] for c in idx["denominator"])
        value = num / den if den > 0 else None
        out[idx["id"]] = {
            "id": idx["id"],
            "value": value,
            "reason": None if value is not None else "insufficient_data",
            "numerator_count": num,
            "denominator_count": den,
            "evidence": {"n_intervals": total, "n_segments": n_segments, "mean_confidence": mean_conf},
            "validation_status": idx["validation_status"],
            "source_reference": idx["source_reference"],
        }
    return out
```

Run: `.venv/Scripts/python -m pytest tests/test_indices.py -v` → PASS (7 testes).

- [ ] **Step 3: Commit**
```bash
git add fias-ed-shared/engine-py
git commit -m "feat(shared): índices FIAS (TT, PT, SC, I/D, PIR, razão de resposta) com evidências"
```

---

### Task 7: Pós-processamento do classificador (softmax + restrição por papel)

**Files:**
- Create: `engine-py/src/fias_ed_engine/classifier.py`
- Test: `engine-py/tests/test_classifier.py`

**Interfaces:**
- Consumes: `fias_rules.classifier`.
- Produces:
  - `softmax(logits: list[float]) -> list[float]` (numericamente estável).
  - `@dataclass(frozen=True) class RolePrediction: pred_raw: int; pred_role_constrained: int; confidence_raw: float; confidence: float; uncertain: bool`
  - `constrain_by_role(logits: list[float], role: str, rules: dict) -> RolePrediction` — `role` ∈ `PROFESSOR|ALUNO`; categorias = índice + `logit_index_offset`; `confidence` = probabilidade (softmax sobre as 10 saídas, sem renormalizar) da categoria restrita; `uncertain = confidence < uncertain_below`.
  - `divergence_rate(preds: list[RolePrediction]) -> float|None`.

- [ ] **Step 1: Testes falhando**

`tests/test_classifier.py`:
```python
import math

import pytest

from fias_ed_engine.classifier import constrain_by_role, divergence_rate, softmax
from fias_ed_engine.rules import load_rules

R = load_rules("fias_rules")


def logits_peak(cat, second=None):
    lg = [0.0] * 10
    lg[cat - 1] = 5.0
    if second:
        lg[second - 1] = 4.0
    return lg


def test_softmax_sums_to_one_and_stable():
    p = softmax([1000.0, 1000.0])
    assert math.isclose(sum(p), 1.0) and math.isclose(p[0], 0.5)


def test_teacher_raw_agrees():
    r = constrain_by_role(logits_peak(5), "PROFESSOR", R)
    assert r.pred_raw == 5 and r.pred_role_constrained == 5
    assert math.isclose(r.confidence, r.confidence_raw)


def test_teacher_constrained_away_from_student_category():
    r = constrain_by_role(logits_peak(8, second=3), "PROFESSOR", R)
    assert r.pred_raw == 8 and r.pred_role_constrained == 3
    assert r.confidence < r.confidence_raw


def test_student_constrained_to_8_or_9():
    r = constrain_by_role(logits_peak(5, second=9), "ALUNO", R)
    assert r.pred_role_constrained == 9


def test_uncertain_flag():
    r = constrain_by_role([0.0] * 10, "PROFESSOR", R)
    assert r.uncertain is True and math.isclose(r.confidence, 0.1)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        constrain_by_role([0.0] * 9, "PROFESSOR", R)
    with pytest.raises(ValueError):
        constrain_by_role([0.0] * 10, "SPEAKER_00", R)


def test_divergence_rate():
    a = constrain_by_role(logits_peak(5), "PROFESSOR", R)
    b = constrain_by_role(logits_peak(8, second=3), "PROFESSOR", R)
    assert divergence_rate([a, b]) == 0.5
    assert divergence_rate([]) is None
```
Run: `.venv/Scripts/python -m pytest tests/test_classifier.py -v` → FAIL.

- [ ] **Step 2: Implementar**

`src/fias_ed_engine/classifier.py`:
```python
"""Pós-processamento das saídas do BERTimbau: confiança e restrição por papel do falante."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RolePrediction:
    pred_raw: int
    pred_role_constrained: int
    confidence_raw: float
    confidence: float
    uncertain: bool


def softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


def constrain_by_role(logits: list[float], role: str, rules: dict) -> RolePrediction:
    cfg = rules["classifier"]
    if len(logits) != 10:
        raise ValueError(f"Esperados 10 logits, recebidos {len(logits)}")
    if role not in cfg["role_categories"]:
        raise ValueError(f"Papel inválido: {role}")
    off = cfg["logit_index_offset"]
    probs = softmax(logits)
    raw_idx = max(range(10), key=lambda i: probs[i])
    allowed = [c - off for c in cfg["role_categories"][role]]
    con_idx = max(allowed, key=lambda i: probs[i])
    return RolePrediction(
        pred_raw=raw_idx + off,
        pred_role_constrained=con_idx + off,
        confidence_raw=probs[raw_idx],
        confidence=probs[con_idx],
        uncertain=probs[con_idx] < cfg["uncertain_below"],
    )


def divergence_rate(preds: list[RolePrediction]) -> float | None:
    if not preds:
        return None
    return sum(p.pred_raw != p.pred_role_constrained for p in preds) / len(preds)
```

Run: `.venv/Scripts/python -m pytest tests/test_classifier.py -v` → PASS (7 testes).

- [ ] **Step 3: Commit**
```bash
git add fias-ed-shared/engine-py
git commit -m "feat(shared): confiança e restrição por papel das predições FIAS"
```

---

### Task 8: MTSS Tier 1 — regras, sugestões, avaliação e verificação de linguagem

**Files:**
- Create: `fias-ed-shared/rules/mtss_rules.json`
- Create: `fias-ed-shared/rules/pedagogical_rules.json` (bloco `recommendations`; o bloco `triangulation_pairs` entra na Task 9 — criar agora já com `"triangulation_pairs": []`)
- Create: `fias-ed-shared/schemas/rules/mtss_rules.schema.json`
- Create: `fias-ed-shared/schemas/rules/pedagogical_rules.schema.json`
- Create: `engine-py/src/fias_ed_engine/mtss.py`
- Create: `engine-py/src/fias_ed_engine/language.py`
- Test: `engine-py/tests/test_mtss.py`, `engine-py/tests/test_language.py`

**Interfaces:**
- Consumes: `compute_indices`, `category_counts` (Task 6).
- Produces:
  - `mtss.build_facts(intervals: list[int], indices: dict[str, dict]) -> dict[str, float|int|None]` — chaves: `count_cat_1..count_cat_10`, `modal_teacher_category` (categoria 1–7 com mais intervalos; empate → menor id; nenhuma → None), e cada índice habilitado pelo id (`TT`, `PT`, `SC`, `ID_RATIO`, `PIR`, `PUPIL_RESPONSE_RATIO`) com o `value`.
  - `mtss.evaluate(facts: dict, mtss_rules: dict) -> list[dict]` — para cada regra `enabled` cujas condições valem: `{"rule_id", "tier1_dimension", "framing", "interpretation", "recommendation_ids", "evidence": {fact: value}, "source_reference", "validation_status", "rules_version"}`. Fato ausente/None → condição falsa.
  - `mtss.recommendations(fired: list[dict], pedagogical: dict) -> list[dict]` — `{"recommendation_id", "rule_id", "text", "validation_status", "source_reference"}`, sem duplicatas, na ordem de disparo.
  - `mtss.select_evidence_segments(segments: list[dict], category: int, limit: int = 3) -> list[dict]` — `segments` = `[{"segment_id", "start_ms", "text", "category", "confidence"}]`; retorna os de maior confiança da categoria, desempate por `start_ms`.
  - `language.find_forbidden(text: str) -> list[str]`; `language.FORBIDDEN_PATTERNS`.

- [ ] **Step 1: Schemas**

`schemas/rules/mtss_rules.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/rules/mtss_rules.schema.json",
  "$defs": {
    "leaf": {"type": "object", "required": ["fact", "op"], "additionalProperties": false,
      "properties": {"fact": {"type": "string"},
        "op": {"enum": ["eq", "ne", "lt", "lte", "gt", "gte", "present", "absent"]},
        "value": {"type": ["number", "integer"]}}},
    "cond": {"oneOf": [
      {"$ref": "#/$defs/leaf"},
      {"type": "object", "required": ["all"], "additionalProperties": false, "properties": {"all": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/cond"}}}},
      {"type": "object", "required": ["any"], "additionalProperties": false, "properties": {"any": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/cond"}}}}]}
  },
  "type": "object",
  "required": ["rules_version", "rules"],
  "properties": {
    "rules_version": {"$ref": "common.schema.json#/$defs/rules_version"},
    "rules": {"type": "array", "items": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["rule_id", "rules_version", "tier1_dimension", "framing", "conditions", "evidence", "interpretation", "recommendation_ids", "enabled"],
      "properties": {
        "rule_id": {"type": "string", "pattern": "^MTSS_[A-Z0-9_]+$"},
        "rules_version": {"$ref": "common.schema.json#/$defs/rules_version"},
        "framing": {"enum": ["reflection", "strength"]},
        "conditions": {"$ref": "#/$defs/cond"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "interpretation": {"type": "string", "minLength": 10},
        "recommendation_ids": {"type": "array", "items": {"type": "string"}},
        "enabled": {"type": "boolean"},
        "threshold_pending_validation": {"type": "boolean"}
      },
      "if": {"properties": {"threshold_pending_validation": {"const": true}}, "required": ["threshold_pending_validation"]},
      "then": {"properties": {"enabled": {"const": false}}}}]}}
  }
}
```

`schemas/rules/pedagogical_rules.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/rules/pedagogical_rules.schema.json",
  "type": "object",
  "required": ["rules_version", "recommendations", "triangulation_pairs"],
  "properties": {
    "rules_version": {"$ref": "common.schema.json#/$defs/rules_version"},
    "recommendations": {"type": "array", "items": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["recommendation_id", "tier1_dimension", "text"],
      "properties": {"recommendation_id": {"type": "string", "pattern": "^PED_[A-Z0-9_]+$"},
                     "text": {"type": "string", "minLength": 10}}}]}},
    "triangulation_pairs": {"type": "array", "items": {"allOf": [{"$ref": "common.schema.json#/$defs/trace"}, {
      "required": ["pair_id", "fias", "qti_octants", "reflection_question"],
      "properties": {
        "pair_id": {"type": "string", "pattern": "^TRI_[A-Z0-9_]+$"},
        "fias": {"oneOf": [
          {"type": "object", "required": ["index"], "additionalProperties": false, "properties": {"index": {"type": "string"}}},
          {"type": "object", "required": ["categories"], "additionalProperties": false, "properties": {"categories": {"type": "array", "items": {"$ref": "common.schema.json#/$defs/category"}, "minItems": 1}}}]},
        "qti_octants": {"type": "array", "items": {"pattern": "^oc[1-8]$"}, "minItems": 1},
        "reflection_question": {"type": "string", "minLength": 10}}}]}}
  }
}
```

- [ ] **Step 2: `mtss_rules.json`** (condições descritivas; dimensões da Tab. `tab:art2-fias-tier1`, CAP4 l.137–146; cortes de FU desligados)

```json
{
  "rules_version": "1.0.0",
  "rules": [
    {"rule_id": "MTSS_EXPOSITIVE_PREDOMINANCE", "rules_version": "1.0.0", "tier1_dimension": "Ensino explícito (modelagem)", "framing": "reflection",
     "conditions": {"fact": "modal_teacher_category", "op": "eq", "value": 5},
     "evidence": ["TT", "ID_RATIO", "count_cat_5", "segments:category=5"],
     "interpretation": "A exposição foi o tipo de fala docente mais frequente nesta aula. Este padrão pode indicar um momento de ensino explícito, em que a modelagem do conteúdo ocupou a maior parte do tempo.",
     "recommendation_ids": ["PED_CHECK_UNDERSTANDING", "PED_WAIT_TIME"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 5 ↔ Ensino explícito, intensidade moderada); CAP4 l.285", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_INSTRUCTIONS_PREDOMINANCE", "rules_version": "1.0.0", "tier1_dimension": "Gestão proativa de rotinas e transições", "framing": "reflection",
     "conditions": {"fact": "modal_teacher_category", "op": "eq", "value": 6},
     "evidence": ["TT", "count_cat_6", "segments:category=6"],
     "interpretation": "Dar instruções foi o tipo de fala docente mais frequente. Este padrão pode indicar uma aula com muitas transições ou tarefas que exigiram orientação.",
     "recommendation_ids": ["PED_ROUTINES_VISIBLE"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 6 ↔ Gestão proativa de rotinas e transições)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_DIRECT_OVER_INDIRECT", "rules_version": "1.0.0", "tier1_dimension": "Engajamento e uptake dialógico", "framing": "reflection",
     "conditions": {"fact": "ID_RATIO", "op": "lt", "value": 1},
     "evidence": ["ID_RATIO", "count_cat_1", "count_cat_2", "count_cat_3", "count_cat_4", "count_cat_5", "count_cat_6", "count_cat_7"],
     "interpretation": "Nesta aula, a fala docente de influência direta (expor, instruir, corrigir) ocupou mais intervalos que a de influência indireta (acolher, encorajar, usar ideias, perguntar). Este padrão pode indicar uma aula mais expositiva ou diretiva.",
     "recommendation_ids": ["PED_USE_STUDENT_IDEAS", "PED_OPEN_QUESTIONS"],
     "source_reference": "SIMB (r_id = cat. 1–4 / cat. 5–7); CAP4 l.285 (percentuais altos em 5, 6 ou 7 indicam padrão mais expositivo ou diretivo). O valor 1 é o ponto de igualdade aritmética, não um corte normativo.", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_NO_STUDENT_INITIATIVE", "rules_version": "1.0.0", "tier1_dimension": "Engajamento ativo e voz discente", "framing": "reflection",
     "conditions": {"all": [{"fact": "count_cat_9", "op": "eq", "value": 0}, {"fact": "count_cat_8", "op": "gt", "value": 0}]},
     "evidence": ["PIR", "count_cat_8", "count_cat_9"],
     "interpretation": "Os estudantes falaram respondendo, mas não houve falas de iniciativa própria registradas. Este padrão pode indicar que a participação aconteceu principalmente a partir das perguntas do professor.",
     "recommendation_ids": ["PED_INVITE_STUDENT_QUESTIONS"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 9 ↔ Engajamento ativo e voz discente); SIMB (PIR)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_NO_IDEA_UPTAKE", "rules_version": "1.0.0", "tier1_dimension": "Engajamento e uptake dialógico", "framing": "reflection",
     "conditions": {"all": [{"fact": "count_cat_3", "op": "eq", "value": 0}, {"fact": "count_cat_8", "op": "gt", "value": 0}]},
     "evidence": ["count_cat_3", "count_cat_8", "segments:category=8"],
     "interpretation": "Houve falas de estudantes, mas não foram registrados momentos em que o professor retomou ou desenvolveu uma ideia trazida por eles. Uma possibilidade é que essas retomadas tenham acontecido de forma breve e não tenham sido captadas.",
     "recommendation_ids": ["PED_USE_STUDENT_IDEAS"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 3 ↔ Engajamento e uptake dialógico)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_NO_PRAISE", "rules_version": "1.0.0", "tier1_dimension": "Feedback formativo contingente", "framing": "reflection",
     "conditions": {"all": [{"fact": "count_cat_2", "op": "eq", "value": 0}, {"fact": "count_cat_8", "op": "gt", "value": 0}]},
     "evidence": ["count_cat_2", "count_cat_8"],
     "interpretation": "Não foram registrados momentos de elogio ou encorajamento após as falas dos estudantes. Este padrão pode indicar que o retorno às respostas foi dado de outras formas.",
     "recommendation_ids": ["PED_SPECIFIC_FEEDBACK"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 2 ↔ Feedback formativo contingente)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_REACTIVE_MANAGEMENT_PRESENT", "rules_version": "1.0.0", "tier1_dimension": "Gestão reativa", "framing": "reflection",
     "conditions": {"fact": "count_cat_7", "op": "gt", "value": 0},
     "evidence": ["count_cat_7", "segments:category=7"],
     "interpretation": "Em alguns momentos da aula houve falas de crítica ou de afirmação de autoridade. Os trechos abaixo mostram onde isso aconteceu, para que você possa observar o contexto.",
     "recommendation_ids": ["PED_PROACTIVE_EXPECTATIONS"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 7 ↔ Gestão reativa, intensidade negativa)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_STUDENT_INITIATIVE_PRESENT", "rules_version": "1.0.0", "tier1_dimension": "Engajamento ativo e voz discente", "framing": "strength",
     "conditions": {"fact": "count_cat_9", "op": "gt", "value": 0},
     "evidence": ["PIR", "count_cat_9", "segments:category=9"],
     "interpretation": "Houve momentos em que os estudantes falaram por iniciativa própria. Este padrão pode indicar espaço para a voz discente na aula.",
     "recommendation_ids": ["PED_KEEP_STUDENT_VOICE"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 9, intensidade forte)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_QUESTIONS_PRESENT", "rules_version": "1.0.0", "tier1_dimension": "Engajamento cognitivo de alta demanda", "framing": "strength",
     "conditions": {"fact": "count_cat_4", "op": "gt", "value": 0},
     "evidence": ["count_cat_4", "segments:category=4"],
     "interpretation": "As perguntas estiveram presentes na fala docente. Os trechos mostram algumas delas, para que você observe que tipo de pensamento elas convidaram.",
     "recommendation_ids": ["PED_OPEN_QUESTIONS"],
     "source_reference": "CAP4 tab:art2-fias-tier1 l.137-146 (cat. 4 ↔ Engajamento cognitivo de alta demanda)", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": true},
    {"rule_id": "MTSS_FU_ID_BAND_LOW", "rules_version": "1.0.0", "tier1_dimension": "Engajamento e uptake dialógico", "framing": "reflection",
     "conditions": {"fact": "ID_RATIO", "op": "lt", "value": 0.4},
     "evidence": ["ID_RATIO"], "interpretation": "Corte proposto em documento de apoio, sem fonte primária; desligado até validação.",
     "recommendation_ids": [], "threshold_pending_validation": true,
     "source_reference": "FU Uso #2 (selo I/D < 0,40), sem referência primária", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": false},
    {"rule_id": "MTSS_FU_ID_BAND_TARGET", "rules_version": "1.0.0", "tier1_dimension": "Engajamento e uptake dialógico", "framing": "reflection",
     "conditions": {"fact": "ID_RATIO", "op": "lt", "value": 0.7},
     "evidence": ["ID_RATIO"], "interpretation": "Meta I/D = 0,70 proposta em documento de apoio, sem fonte primária; desligada até validação.",
     "recommendation_ids": [], "threshold_pending_validation": true,
     "source_reference": "FU Usos #2 e #9 (0,40–0,69; meta 0,70), sem referência primária", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": false},
    {"rule_id": "MTSS_FU_STUDENT_TALK_LOW", "rules_version": "1.0.0", "tier1_dimension": "Engajamento ativo e voz discente", "framing": "reflection",
     "conditions": {"fact": "PT", "op": "lt", "value": 0.25},
     "evidence": ["PT"], "interpretation": "Corte de 25% de fala discente proposto em documento de apoio, sem fonte primária; desligado até validação.",
     "recommendation_ids": [], "threshold_pending_validation": true,
     "source_reference": "FU Uso #2 (fala discente < 25%), sem referência primária", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": false},
    {"rule_id": "MTSS_FU_INDIRECT_TWO_THIRDS", "rules_version": "1.0.0", "tier1_dimension": "Engajamento e uptake dialógico", "framing": "reflection",
     "conditions": {"fact": "ID_RATIO", "op": "lt", "value": 1.5},
     "evidence": ["ID_RATIO"], "interpretation": "≥60% de intervalos docentes indiretos ('adaptado da regra dos dois terços') proposto sem definição primária; I/D ≥ 1,5 equivale a 60% indiretos. Desligado até validação.",
     "recommendation_ids": [], "threshold_pending_validation": true,
     "source_reference": "FU Uso #3; 'regra dos dois terços' citada sem definição em CAP4 tab:art2-resultados-esperados-sintese l.408", "validation_status": "PENDING_SCIENTIFIC_VALIDATION", "enabled": false}
  ]
}
```

- [ ] **Step 3: `pedagogical_rules.json`** (textos `draft_pending_researcher_review`)

```json
{
  "rules_version": "1.0.0",
  "recommendations": [
    {"recommendation_id": "PED_CHECK_UNDERSTANDING", "tier1_dimension": "Ensino explícito (modelagem)", "text": "Considere intercalar os momentos de exposição com pausas curtas em que os estudantes expliquem com as próprias palavras o que acabaram de ouvir.", "source_reference": "Redigido a partir da dimensão Tier 1 'Ensino explícito (modelagem)', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_WAIT_TIME", "tier1_dimension": "Ensino explícito (modelagem)", "text": "Você pode experimentar aguardar alguns segundos a mais depois de uma pergunta antes de retomar a explicação, dando tempo para que mais estudantes elaborem uma resposta.", "source_reference": "Redigido a partir da dimensão Tier 1 'Ensino explícito (modelagem)', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_ROUTINES_VISIBLE", "tier1_dimension": "Gestão proativa de rotinas e transições", "text": "Uma possibilidade é deixar as etapas da atividade visíveis no quadro, para que parte das orientações possa ser consultada pelos estudantes sem precisar ser repetida.", "source_reference": "Redigido a partir da dimensão Tier 1 'Gestão proativa de rotinas e transições', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_USE_STUDENT_IDEAS", "tier1_dimension": "Engajamento e uptake dialógico", "text": "Considere retomar em voz alta uma ideia trazida por um estudante e perguntar à turma como ela se relaciona com o conteúdo, antes de apresentar a sua própria explicação.", "source_reference": "Redigido a partir da dimensão Tier 1 'Engajamento e uptake dialógico', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_OPEN_QUESTIONS", "tier1_dimension": "Engajamento cognitivo de alta demanda", "text": "Você pode experimentar incluir perguntas que peçam justificativa, como \"por que você acha isso?\" ou \"como chegou a essa resposta?\".", "source_reference": "Redigido a partir da dimensão Tier 1 'Engajamento cognitivo de alta demanda', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_INVITE_STUDENT_QUESTIONS", "tier1_dimension": "Engajamento ativo e voz discente", "text": "Uma possibilidade é reservar um momento da aula para que os estudantes formulem as próprias perguntas sobre o tema, em duplas ou individualmente.", "source_reference": "Redigido a partir da dimensão Tier 1 'Engajamento ativo e voz discente', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_SPECIFIC_FEEDBACK", "tier1_dimension": "Feedback formativo contingente", "text": "Considere responder às contribuições dos estudantes apontando o que especificamente ajudou no raciocínio, e não apenas se a resposta estava certa.", "source_reference": "Redigido a partir da dimensão Tier 1 'Feedback formativo contingente', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_PROACTIVE_EXPECTATIONS", "tier1_dimension": "Gestão reativa", "text": "Uma possibilidade é combinar com a turma, no início da aula, as expectativas para os momentos de maior agitação, de modo que as intervenções possam ser mais breves.", "source_reference": "Redigido a partir da dimensão Tier 1 'Gestão reativa' ↔ 'Gestão proativa do clima de sala', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"},
    {"recommendation_id": "PED_KEEP_STUDENT_VOICE", "tier1_dimension": "Engajamento ativo e voz discente", "text": "Os momentos de iniciativa dos estudantes podem ser um ponto de partida: considere observar o que os favoreceu nesta aula e repetir essas condições.", "source_reference": "Redigido a partir da dimensão Tier 1 'Engajamento ativo e voz discente', CAP4 tab:art2-fias-tier1", "validation_status": "draft_pending_researcher_review"}
  ],
  "triangulation_pairs": []
}
```

- [ ] **Step 4: Testes falhando**

`tests/test_language.py`:
```python
from fias_ed_engine.language import find_forbidden
from fias_ed_engine.rules import load_rules


def test_detects_forbidden():
    assert sorted(find_forbidden("Seu desempenho foi ruim")) == ["desempenho", "ruim"]
    assert find_forbidden("Você fez errado") == ["errado"]
    assert find_forbidden("A aula está não conforme") == ["conforme", "não conforme"]


def test_word_boundaries():
    assert find_forbidden("Vale anotar os momentos de pergunta") == []
    assert find_forbidden("conformidade das rotinas") == []


def test_rules_texts_are_clean():
    texts = [r["interpretation"] for r in load_rules("mtss_rules")["rules"] if r["enabled"]]
    ped = load_rules("pedagogical_rules")
    texts += [r["text"] for r in ped["recommendations"]]
    texts += [p["reflection_question"] for p in ped["triangulation_pairs"]]
    offenders = {t: find_forbidden(t) for t in texts if find_forbidden(t)}
    assert offenders == {}
```

`tests/test_mtss.py`:
```python
from fias_ed_engine.indices import compute_indices
from fias_ed_engine.mtss import build_facts, evaluate, recommendations, select_evidence_segments
from fias_ed_engine.rules import load_rules
from fias_ed_engine.traceability import find_untraced

F = load_rules("fias_rules")
M = load_rules("mtss_rules")
P = load_rules("pedagogical_rules")


def facts(iv):
    return build_facts(iv, compute_indices(iv, F))


def ids(fired):
    return [f["rule_id"] for f in fired]


def test_traced():
    assert find_untraced(M) == [] and find_untraced(P) == []


def test_every_recommendation_id_exists():
    known = {r["recommendation_id"] for r in P["recommendations"]}
    for r in M["rules"]:
        assert set(r["recommendation_ids"]) <= known, r["rule_id"]


def test_build_facts_modal_and_counts():
    f = facts([5, 5, 4, 8, 10])
    assert f["modal_teacher_category"] == 5 and f["count_cat_8"] == 1 and f["count_cat_9"] == 0
    assert f["ID_RATIO"] == 0.5


def test_modal_tie_takes_lowest_and_none_without_teacher():
    assert facts([4, 5])["modal_teacher_category"] == 4
    assert facts([8, 10])["modal_teacher_category"] is None


def test_expositive_lesson_fires_expected_rules():
    fired = evaluate(facts([5, 5, 5, 4, 8, 8, 10]), M)
    assert ids(fired) == ["MTSS_EXPOSITIVE_PREDOMINANCE", "MTSS_DIRECT_OVER_INDIRECT",
                          "MTSS_NO_STUDENT_INITIATIVE", "MTSS_NO_IDEA_UPTAKE", "MTSS_NO_PRAISE",
                          "MTSS_QUESTIONS_PRESENT"]
    assert fired[0]["evidence"]["count_cat_5"] == 3
    assert fired[0]["framing"] == "reflection"


def test_disabled_threshold_rules_never_fire():
    fired = evaluate(facts([5, 5, 5, 5, 8]), M)
    assert not any(r.startswith("MTSS_FU_") for r in ids(fired))


def test_none_fact_is_false():
    fired = evaluate(facts([4, 4, 10]), M)  # ID_RATIO None (sem cat. 5–7)
    assert "MTSS_DIRECT_OVER_INDIRECT" not in ids(fired)


def test_any_and_present_ops():
    rules = {"rules_version": "1.0.0", "rules": [{
        "rule_id": "MTSS_T", "rules_version": "1.0.0", "tier1_dimension": "x", "framing": "strength",
        "conditions": {"any": [{"fact": "PIR", "op": "present"}, {"fact": "count_cat_9", "op": "gt", "value": 5}]},
        "evidence": ["PIR"], "interpretation": "Este padrão pode indicar algo.", "recommendation_ids": [],
        "source_reference": "teste", "validation_status": "engineering_decision", "enabled": True}]}
    assert ids(evaluate(facts([8, 9]), rules)) == ["MTSS_T"]
    assert ids(evaluate(facts([4]), rules)) == []


def test_recommendations_dedup_in_order():
    fired = evaluate(facts([5, 5, 5, 4, 8, 8, 10]), M)
    recs = recommendations(fired, P)
    rid = [r["recommendation_id"] for r in recs]
    assert rid[0] == "PED_CHECK_UNDERSTANDING" and len(rid) == len(set(rid))
    assert all(r["validation_status"] == "draft_pending_researcher_review" for r in recs)


def test_select_evidence_segments():
    segs = [{"segment_id": "a", "start_ms": 0, "text": "x", "category": 5, "confidence": 0.6},
            {"segment_id": "b", "start_ms": 10, "text": "y", "category": 5, "confidence": 0.9},
            {"segment_id": "c", "start_ms": 20, "text": "z", "category": 4, "confidence": 0.99},
            {"segment_id": "d", "start_ms": 5, "text": "w", "category": 5, "confidence": 0.6}]
    assert [s["segment_id"] for s in select_evidence_segments(segs, 5, limit=2)] == ["b", "a"]
```
Run: `.venv/Scripts/python -m pytest tests/test_mtss.py tests/test_language.py -v` → FAIL.

Nota sobre a ordem esperada em `test_expositive_lesson_fires_expected_rules`: é a ordem de declaração em `mtss_rules.json`. Com `[5,5,5,4,8,8,10]`: modal=5 ✓; I/D=1/3<1 ✓; cat9=0 e cat8>0 ✓; cat3=0 e cat8>0 ✓; cat2=0 e cat8>0 ✓; cat7=0 ✗; cat9>0 ✗; cat4>0 ✓.

A ordem retornada por `find_forbidden` é a ordem de `FORBIDDEN_PATTERNS`, sem duplicatas.

- [ ] **Step 5: Implementar `language.py` e `mtss.py`**

`src/fias_ed_engine/language.py`:
```python
"""Verificação da linguagem formativa (nada de julgamento ou rótulo de desempenho)."""
import re

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    ("errado", r"\berrad[oa]s?\b"),
    ("ruim", r"\bruins?\b"),
    ("inadequado", r"\binadequad[oa]s?\b"),
    ("nota", r"\bnotas?\b"),
    ("desempenho", r"\bdesempenhos?\b"),
    ("fracasso", r"\bfracass(o|os|ou)\b"),
    ("deveria ter", r"\bdeveria ter\b"),
    ("conforme", r"\bconforme\b"),
    ("não conforme", r"\bn[ãa]o conforme\b"),
    ("reprovado", r"\breprovad[oa]s?\b"),
    ("avaliação docente", r"\bavalia[çc][ãa]o docente\b"),
]


def find_forbidden(text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in FORBIDDEN_PATTERNS:
        if label not in hits and re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(label)
    return hits
```

`src/fias_ed_engine/mtss.py`:
```python
"""MTSS Tier 1 descritivo: fatos da aula, avaliação de regras, sugestões e trechos de evidência."""
from .indices import category_counts

_OPS = {
    "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b,
}


def build_facts(intervals: list[int], indices: dict[str, dict]) -> dict:
    counts = category_counts(intervals)
    facts: dict = {f"count_cat_{k}": v for k, v in counts.items()}
    teacher = [(counts[c], -c) for c in range(1, 8) if counts[c] > 0]
    facts["modal_teacher_category"] = -max(teacher)[1] if teacher else None
    for idx_id, res in indices.items():
        facts[idx_id] = res["value"]
    return facts


def _holds(cond: dict, facts: dict) -> bool:
    if "all" in cond:
        return all(_holds(c, facts) for c in cond["all"])
    if "any" in cond:
        return any(_holds(c, facts) for c in cond["any"])
    value = facts.get(cond["fact"])
    if cond["op"] == "present":
        return value is not None
    if cond["op"] == "absent":
        return value is None
    return value is not None and _OPS[cond["op"]](value, cond["value"])


def evaluate(facts: dict, mtss_rules: dict) -> list[dict]:
    fired = []
    for r in mtss_rules["rules"]:
        if not r["enabled"] or not _holds(r["conditions"], facts):
            continue
        fired.append({
            "rule_id": r["rule_id"],
            "tier1_dimension": r["tier1_dimension"],
            "framing": r["framing"],
            "interpretation": r["interpretation"],
            "recommendation_ids": list(r["recommendation_ids"]),
            "evidence": {e: facts.get(e) for e in r["evidence"] if not e.startswith("segments:")},
            "evidence_segment_categories": [int(e.split("=")[1]) for e in r["evidence"] if e.startswith("segments:category=")],
            "source_reference": r["source_reference"],
            "validation_status": r["validation_status"],
            "rules_version": r["rules_version"],
        })
    return fired


def recommendations(fired: list[dict], pedagogical: dict) -> list[dict]:
    by_id = {r["recommendation_id"]: r for r in pedagogical["recommendations"]}
    out, seen = [], set()
    for f in fired:
        for rid in f["recommendation_ids"]:
            if rid in seen:
                continue
            seen.add(rid)
            r = by_id[rid]
            out.append({"recommendation_id": rid, "rule_id": f["rule_id"], "text": r["text"],
                        "validation_status": r["validation_status"], "source_reference": r["source_reference"]})
    return out


def select_evidence_segments(segments: list[dict], category: int, limit: int = 3) -> list[dict]:
    chosen = [s for s in segments if s["category"] == category]
    chosen.sort(key=lambda s: (-s["confidence"], s["start_ms"]))
    return chosen[:limit]
```

Nota: em `select_evidence_segments` o desempate é por `start_ms` crescente; no teste, "a" (0 ms) e "d" (5 ms) têm 0,6 → "a" vem antes. ✓

Run: `.venv/Scripts/python -m pytest tests/test_mtss.py tests/test_language.py -v` → PASS.

- [ ] **Step 6: Commit**
```bash
git add fias-ed-shared/rules/mtss_rules.json fias-ed-shared/rules/pedagogical_rules.json fias-ed-shared/schemas/rules fias-ed-shared/engine-py
git commit -m "feat(shared): MTSS Tier 1 descritivo, sugestões preliminares e verificação de linguagem"
```

---

### Task 9: Triangulação FIAS × QTI (justaposição, sem veredito)

**Files:**
- Modify: `fias-ed-shared/rules/pedagogical_rules.json` (preencher `triangulation_pairs`)
- Create: `engine-py/src/fias_ed_engine/triangulation.py`
- Test: `engine-py/tests/test_triangulation.py`

**Interfaces:**
- Consumes: `compute_indices`, `category_counts`, `qti.aggregate`.
- Produces: `triangulate(intervals: list[int], indices: dict[str, dict], qti_result: dict, pedagogical: dict, qti_cfg: dict) -> list[dict]` → por par: `{"pair_id", "fias": {"kind": "index"|"categories", "ref": str|list[int], "value": float|None}, "qti": [{"octant", "label", "value": float|None}], "qti_available": bool, "reflection_question", "source_reference", "validation_status"}`. **Sem campo de veredito.** `qti_available = qti_result["displayable"]`; se falso, valores QTI = None.

- [ ] **Step 1: Preencher pares**

Substituir `"triangulation_pairs": []` por:
```json
"triangulation_pairs": [
  {"pair_id": "TRI_WARMTH", "fias": {"categories": [2, 3]}, "qti_octants": ["oc2", "oc3"],
   "reflection_question": "Nesta aula houve momentos de encorajamento e de uso das ideias dos estudantes. Como isso se relaciona com o quanto a turma percebe você como amigável e compreensivo?",
   "source_reference": "CAP4 subsec:art2-triangulacao l.350-371 (exemplo de convergência: alta cat. 2/3 + DC/CS altos; Fisher 1995). Pareamento operacional proposto no spec §6.", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
  {"pair_id": "TRI_INFLUENCE", "fias": {"index": "ID_RATIO"}, "qti_octants": ["oc1", "oc8"],
   "reflection_question": "O equilíbrio entre fala de influência indireta e direta desta aula combina com o modo como os estudantes percebem sua liderança e seu rigor?",
   "source_reference": "CAP4 subsec:art2-triangulacao l.350-371 (exemplo de divergência reveladora: I/D alta + DO alto). Pareamento operacional proposto no spec §6.", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
  {"pair_id": "TRI_STUDENT_VOICE", "fias": {"index": "PIR"}, "qti_octants": ["oc4"],
   "reflection_question": "Quanto espaço os estudantes tiveram para falar por iniciativa própria nesta aula, e como eles percebem a liberdade que você oferece?",
   "source_reference": "CAP4 subsec:art2-triangulacao l.350-371 (complementaridade). Pareamento operacional proposto no spec §6.", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"},
  {"pair_id": "TRI_TENSION", "fias": {"categories": [7]}, "qti_octants": ["oc7", "oc6"],
   "reflection_question": "Os momentos de crítica ou afirmação de autoridade desta aula aparecem também na forma como os estudantes percebem irritação ou insatisfação?",
   "source_reference": "CAP4 subsec:art2-triangulacao l.350-371. Pareamento operacional proposto no spec §6.", "validation_status": "PENDING_SCIENTIFIC_VALIDATION"}
]
```

- [ ] **Step 2: Testes falhando**

`tests/test_triangulation.py`:
```python
import math

from fias_ed_engine.indices import compute_indices
from fias_ed_engine.qti import aggregate
from fias_ed_engine.rules import load_rules
from fias_ed_engine.triangulation import triangulate

F = load_rules("fias_rules")
P = load_rules("pedagogical_rules")
Q = load_rules("qti_config")
IV = [2, 3, 5, 5, 8, 9, 7, 10]


def run(qti):
    return triangulate(IV, compute_indices(IV, F), qti, P, Q)


def test_pairs_with_qti():
    out = run(aggregate([{i: 3 for i in range(1, 25)}] * 10, Q))
    by = {p["pair_id"]: p for p in out}
    assert math.isclose(by["TRI_WARMTH"]["fias"]["value"], 2 / 8)
    assert math.isclose(by["TRI_INFLUENCE"]["fias"]["value"], 2 / 3)
    assert by["TRI_WARMTH"]["qti_available"] is True
    assert [q["label"] for q in by["TRI_WARMTH"]["qti"]] == ["Amigável", "Compreensivo"]
    assert math.isclose(by["TRI_WARMTH"]["qti"][0]["value"], 0.5)


def test_pairs_without_enough_qti():
    out = run(aggregate([{i: 3 for i in range(1, 25)}] * 3, Q))
    assert all(p["qti_available"] is False for p in out)
    assert all(q["value"] is None for p in out for q in p["qti"])


def test_no_verdict_fields():
    out = run(aggregate([], Q))
    for p in out:
        assert not {"verdict", "plane", "classification", "convergence"} & set(p)
```
Run: `.venv/Scripts/python -m pytest tests/test_triangulation.py -v` → FAIL.

- [ ] **Step 3: Implementar**

`src/fias_ed_engine/triangulation.py`:
```python
"""Triangulação FIAS × QTI: justaposição de evidências, sem classificação automática."""
from .indices import category_counts


def triangulate(intervals: list[int], indices: dict[str, dict], qti_result: dict,
                pedagogical: dict, qti_cfg: dict) -> list[dict]:
    counts = category_counts(intervals)
    total = len(intervals)
    labels = {o["code"]: o["label_pt_br"] for o in qti_cfg["octants"]}
    available = bool(qti_result.get("displayable"))
    out = []
    for pair in pedagogical["triangulation_pairs"]:
        if "index" in pair["fias"]:
            ref = pair["fias"]["index"]
            fias = {"kind": "index", "ref": ref, "value": indices.get(ref, {}).get("value")}
        else:
            cats = pair["fias"]["categories"]
            value = sum(counts[c] for c in cats) / total if total else None
            fias = {"kind": "categories", "ref": cats, "value": value}
        qti = [{"octant": oc, "label": labels[oc],
                "value": qti_result["octants"][oc] if available else None}
               for oc in pair["qti_octants"]]
        out.append({"pair_id": pair["pair_id"], "fias": fias, "qti": qti, "qti_available": available,
                    "reflection_question": pair["reflection_question"],
                    "source_reference": pair["source_reference"],
                    "validation_status": pair["validation_status"]})
    return out
```

Run: `.venv/Scripts/python -m pytest tests/test_triangulation.py tests/test_language.py -v` → PASS (a verificação de linguagem agora cobre as perguntas de reflexão).

- [ ] **Step 4: Commit**
```bash
git add fias-ed-shared/rules/pedagogical_rules.json fias-ed-shared/engine-py
git commit -m "feat(shared): triangulação FIAS×QTI por justaposição de evidências"
```

---

### Task 10: Casos de conformidade e runner

**Files:**
- Create: `fias-ed-shared/conformance/README.md`
- Create: `fias-ed-shared/conformance/cases/*.json` (um arquivo por grupo)
- Create: `fias-ed-shared/scripts/generate_conformance.py`
- Test: `engine-py/tests/test_conformance.py`

**Interfaces:**
- Consumes: todas as funções das Tasks 4–9.
- Produces: formato de caso `{"id": str, "function": str, "description": str, "input": {...}, "expected": ...}`, onde `function` ∈ `segments_to_intervals | transition_matrix | compute_indices | constrain_by_role | score_response | aggregate_qti | evaluate_mtss | triangulate`. Floats comparados com tolerância absoluta `1e-9`. Este é o contrato que o motor Kotlin (subprojeto 3) executará.

- [ ] **Step 1: README do formato**

`conformance/README.md`:
```markdown
# Casos de conformidade FIAS-ED

Cada arquivo em `cases/` contém uma lista de casos:

    {"id": "...", "function": "...", "description": "...", "input": {...}, "expected": ...}

Funções e entradas:

| function | input | expected |
|---|---|---|
| segments_to_intervals | {segments:[{start_ms,end_ms,category}], total_ms} | [int] |
| transition_matrix | {intervals:[int]} | [[int]] 10×10 |
| compute_indices | {intervals, n_segments, confidences} | {id: {value, reason, numerator_count, denominator_count}} |
| constrain_by_role | {logits:[10 floats], role} | {pred_raw, pred_role_constrained, confidence_raw, confidence, uncertain} |
| score_response | {answers:{"1":int..."24":int}} | {octants, agency, communion} |
| aggregate_qti | {responses:[answers]} | {response_count, displayable, octants, agency, communion} |
| evaluate_mtss | {intervals} | [rule_id] (ordem de disparo) |
| triangulate | {intervals, qti_responses:[answers]} | [{pair_id, fias_value, qti_available, qti_values}] |

Regras usadas: sempre os arquivos de `rules/` da mesma versão (`rules_version`).
Floats: tolerância absoluta 1e-9. Chaves de `answers` são strings ("1".."24").
Um motor só é conforme se passar em 100% dos casos.
Os casos QTI foram conferidos contra os testes de `avalie-seu-professor/tests/unit/qtiCalculations.test.ts`.
```

- [ ] **Step 2: Gerador de casos**

`scripts/generate_conformance.py` — define as **entradas** manualmente (lista abaixo) e grava as saídas calculadas pelo motor de referência. As saídas geradas devem ser revisadas uma vez à mão (Step 4) e daí em diante ficam congeladas; qualquer mudança de comportamento aparece como diff no Git.
```python
"""Gera conformance/cases/*.json a partir de entradas definidas aqui e do motor de referência."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.classifier import constrain_by_role  # noqa: E402
from fias_ed_engine.indices import compute_indices  # noqa: E402
from fias_ed_engine.intervals import CodedSegment, segments_to_intervals, transition_matrix  # noqa: E402
from fias_ed_engine.mtss import build_facts, evaluate  # noqa: E402
from fias_ed_engine.paths import CONFORMANCE_DIR  # noqa: E402
from fias_ed_engine.qti import aggregate, score_response  # noqa: E402
from fias_ed_engine.rules import load_rules  # noqa: E402
from fias_ed_engine.triangulation import triangulate  # noqa: E402

F, Q, M, P = (load_rules(n) for n in ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules"))


def ans(fn):
    return {str(i): fn(i) for i in range(1, 25)}


def to_int_keys(a):
    return {int(k): v for k, v in a.items()}


SEGMENT_CASES = [
    ("seg-empty", "Áudio sem fala vira silêncio", [], 9000),
    ("seg-partial-last", "Último intervalo parcial conta", [], 7000),
    ("seg-largest", "Maior cobertura vence", [(0, 1000, 5), (1000, 3000, 4)], 3000),
    ("seg-tie", "Empate: segmento que começa antes", [(0, 1500, 5), (1500, 3000, 8)], 3000),
    ("seg-span", "Segmento cobrindo vários intervalos", [(500, 7000, 5)], 9000),
    ("seg-gap", "Intervalo sem fala = 10", [(0, 3000, 4), (6000, 9000, 8)], 9000),
    ("seg-unsorted", "Entrada fora de ordem", [(6000, 9000, 8), (0, 3000, 4)], 9000),
]
INTERVAL_SEQS = [
    ("lesson-expositive", [5, 5, 5, 4, 8, 8, 10]),
    ("lesson-dialogic", [4, 8, 3, 9, 2, 4, 8, 3, 10]),
    ("lesson-teacher-only-indirect", [4, 4, 10]),
    ("lesson-empty", []),
    ("lesson-reactive", [5, 7, 6, 7, 8, 10]),
]
LOGIT_CASES = [
    ("role-agree", [0, 0, 0, 0, 5, 0, 0, 0, 0, 0], "PROFESSOR"),
    ("role-teacher-diverge", [0, 0, 4, 0, 0, 0, 0, 5, 0, 0], "PROFESSOR"),
    ("role-student-diverge", [0, 0, 0, 0, 5, 0, 0, 0, 4, 0], "ALUNO"),
    ("role-flat-uncertain", [0.0] * 10, "PROFESSOR"),
]
QTI_ANSWERS = [
    ("qti-all-1", ans(lambda i: 1)),
    ("qti-all-5", ans(lambda i: 5)),
    ("qti-all-3", ans(lambda i: 3)),
    ("qti-only-oc1", ans(lambda i: 5 if i in (1, 9, 17) else 1)),
    ("qti-only-oc6", ans(lambda i: 5 if i in (6, 14, 22) else 1)),
    ("qti-spss-hand", ans(lambda i: {1: 5, 2: 3, 3: 2, 4: 1, 5: 1, 6: 2, 7: 3, 8: 5}[(i - 1) % 8 + 1])),
]


def main() -> None:
    out_dir = CONFORMANCE_DIR / "cases"
    out_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list] = {k: [] for k in ("intervals", "matrix", "indices", "classifier", "qti", "mtss", "triangulation")}
    for cid, desc, segs, total in SEGMENT_CASES:
        inp = {"segments": [{"start_ms": a, "end_ms": b, "category": c} for a, b, c in segs], "total_ms": total}
        exp = segments_to_intervals([CodedSegment(a, b, c) for a, b, c in segs], total, F)
        groups["intervals"].append({"id": cid, "function": "segments_to_intervals", "description": desc, "input": inp, "expected": exp})
    for cid, iv in INTERVAL_SEQS:
        groups["matrix"].append({"id": f"matrix-{cid}", "function": "transition_matrix", "description": cid, "input": {"intervals": iv}, "expected": transition_matrix(iv, F)})
        idx = compute_indices(iv, F, n_segments=len(iv), confidences=[0.8] * len(iv))
        groups["indices"].append({"id": f"indices-{cid}", "function": "compute_indices", "description": cid,
            "input": {"intervals": iv, "n_segments": len(iv), "confidences": [0.8] * len(iv)},
            "expected": {k: {f: v[f] for f in ("value", "reason", "numerator_count", "denominator_count")} for k, v in idx.items()}})
        fired = evaluate(build_facts(iv, compute_indices(iv, F)), M)
        groups["mtss"].append({"id": f"mtss-{cid}", "function": "evaluate_mtss", "description": cid, "input": {"intervals": iv}, "expected": [f["rule_id"] for f in fired]})
    for cid, lg, role in LOGIT_CASES:
        r = constrain_by_role(lg, role, F)
        groups["classifier"].append({"id": cid, "function": "constrain_by_role", "description": cid, "input": {"logits": lg, "role": role},
            "expected": {"pred_raw": r.pred_raw, "pred_role_constrained": r.pred_role_constrained, "confidence_raw": r.confidence_raw, "confidence": r.confidence, "uncertain": r.uncertain}})
    for cid, a in QTI_ANSWERS:
        groups["qti"].append({"id": cid, "function": "score_response", "description": cid, "input": {"answers": a}, "expected": score_response(to_int_keys(a), Q)})
    for cid, n in (("qti-agg-below-min", 3), ("qti-agg-min", 10)):
        responses = [QTI_ANSWERS[2][1]] * (n - 1) + [QTI_ANSWERS[3][1]]
        groups["qti"].append({"id": cid, "function": "aggregate_qti", "description": cid, "input": {"responses": responses},
            "expected": aggregate([to_int_keys(r) for r in responses], Q)})
    for cid, iv in INTERVAL_SEQS[:2]:
        for qn in (3, 10):
            responses = [QTI_ANSWERS[2][1]] * qn
            tri = triangulate(iv, compute_indices(iv, F), aggregate([to_int_keys(r) for r in responses], Q), P, Q)
            groups["triangulation"].append({"id": f"tri-{cid}-{qn}", "function": "triangulate", "description": f"{cid} com {qn} respostas QTI",
                "input": {"intervals": iv, "qti_responses": responses},
                "expected": [{"pair_id": t["pair_id"], "fias_value": t["fias"]["value"], "qti_available": t["qti_available"], "qti_values": [q["value"] for q in t["qti"]]} for t in tri]})
    meta = {"rules_version": F["rules_version"]}
    for name, cases in groups.items():
        (out_dir / f"{name}.json").write_text(json.dumps({**meta, "cases": cases}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {len(cases)} casos")


if __name__ == "__main__":
    main()
```

Run (de `fias-ed-shared`): `engine-py/.venv/Scripts/python scripts/generate_conformance.py` → 7 arquivos.

- [ ] **Step 3: Runner (teste)**

`tests/test_conformance.py`:
```python
import json
import math

import pytest

from fias_ed_engine.classifier import constrain_by_role
from fias_ed_engine.indices import compute_indices
from fias_ed_engine.intervals import CodedSegment, segments_to_intervals, transition_matrix
from fias_ed_engine.mtss import build_facts, evaluate
from fias_ed_engine.paths import CONFORMANCE_DIR
from fias_ed_engine.qti import aggregate, score_response
from fias_ed_engine.rules import load_rules
from fias_ed_engine.triangulation import triangulate

F, Q, M, P = (load_rules(n) for n in ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules"))


def _ik(a):
    return {int(k): v for k, v in a.items()}


def run(fn, i):
    if fn == "segments_to_intervals":
        return segments_to_intervals([CodedSegment(**s) for s in i["segments"]], i["total_ms"], F)
    if fn == "transition_matrix":
        return transition_matrix(i["intervals"], F)
    if fn == "compute_indices":
        r = compute_indices(i["intervals"], F, i["n_segments"], i["confidences"])
        return {k: {f: v[f] for f in ("value", "reason", "numerator_count", "denominator_count")} for k, v in r.items()}
    if fn == "constrain_by_role":
        r = constrain_by_role(i["logits"], i["role"], F)
        return {"pred_raw": r.pred_raw, "pred_role_constrained": r.pred_role_constrained,
                "confidence_raw": r.confidence_raw, "confidence": r.confidence, "uncertain": r.uncertain}
    if fn == "score_response":
        return score_response(_ik(i["answers"]), Q)
    if fn == "aggregate_qti":
        return aggregate([_ik(r) for r in i["responses"]], Q)
    if fn == "evaluate_mtss":
        return [f["rule_id"] for f in evaluate(build_facts(i["intervals"], compute_indices(i["intervals"], F)), M)]
    if fn == "triangulate":
        iv = i["intervals"]
        tri = triangulate(iv, compute_indices(iv, F), aggregate([_ik(r) for r in i["qti_responses"]], Q), P, Q)
        return [{"pair_id": t["pair_id"], "fias_value": t["fias"]["value"], "qti_available": t["qti_available"],
                 "qti_values": [q["value"] for q in t["qti"]]} for t in tri]
    raise AssertionError(f"função desconhecida {fn}")


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, abs_tol=1e-9)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


CASES = [(p.stem, c) for p in sorted((CONFORMANCE_DIR / "cases").glob("*.json"))
         for c in json.loads(p.read_text(encoding="utf-8"))["cases"]]


def test_cases_exist_for_every_function():
    fns = {c["function"] for _, c in CASES}
    assert fns == {"segments_to_intervals", "transition_matrix", "compute_indices", "constrain_by_role",
                   "score_response", "aggregate_qti", "evaluate_mtss", "triangulate"}


@pytest.mark.parametrize("group,case", CASES, ids=[c["id"] for _, c in CASES])
def test_case(group, case):
    assert same(run(case["function"], case["input"]), case["expected"])


def test_cases_rules_version_matches():
    for p in (CONFORMANCE_DIR / "cases").glob("*.json"):
        assert json.loads(p.read_text(encoding="utf-8"))["rules_version"] == F["rules_version"]
```

Run: `.venv/Scripts/python -m pytest tests/test_conformance.py -v` → PASS (todos os casos).

- [ ] **Step 4: Revisão manual dos esperados**

Abrir `conformance/cases/intervals.json`, `qti.json`, `mtss.json` e conferir à mão:
- `seg-tie` → `[5]`; `seg-gap` → `[4, 10, 8]`; `seg-unsorted` → `[4, 10, 8]`.
- `qti-only-oc1` → agency ≈ 0.353553 (b·a), communion ≈ 0.146446 (b·b).
- `mtss-lesson-expositive` → `["MTSS_EXPOSITIVE_PREDOMINANCE","MTSS_DIRECT_OVER_INDIRECT","MTSS_NO_STUDENT_INITIATIVE","MTSS_NO_IDEA_UPTAKE","MTSS_NO_PRAISE","MTSS_QUESTIONS_PRESENT"]`.
- `mtss-lesson-reactive` contém `MTSS_REACTIVE_MANAGEMENT_PRESENT`.
Se algo divergir, o erro está no motor: corrigir o motor (com teste unitário), regenerar, revisar de novo.

- [ ] **Step 5: Commit**
```bash
git add fias-ed-shared/conformance fias-ed-shared/scripts/generate_conformance.py fias-ed-shared/engine-py/tests/test_conformance.py
git commit -m "test(shared): casos de conformidade compartilhados Web/Android"
```

---

### Task 11: Schemas das entidades (modelo lógico compartilhado)

**Files:**
- Create: `fias-ed-shared/schemas/entities/_base.schema.json`
- Create: `fias-ed-shared/schemas/entities/<entidade>.schema.json` × 20
- Create: `fias-ed-shared/schemas/entities/examples/<entidade>.json` × 20
- Test: `engine-py/tests/test_entities.py`

**Interfaces:**
- Produces: um schema por entidade, todos com `allOf: [{"$ref": "_base.schema.json"}, {...}]`, `$id` = `https://fias-ed.local/schemas/entities/<nome>.schema.json`, `unevaluatedProperties: false`. Chaves estrangeiras terminam em `_id` (formato uuid). Nomes de entidade em snake_case: `professor, escola, turma, disciplina, aula, audio, transcricao, segmento, falante, classificacao_fias, indicador_fias, questionario_qti, resposta_qti, resultado_qti, triangulacao, resultado_mtss, recomendacao, relatorio, processamento, modelo_ia`.

- [ ] **Step 1: Base**

`_base.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/entities/_base.schema.json",
  "type": "object",
  "required": ["id", "created_at", "updated_at", "deleted_at", "version", "sync_status", "device_id"],
  "properties": {
    "id": {"type": "string", "format": "uuid"},
    "created_at": {"type": "string", "format": "date-time"},
    "updated_at": {"type": "string", "format": "date-time"},
    "deleted_at": {"type": ["string", "null"], "format": "date-time"},
    "version": {"type": "integer", "minimum": 1},
    "sync_status": {"enum": ["LOCAL_ONLY", "PENDING_SYNC", "SYNCED", "CONFLICT"]},
    "device_id": {"type": "string", "minLength": 1}
  }
}
```

- [ ] **Step 2: Schemas das 20 entidades**

Cada arquivo segue exatamente este molde (exemplo `audio.schema.json`); os campos específicos de cada entidade estão na tabela abaixo. `format: uuid` para todo `*_id`; strings de texto livre com `maxLength` indicado; enums conforme a tabela.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/entities/audio.schema.json",
  "title": "Audio",
  "allOf": [{"$ref": "_base.schema.json"}, {
    "type": "object",
    "required": ["aula_id", "original_filename", "internal_filename", "path", "mime_type", "size_bytes", "duration_ms", "sha256", "channels", "sample_rate", "is_original"],
    "properties": {
      "aula_id": {"type": "string", "format": "uuid"},
      "original_filename": {"type": "string", "maxLength": 255},
      "internal_filename": {"type": "string", "pattern": "^[0-9a-f-]{36}\\.[a-z0-9]{2,5}$"},
      "path": {"type": "string", "maxLength": 1024},
      "mime_type": {"enum": ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac", "audio/flac", "audio/x-flac"]},
      "size_bytes": {"type": "integer", "minimum": 1},
      "duration_ms": {"type": "integer", "minimum": 1},
      "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
      "channels": {"type": "integer", "minimum": 1},
      "sample_rate": {"type": "integer", "minimum": 8000},
      "is_original": {"type": "boolean"},
      "derived_from_audio_id": {"type": ["string", "null"], "format": "uuid"}
    }
  }],
  "unevaluatedProperties": false
}
```

| Entidade | Campos obrigatórios (tipo) | Opcionais |
|---|---|---|
| professor | display_name (str ≤120), role (`ADMIN_LOCAL`\|`PROFESSOR`) | username (str ≤64, só Web) |
| escola | name (str ≤200) | municipality (str ≤120), region (`Norte`\|`Nordeste`\|`Centro-Oeste`\|`Sudeste`\|`Sul`) |
| turma | escola_id, professor_id, name (str ≤120) | school_year (int), level (str ≤60) |
| disciplina | professor_id, name (str ≤120) | |
| aula | professor_id, turma_id, disciplina_id, lesson_date (format date), status (enum dos 17 status do spec §9) | note (str ≤2000), error_code (str ≤64) |
| audio | ver molde acima | |
| transcricao | aula_id, audio_id, language (`pt-BR`), asr_model_id | |
| segmento | transcricao_id, falante_id, start_ms (int ≥0), end_ms (int ≥1), texto_original_asr (str ≤10000), texto_revisado (str\|null ≤10000), revisado (bool) | asr_confidence (number 0–1) |
| falante | transcricao_id, diarization_label (str ≤32, ex. `SPEAKER_00`), role (`PROFESSOR`\|`ALUNO`\|`UNASSIGNED`) | |
| classificacao_fias | segmento_id, transcript_source (`ASR_ORIGINAL`\|`TRANSCRICAO_REVISADA`), pred_raw (int 1–10), pred_role_constrained (int 1–10), confidence_raw (0–1), confidence (0–1), uncertain (bool), model_id, rules_version | |
| indicador_fias | aula_id, index_id (str), value (number\|null), reason (null\|`insufficient_data`), numerator_count (int), denominator_count (int), n_intervals (int), rules_version, validation_status | mean_confidence (number\|null) |
| questionario_qti | aula_id, instrument_version (str), source (`IMPORT_AVALIE_SEU_PROFESSOR`\|`FORM`\|`MANUAL`\|`OCR`), confirmed (bool) | import_filename (str ≤255) |
| resposta_qti | questionario_qti_id, answers (object com chaves `"1"`..`"24"`, valores int 1–5, `minProperties: 24`, `maxProperties: 24`) | ocr_confidence (0–1) |
| resultado_qti | questionario_qti_id, response_count (int), displayable (bool), octants (object oc1..oc8 number\|null), agency (number\|null), communion (number\|null), rules_version | |
| triangulacao | aula_id, pairs (array de `{pair_id, fias_value, qti_available, qti_values}`), rules_version | |
| resultado_mtss | aula_id, fired_rules (array de `{rule_id, tier1_dimension, framing, evidence}`), rules_version | |
| recomendacao | resultado_mtss_id, recommendation_id, rule_id, text (str ≤2000), validation_status | |
| relatorio | aula_id, status (`DRAFT`\|`READY`), rules_version, app_version | pdf_path (str ≤1024), pdf_sha256 (sha256) |
| processamento | aula_id, app_version, rules_version, asr_model, asr_model_hash, diarization_model, fias_model, fias_model_hash, parameters (object), hardware (str ≤200), device (str ≤200), audio_duration_ms (int), transcript_source, stage_times_ms (object), status (mesmo enum de aula) | processing_time_ms (int), role_divergence_rate (number\|null), error_code (str ≤64) |
| modelo_ia | model_id (str), name, version, task, format (`safetensors`\|`onnx`\|`ggml`\|`other`), sha256, size_bytes, source (str ≤500), license (str ≤200), parameters (object) | |

`processamento.status` e `aula.status` usam o enum: `DRAFT, AUDIO_IMPORTED, AUDIO_VALIDATED, PREPROCESSING, TRANSCRIBING, TRANSCRIBED, DIARIZING, READY_FOR_SPEAKER_REVIEW, READY_FOR_TRANSCRIPT_REVIEW, READY_FOR_FIAS, FIAS_COMPLETED, WAITING_QTI, QTI_COMPLETED, TRIANGULATED, MTSS_INTERPRETED, REPORT_READY, ERROR`.

**Privacidade por construção:** nenhum schema tem campo para nome de aluno, embedding de voz, CPF, e-mail ou áudio em BLOB (`unevaluatedProperties: false` impede acréscimo).

- [ ] **Step 3: Exemplos válidos**

Para cada entidade, `examples/<entidade>.json` com uma instância válida. Base comum dos exemplos:
```json
{"id": "01926b3e-7a1c-7c3e-9f00-000000000001", "created_at": "2026-09-21T10:00:00Z", "updated_at": "2026-09-21T10:00:00Z", "deleted_at": null, "version": 1, "sync_status": "LOCAL_ONLY", "device_id": "web-local"}
```
mais os campos obrigatórios da tabela (usar `01926b3e-7a1c-7c3e-9f00-0000000000NN` com NN distinto para cada `*_id`).

- [ ] **Step 4: Teste**

`tests/test_entities.py`:
```python
import json

import jsonschema
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from fias_ed_engine.paths import SCHEMAS_DIR

ENT = SCHEMAS_DIR / "entities"
NAMES = ["professor", "escola", "turma", "disciplina", "aula", "audio", "transcricao", "segmento", "falante",
         "classificacao_fias", "indicador_fias", "questionario_qti", "resposta_qti", "resultado_qti",
         "triangulacao", "resultado_mtss", "recomendacao", "relatorio", "processamento", "modelo_ia"]


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


REG = Registry().with_resources((_load(p)["$id"], Resource.from_contents(_load(p))) for p in ENT.glob("*.schema.json"))


def validator(name):
    return Draft202012Validator(_load(ENT / f"{name}.schema.json"), registry=REG, format_checker=FormatChecker())


def test_all_twenty_present():
    assert sorted(p.name.removesuffix(".schema.json") for p in ENT.glob("*.schema.json") if not p.name.startswith("_")) == sorted(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_schema_valid_and_example_validates(name):
    Draft202012Validator.check_schema(_load(ENT / f"{name}.schema.json"))
    validator(name).validate(_load(ENT / "examples" / f"{name}.json"))


@pytest.mark.parametrize("name", NAMES)
def test_rejects_unknown_field(name):
    ex = _load(ENT / "examples" / f"{name}.json") | {"student_name": "Fulano"}
    with pytest.raises(jsonschema.ValidationError):
        validator(name).validate(ex)


def test_base_fields_required():
    ex = _load(ENT / "examples" / "aula.json")
    del ex["sync_status"]
    with pytest.raises(jsonschema.ValidationError):
        validator("aula").validate(ex)


def test_no_sensitive_fields_anywhere():
    forbidden = {"student_name", "nome_aluno", "cpf", "email", "voice_embedding", "embedding", "audio_blob", "blob"}
    for p in ENT.glob("*.schema.json"):
        assert not forbidden & set(json.dumps(_load(p)).replace('"', " ").split()), p.name
```

Run: `.venv/Scripts/python -m pytest tests/test_entities.py -v` → PASS (62 testes).

Nota: `format: uuid`/`date-time` só são checados com `FormatChecker`; `jsonschema` valida `uuid` nativamente e `date-time` exige o extra `rfc3339-validator` — adicionar `"jsonschema[format-nongpl]>=4.23,<5"` em `dependencies` do pyproject e reinstalar (`pip install -e ".[dev,tools]"`).

- [ ] **Step 5: Commit**
```bash
git add fias-ed-shared/schemas/entities fias-ed-shared/engine-py
git commit -m "feat(shared): schemas das 20 entidades com UUID e campos de sincronização"
```

---

### Task 11B: Exportação do dataset da(s) aula(s)

**Files:**
- Create: `fias-ed-shared/schemas/export/lesson_dataset.schema.json`
- Create: `engine-py/src/fias_ed_engine/export.py`
- Test: `engine-py/tests/test_export.py`

**Interfaces:**
- Consumes: `segments_to_intervals`, `transition_matrix` (Task 4); `compute_indices` (Task 6); `score_response`/`aggregate` (Task 5); `build_facts`/`evaluate`/`recommendations` (Task 8); `triangulate` (Task 9); `load_rules`.
- Produces:
  - `EXPORT_VERSION = "1.0.0"`; `TABLES: tuple[str, ...]` = `("lessons","segments","intervals","matrix","indices","qti_responses","qti_results","mtss","recommendations","triangulation")`.
  - `class ExportPrivacyError(ValueError)`.
  - `build_dataset(lessons: list[dict], include_text: bool, exported_at: str) -> dict` — retorna `{"manifest": {...}, "<tabela>": [linhas]}`. Cada `lesson` de entrada:
    ```
    {"lesson": {"lesson_id", "lesson_date", "disciplina", "turma_id", "duration_ms", "transcript_source"},
     "segments": [{"segment_id", "start_ms", "end_ms", "role", "pred_raw", "pred_role_constrained",
                   "confidence", "uncertain", "text_pseudonymized"?}],
     "qti_responses": [{"1": int, ..., "24": int}],
     "processing": {"app_version", "fias_model", "fias_model_hash", "asr_model", "asr_model_hash", "diarization_model"}}
    ```
  - `to_json(dataset) -> str`; `to_csv_files(dataset) -> dict[str, str]` (`"<tabela>.csv"` → conteúdo); `write_zip(dataset, path: Path) -> None` (CSVs + `manifest.json` com `files: {nome: sha256}`).

- [ ] **Step 1: Schema do JSON exportado**

`schemas/export/lesson_dataset.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fias-ed.local/schemas/export/lesson_dataset.schema.json",
  "type": "object",
  "required": ["manifest", "lessons", "segments", "intervals", "matrix", "indices", "qti_responses", "qti_results", "mtss", "recommendations", "triangulation"],
  "additionalProperties": false,
  "properties": {
    "manifest": {"type": "object", "required": ["export_version", "rules_version", "exported_at", "include_text", "lesson_count", "processing"],
      "properties": {"include_text": {"type": "boolean"}, "lesson_count": {"type": "integer", "minimum": 1}}},
    "lessons": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "lesson_date", "disciplina", "turma_id", "duration_ms", "transcript_source", "n_segments", "n_intervals", "rules_version"],
      "properties": {"lesson_id": {"type": "string", "format": "uuid"}, "lesson_date": {"type": "string", "format": "date"},
        "disciplina": {"type": "string"}, "turma_id": {"type": "string", "format": "uuid"},
        "duration_ms": {"type": "integer"}, "transcript_source": {"enum": ["ASR_ORIGINAL", "TRANSCRICAO_REVISADA"]},
        "n_segments": {"type": "integer"}, "n_intervals": {"type": "integer"}, "rules_version": {"type": "string"}}}},
    "segments": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "segment_id", "start_ms", "end_ms", "role", "pred_raw", "pred_role_constrained", "confidence", "uncertain"],
      "properties": {"lesson_id": {"type": "string"}, "segment_id": {"type": "string"}, "start_ms": {"type": "integer"}, "end_ms": {"type": "integer"},
        "role": {"enum": ["PROFESSOR", "ALUNO"]}, "pred_raw": {"type": "integer"}, "pred_role_constrained": {"type": "integer"},
        "confidence": {"type": "number"}, "uncertain": {"type": "boolean"}, "text_pseudonymized": {"type": "string"}}}},
    "intervals": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "interval_index", "start_ms", "category"]}},
    "matrix": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "from_category", "to_category", "count"]}},
    "indices": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "index_id", "value", "reason", "numerator_count", "denominator_count", "validation_status"]}},
    "qti_responses": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "response_index"], "patternProperties": {"^q([1-9]|1[0-9]|2[0-4])$": {"type": "integer", "minimum": 1, "maximum": 5}},
      "properties": {"lesson_id": {"type": "string"}, "response_index": {"type": "integer"}}}},
    "qti_results": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "response_count", "displayable", "agency", "communion"],
      "patternProperties": {"^oc[1-8]$": {"type": ["number", "null"]}},
      "properties": {"lesson_id": {"type": "string"}, "response_count": {"type": "integer"}, "displayable": {"type": "boolean"},
        "agency": {"type": ["number", "null"]}, "communion": {"type": ["number", "null"]}}}},
    "mtss": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "rule_id", "tier1_dimension", "framing", "validation_status", "rules_version"]}},
    "recommendations": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "recommendation_id", "rule_id", "validation_status"]}},
    "triangulation": {"type": "array", "items": {"type": "object", "additionalProperties": false,
      "required": ["lesson_id", "pair_id", "fias_value", "qti_available", "qti_values"]}}
  }
}
```

- [ ] **Step 2: Testes falhando**

`tests/test_export.py`:
```python
import csv
import hashlib
import io
import json
import zipfile

import jsonschema
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from fias_ed_engine.export import TABLES, ExportPrivacyError, build_dataset, to_csv_files, to_json, write_zip
from fias_ed_engine.paths import SCHEMAS_DIR

SCHEMA = json.loads((SCHEMAS_DIR / "export" / "lesson_dataset.schema.json").read_text(encoding="utf-8"))
PROC = {"app_version": "web-0.1.0", "fias_model": "fias-bertimbau-ptbr-frente3", "fias_model_hash": "625d32a2",
        "asr_model": "faster-whisper-small", "asr_model_hash": "x", "diarization_model": "pyannote"}


def lesson(lid="01926b3e-7a1c-7c3e-9f00-000000000001", text=True):
    segs = [
        {"segment_id": "s1", "start_ms": 0, "end_ms": 3000, "role": "PROFESSOR", "pred_raw": 4, "pred_role_constrained": 4, "confidence": 0.9, "uncertain": False},
        {"segment_id": "s2", "start_ms": 3000, "end_ms": 6000, "role": "ALUNO", "pred_raw": 8, "pred_role_constrained": 8, "confidence": 0.8, "uncertain": False},
    ]
    if text:
        segs[0]["text_pseudonymized"] = "[NOME], quanto é três vezes quatro?"
        segs[1]["text_pseudonymized"] = "Doze."
    return {"lesson": {"lesson_id": lid, "lesson_date": "2026-09-21", "disciplina": "Matemática",
                       "turma_id": "01926b3e-7a1c-7c3e-9f00-000000000099", "duration_ms": 9000,
                       "transcript_source": "TRANSCRICAO_REVISADA"},
            "segments": segs, "qti_responses": [{str(i): 3 for i in range(1, 25)}] * 10, "processing": PROC}


def validate(ds):
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(ds)


def test_default_export_has_no_text():
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert all("text_pseudonymized" not in s for s in ds["segments"])
    assert "Doze" not in to_json(ds)


def test_include_text_uses_pseudonymized_only():
    ds = build_dataset([lesson()], include_text=True, exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert ds["segments"][0]["text_pseudonymized"].startswith("[NOME]")
    assert ds["manifest"]["include_text"] is True


def test_include_text_refused_without_pseudonymization():
    with pytest.raises(ExportPrivacyError):
        build_dataset([lesson(text=False)], include_text=True, exported_at="2026-09-21T12:00:00Z")


def test_derived_tables_consistent_with_engine():
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    assert [r["category"] for r in ds["intervals"]] == [4, 8, 10]
    by = {r["index_id"]: r for r in ds["indices"]}
    assert by["TT"]["value"] == pytest.approx(1 / 3)
    assert ds["qti_results"][0]["displayable"] is True
    assert len(ds["qti_responses"]) == 10 and ds["qti_responses"][0]["q24"] == 3
    assert sum(r["count"] for r in ds["matrix"]) == 4
    assert {r["pair_id"] for r in ds["triangulation"]} >= {"TRI_WARMTH"}


def test_multiple_lessons():
    ds = build_dataset([lesson(), lesson(lid="01926b3e-7a1c-7c3e-9f00-000000000002")], include_text=False,
                       exported_at="2026-09-21T12:00:00Z")
    validate(ds)
    assert ds["manifest"]["lesson_count"] == 2
    assert {r["lesson_id"] for r in ds["segments"]} == {"01926b3e-7a1c-7c3e-9f00-000000000001", "01926b3e-7a1c-7c3e-9f00-000000000002"}


def test_never_exports_sensitive_fields():
    raw = lesson()
    raw["lesson"]["professor_name"] = "Fulano"
    raw["segments"][0]["texto_original_asr"] = "Maria, quanto é três vezes quatro?"
    raw["processing"]["audio_path"] = "C:/audio.wav"
    text = to_json(build_dataset([raw], include_text=True, exported_at="2026-09-21T12:00:00Z"))
    for leak in ("Fulano", "Maria", "audio.wav", "professor_name", "texto_original_asr", "audio_path"):
        assert leak not in text


def test_empty_export_rejected():
    with pytest.raises(ValueError):
        build_dataset([], include_text=False, exported_at="2026-09-21T12:00:00Z")


def test_csv_and_zip(tmp_path):
    ds = build_dataset([lesson()], include_text=False, exported_at="2026-09-21T12:00:00Z")
    files = to_csv_files(ds)
    assert set(files) == {f"{t}.csv" for t in TABLES}
    rows = list(csv.DictReader(io.StringIO(files["segments.csv"])))
    assert rows[0]["segment_id"] == "s1"
    out = tmp_path / "aulas.zip"
    write_zip(ds, out)
    with zipfile.ZipFile(out) as z:
        manifest = json.loads(z.read("manifest.json"))
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(z.read(name)).hexdigest() == digest
```
Run: `.venv/Scripts/python -m pytest tests/test_export.py -v` → FAIL.

- [ ] **Step 3: Implementar**

`src/fias_ed_engine/export.py`:
```python
"""Exportação do dataset de uma ou mais aulas (JSON e ZIP de CSVs). Sem áudio, sem texto por padrão."""
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from .indices import compute_indices
from .intervals import CodedSegment, segments_to_intervals, transition_matrix
from .mtss import build_facts, evaluate, recommendations
from .qti import aggregate
from .rules import load_rules
from .triangulation import triangulate

EXPORT_VERSION = "1.0.0"
TABLES = ("lessons", "segments", "intervals", "matrix", "indices", "qti_responses",
          "qti_results", "mtss", "recommendations", "triangulation")
_LESSON_FIELDS = ("lesson_id", "lesson_date", "disciplina", "turma_id", "duration_ms", "transcript_source")
_SEGMENT_FIELDS = ("segment_id", "start_ms", "end_ms", "role", "pred_raw", "pred_role_constrained", "confidence", "uncertain")
_PROCESSING_FIELDS = ("app_version", "fias_model", "fias_model_hash", "asr_model", "asr_model_hash", "diarization_model")


class ExportPrivacyError(ValueError):
    pass


def build_dataset(lessons: list[dict], include_text: bool, exported_at: str) -> dict:
    if not lessons:
        raise ValueError("Nenhuma aula selecionada para exportação.")
    F, Q, M, P = (load_rules(n) for n in ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules"))
    step = int(F["coding"]["interval_seconds"] * 1000)
    ds: dict = {t: [] for t in TABLES}
    processing = []
    for item in lessons:
        meta, segs = item["lesson"], item["segments"]
        lid = meta["lesson_id"]
        if include_text and any(not s.get("text_pseudonymized") for s in segs):
            raise ExportPrivacyError(f"Aula {lid}: há falas sem versão pseudonimizada; exportação com texto recusada.")
        coded = [CodedSegment(s["start_ms"], s["end_ms"], s["pred_role_constrained"]) for s in segs]
        intervals = segments_to_intervals(coded, meta["duration_ms"], F)
        indices = compute_indices(intervals, F, n_segments=len(segs), confidences=[s["confidence"] for s in segs])
        answers = [{int(k): v for k, v in r.items()} for r in item["qti_responses"]]
        qti = aggregate(answers, Q)
        fired = evaluate(build_facts(intervals, indices), M)

        ds["lessons"].append({**{f: meta[f] for f in _LESSON_FIELDS}, "n_segments": len(segs),
                              "n_intervals": len(intervals), "rules_version": F["rules_version"]})
        for s in segs:
            row = {"lesson_id": lid, **{f: s[f] for f in _SEGMENT_FIELDS}}
            if include_text:
                row["text_pseudonymized"] = s["text_pseudonymized"]
            ds["segments"].append(row)
        ds["intervals"] += [{"lesson_id": lid, "interval_index": i, "start_ms": i * step, "category": c}
                            for i, c in enumerate(intervals)]
        m = transition_matrix(intervals, F)
        ds["matrix"] += [{"lesson_id": lid, "from_category": a + 1, "to_category": b + 1, "count": m[a][b]}
                         for a in range(10) for b in range(10) if m[a][b]]
        ds["indices"] += [{"lesson_id": lid, "index_id": k, "value": v["value"], "reason": v["reason"],
                           "numerator_count": v["numerator_count"], "denominator_count": v["denominator_count"],
                           "validation_status": v["validation_status"]} for k, v in indices.items()]
        ds["qti_responses"] += [{"lesson_id": lid, "response_index": n, **{f"q{i}": a[i] for i in range(1, 25)}}
                                for n, a in enumerate(answers)]
        ds["qti_results"].append({"lesson_id": lid, "response_count": qti["response_count"], "displayable": qti["displayable"],
                                  **{f"oc{i}": (qti["octants"] or {}).get(f"oc{i}") for i in range(1, 9)},
                                  "agency": qti["agency"], "communion": qti["communion"]})
        ds["mtss"] += [{"lesson_id": lid, "rule_id": f["rule_id"], "tier1_dimension": f["tier1_dimension"],
                        "framing": f["framing"], "validation_status": f["validation_status"],
                        "rules_version": f["rules_version"]} for f in fired]
        ds["recommendations"] += [{"lesson_id": lid, "recommendation_id": r["recommendation_id"], "rule_id": r["rule_id"],
                                   "validation_status": r["validation_status"]} for r in recommendations(fired, P)]
        ds["triangulation"] += [{"lesson_id": lid, "pair_id": t["pair_id"], "fias_value": t["fias"]["value"],
                                 "qti_available": t["qti_available"], "qti_values": [q["value"] for q in t["qti"]]}
                                for t in triangulate(intervals, indices, qti, P, Q)]
        processing.append({"lesson_id": lid, **{f: item["processing"].get(f) for f in _PROCESSING_FIELDS}})
    ds["manifest"] = {"export_version": EXPORT_VERSION, "rules_version": F["rules_version"], "exported_at": exported_at,
                      "include_text": include_text, "lesson_count": len(lessons), "processing": processing}
    return ds


def to_json(dataset: dict) -> str:
    return json.dumps(dataset, ensure_ascii=False, indent=2)


def _cell(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else ("" if v is None else v)


def to_csv_files(dataset: dict) -> dict[str, str]:
    files = {}
    for t in TABLES:
        rows = dataset[t]
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows({k: _cell(v) for k, v in r.items()} for r in rows)
        files[f"{t}.csv"] = buf.getvalue()
    return files


def write_zip(dataset: dict, path: Path) -> None:
    files = to_csv_files(dataset)
    manifest = {**dataset["manifest"],
                "files": {n: hashlib.sha256(c.encode("utf-8")).hexdigest() for n, c in files.items()}}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content.encode("utf-8"))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
```

Nota: `segments.csv` tem colunas iguais em todas as linhas (mesmo `include_text` para o lote inteiro), então o cabeçalho da primeira linha serve para todas.

Run: `.venv/Scripts/python -m pytest tests/test_export.py -v` → PASS (8 testes).

- [ ] **Step 4: Commit**
```bash
git add fias-ed-shared/schemas/export fias-ed-shared/engine-py
git commit -m "feat(shared): exportação do dataset de aulas (JSON e ZIP de CSVs), sem texto por padrão"
```

---

### Task 12: Design tokens, fontes locais e geração CSS/Kotlin

**Files:**
- Create: `fias-ed-shared/design-tokens/tokens.json`
- Create: `fias-ed-shared/scripts/build_tokens.py`
- Create: `fias-ed-shared/scripts/fetch_fonts.py`
- Create: `fias-ed-shared/design-tokens/fonts/` (TTF + WOFF2 + licenças + `manifest.json`)
- Create (gerados): `design-tokens/build/tokens.css`, `design-tokens/build/FiasTokens.kt`
- Test: `engine-py/tests/test_tokens.py`

**Interfaces:**
- Produces: variáveis CSS `--color-*`, `--font-interface`, `--font-editorial`, `--space-*`, `--radius-*`, `--border-*`; objeto Kotlin `FiasTokens` (pacote `br.ufersa.fiased.designsystem`) com `Color`s e dimensões. `build_tokens.contrast(fg: str, bg: str) -> float`.

- [ ] **Step 1: `tokens.json`**

```json
{
  "tokens_version": "1.0.0",
  "color": {
    "brand": {
      "navy": "#2F4156", "teal": "#567C8D", "sky": "#C8D9E6", "beige": "#F5EFEB", "white": "#FFFFFF"
    },
    "semantic": {
      "error": "#9B3B3B", "success": "#3E6B4F", "warning": "#7A5512", "info": "#3F6A8A", "muted": "#5B6673"
    },
    "role": {
      "text": "navy", "text-muted": "muted", "link": "teal", "surface": "white", "surface-alt": "beige",
      "surface-info": "sky", "border": "sky", "action-primary": "navy", "action-secondary": "teal"
    },
    "fias_groups": {"indirect": "teal", "direct": "navy", "student": "sky", "silence": "beige"}
  },
  "text_pairs": [
    ["navy", "white"], ["navy", "beige"], ["navy", "sky"], ["teal", "white"],
    ["muted", "white"], ["muted", "beige"], ["white", "navy"], ["white", "teal"],
    ["error", "white"], ["success", "white"], ["warning", "white"], ["info", "white"],
    ["error", "beige"], ["success", "beige"], ["warning", "beige"], ["info", "beige"]
  ],
  "forbidden_text_pairs": [["teal", "beige"], ["sky", "white"], ["teal", "sky"]],
  "font": {
    "interface": {"family": "Ubuntu", "fallback": "system-ui, sans-serif", "weights": [400, 500, 700]},
    "editorial": {"family": "Rokkitt", "fallback": "Georgia, serif", "weights": [500, 600, 700]}
  },
  "type_scale": {
    "display": {"font": "editorial", "size_px": 44, "weight": 600, "line": 1.1},
    "h1": {"font": "editorial", "size_px": 34, "weight": 600, "line": 1.15},
    "h2": {"font": "editorial", "size_px": 26, "weight": 600, "line": 1.2},
    "h3": {"font": "interface", "size_px": 19, "weight": 700, "line": 1.3},
    "body": {"font": "interface", "size_px": 16, "weight": 400, "line": 1.55},
    "label": {"font": "interface", "size_px": 14, "weight": 500, "line": 1.4},
    "button": {"font": "interface", "size_px": 15, "weight": 500, "line": 1.2},
    "caption": {"font": "interface", "size_px": 13, "weight": 400, "line": 1.4}
  },
  "space_px": {"1": 4, "2": 8, "3": 12, "4": 16, "5": 24, "6": 32, "7": 48, "8": 64},
  "radius_px": {"sm": 4, "md": 6},
  "border_px": {"hairline": 1, "strong": 2},
  "breakpoints_px": {"sm": 600, "md": 900, "lg": 1200}
}
```

Nota: `white` sobre `teal` (botão secundário) = 4,50:1 — passa AA para texto de botão (15 px medium). `white` sobre `navy` = 10,44:1.

- [ ] **Step 2: Testes falhando**

`tests/test_tokens.py`:
```python
import json
import subprocess
import sys

from fias_ed_engine.paths import DESIGN_TOKENS_DIR, SHARED_ROOT

sys.path.insert(0, str(SHARED_ROOT / "scripts"))
import build_tokens  # noqa: E402

T = json.loads((DESIGN_TOKENS_DIR / "tokens.json").read_text(encoding="utf-8"))
ALL = {**T["color"]["brand"], **T["color"]["semantic"]}


def test_official_palette_exact():
    assert T["color"]["brand"] == {"navy": "#2F4156", "teal": "#567C8D", "sky": "#C8D9E6",
                                   "beige": "#F5EFEB", "white": "#FFFFFF"}


def test_contrast_function_known_values():
    assert round(build_tokens.contrast("#2F4156", "#FFFFFF"), 2) == 10.44
    assert build_tokens.contrast("#567C8D", "#FFFFFF") >= 4.5
    assert build_tokens.contrast("#567C8D", "#F5EFEB") < 4.5


def test_all_declared_text_pairs_pass_aa():
    for fg, bg in T["text_pairs"]:
        assert build_tokens.contrast(ALL[fg], ALL[bg]) >= 4.5, (fg, bg)


def test_forbidden_pairs_really_fail():
    for fg, bg in T["forbidden_text_pairs"]:
        assert build_tokens.contrast(ALL[fg], ALL[bg]) < 4.5, (fg, bg)


def test_editorial_font_not_used_for_small_text():
    for name, style in T["type_scale"].items():
        if style["font"] == "editorial":
            assert style["size_px"] >= 24, name


def test_build_outputs():
    subprocess.run([sys.executable, str(SHARED_ROOT / "scripts" / "build_tokens.py")], check=True)
    css = (DESIGN_TOKENS_DIR / "build" / "tokens.css").read_text(encoding="utf-8")
    kt = (DESIGN_TOKENS_DIR / "build" / "FiasTokens.kt").read_text(encoding="utf-8")
    assert "--color-navy: #2F4156;" in css
    assert "--font-interface: 'Ubuntu', system-ui, sans-serif;" in css
    assert "--font-editorial: 'Rokkitt', Georgia, serif;" in css
    assert "gradient" not in css.lower()
    assert "val Navy = Color(0xFF2F4156)" in kt
```
Run: `.venv/Scripts/python -m pytest tests/test_tokens.py -v` → FAIL.

- [ ] **Step 3: `build_tokens.py`**

```python
"""Gera tokens.css (Web) e FiasTokens.kt (Compose) a partir de design-tokens/tokens.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "design-tokens"


def _lum(hex_color: str) -> float:
    c = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(fg: str, bg: str) -> float:
    a, b = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _pascal(name: str) -> str:
    return "".join(p.capitalize() for p in name.replace("_", "-").split("-"))


def build() -> None:
    t = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))
    colors = {**t["color"]["brand"], **t["color"]["semantic"]}
    out = ROOT / "build"
    out.mkdir(exist_ok=True)

    css = ["/* Gerado por scripts/build_tokens.py — não editar. */", ":root {"]
    css += [f"  --color-{k}: {v};" for k, v in colors.items()]
    css += [f"  --color-{k}: var(--color-{v});" for k, v in t["color"]["role"].items()]
    css += [f"  --color-fias-{k}: var(--color-{v});" for k, v in t["color"]["fias_groups"].items()]
    for key, f in t["font"].items():
        css.append(f"  --font-{key}: '{f['family']}', {f['fallback']};")
    for name, s in t["type_scale"].items():
        css.append(f"  --type-{name}-size: {s['size_px'] / 16:.4g}rem;")
        css.append(f"  --type-{name}-weight: {s['weight']};")
        css.append(f"  --type-{name}-line: {s['line']};")
        css.append(f"  --type-{name}-font: var(--font-{s['font']});")
    css += [f"  --space-{k}: {v}px;" for k, v in t["space_px"].items()]
    css += [f"  --radius-{k}: {v}px;" for k, v in t["radius_px"].items()]
    css += [f"  --border-{k}: {v}px;" for k, v in t["border_px"].items()]
    css.append("}")
    (out / "tokens.css").write_text("\n".join(css) + "\n", encoding="utf-8")

    kt = ["// Gerado por scripts/build_tokens.py — não editar.",
          "package br.ufersa.fiased.designsystem", "",
          "import androidx.compose.ui.graphics.Color", "import androidx.compose.ui.unit.dp", "",
          "object FiasTokens {"]
    kt += [f"    val {_pascal(k)} = Color(0xFF{v.lstrip('#').upper()})" for k, v in colors.items()]
    kt += [f"    val Space{k} = {v}.dp" for k, v in t["space_px"].items()]
    kt += [f"    val Radius{_pascal(k)} = {v}.dp" for k, v in t["radius_px"].items()]
    kt += [f"    val Border{_pascal(k)} = {v}.dp" for k, v in t["border_px"].items()]
    kt.append("}")
    (out / "FiasTokens.kt").write_text("\n".join(kt) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
    print("tokens.css e FiasTokens.kt gerados")
```

Run: `.venv/Scripts/python -m pytest tests/test_tokens.py -v` → PASS (6 testes).

- [ ] **Step 4: Fontes locais**

`scripts/fetch_fonts.py` — baixa **uma vez** (em tempo de desenvolvimento, não em runtime) os TTFs do repositório oficial `google/fonts` no GitHub, grava SHA-256 em `fonts/manifest.json` e converte para WOFF2 com fontTools. Depois disso o sistema nunca mais precisa de rede para fontes.
```python
"""Baixa (uma vez) Ubuntu e Rokkitt do repositório google/fonts, registra hashes e gera WOFF2."""
import hashlib
import json
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont

BASE = "https://raw.githubusercontent.com/google/fonts/main/"
FILES = {
    "Ubuntu-Regular.ttf": "ufl/ubuntu/Ubuntu-Regular.ttf",
    "Ubuntu-Medium.ttf": "ufl/ubuntu/Ubuntu-Medium.ttf",
    "Ubuntu-Bold.ttf": "ufl/ubuntu/Ubuntu-Bold.ttf",
    "UFL.txt": "ufl/ubuntu/UFL.txt",
    "Rokkitt[wght].ttf": "ofl/rokkitt/Rokkitt%5Bwght%5D.ttf",
    "OFL-Rokkitt.txt": "ofl/rokkitt/OFL.txt",
}
OUT = Path(__file__).resolve().parents[1] / "design-tokens" / "fonts"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, rel in FILES.items():
        dest = OUT / name
        if not dest.exists():
            with urllib.request.urlopen(BASE + rel, timeout=60) as r:  # noqa: S310 (URL fixa, https)
                dest.write_bytes(r.read())
        manifest[name] = {"source": BASE + rel, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                          "size_bytes": dest.stat().st_size}
        if name.endswith(".ttf"):
            woff2 = dest.with_suffix(".woff2")
            font = TTFont(dest)
            font.flavor = "woff2"
            font.save(woff2)
            manifest[woff2.name] = {"derived_from": name, "sha256": hashlib.sha256(woff2.read_bytes()).hexdigest()}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(manifest)} arquivos registrados em {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
```

Run (de `fias-ed-shared`): `engine-py/.venv/Scripts/python scripts/fetch_fonts.py`
Expected: 3 TTF Ubuntu + 1 TTF Rokkitt variável + 4 WOFF2 + 2 licenças + manifest. Se o caminho `ufl/ubuntu/...` retornar 404, listar a pasta via `https://api.github.com/repos/google/fonts/contents/ufl/ubuntu` e ajustar `FILES` para os nomes reais; registrar a mudança no commit.

As fontes **são versionadas** (arquivos pequenos, licenças livres UFL/OFL que permitem redistribuição): remover a exclusão se alguma regra do `.gitignore` bloquear (não bloqueia — só áudio e modelos são ignorados).

Adicionar a `tests/test_tokens.py`:
```python
def test_fonts_bundled_with_licenses():
    fonts = DESIGN_TOKENS_DIR / "fonts"
    manifest = json.loads((fonts / "manifest.json").read_text(encoding="utf-8"))
    for name in ("Ubuntu-Regular.woff2", "Ubuntu-Medium.woff2", "Ubuntu-Bold.woff2", "Rokkitt[wght].woff2", "UFL.txt", "OFL-Rokkitt.txt"):
        assert (fonts / name).exists() and name in manifest
```
Run: `.venv/Scripts/python -m pytest tests/test_tokens.py -v` → PASS (7 testes).

- [ ] **Step 5: Commit**
```bash
git add fias-ed-shared/design-tokens fias-ed-shared/scripts/build_tokens.py fias-ed-shared/scripts/fetch_fonts.py fias-ed-shared/engine-py/tests/test_tokens.py
git commit -m "feat(shared): design tokens (paleta oficial, Ubuntu+Rokkitt locais) com verificação de contraste"
```

---

### Task 13: Documentação científica e de dados

**Files (todos em `fias-ed-shared/docs/`):** RESEARCH_INVENTORY.md, ANALISE_MODELOS_EXISTENTES.md, MODELS.md, FIAS.md, QTI.md, MTSS.md, SCIENTIFIC_TRACEABILITY.md, SCIENTIFIC_REPRODUCIBILITY.md, DATABASE_MODEL.md, ENTITY_DICTIONARY.md, PRIVACY.md, FUTURE_SYNC.md, FUTURE_SYNC_API.md
- Test: `engine-py/tests/test_docs.py`

**Regra de escrita:** toda afirmação factual cita arquivo + seção/linha (abreviações CAP4/CAP5/SIMB/FU/CEP) ou arquivo de experimento. Nada inventado. Onde a fonte não define, escrever literalmente `PENDING_SCIENTIFIC_VALIDATION` e o motivo. Linguagem sem expressões proibidas (Global Constraints). Português do Brasil.

Fontes de conteúdo (já levantadas; reler quando necessário):
- Inventário científico: relatório de pesquisa (seções 1–7) reproduzido no spec §3–8, §17; arquivos em `artigos selecionados\` listados no spec.
- Modelos: `scientific-config/models.json` + `experimentos/DOCUMENTACAO_EXPERIMENTOS.md` §2–4.

- [ ] **Step 1: Teste de presença e linguagem**

`tests/test_docs.py`:
```python
import pytest

from fias_ed_engine.language import find_forbidden
from fias_ed_engine.paths import SHARED_ROOT

DOCS = SHARED_ROOT / "docs"
REQUIRED = {
    "RESEARCH_INVENTORY.md": ["FIAS", "QTI", "MTSS", "AIED Unplugged", "PENDING_SCIENTIFIC_VALIDATION"],
    "ANALISE_MODELOS_EXISTENTES.md": ["token_type_ids", "0,7915", "BERTimbau", "CC BY-NC-SA", "training_args.bin"],
    "MODELS.md": ["SHA-256", "verify_models.py"],
    "FIAS.md": ["ID_RATIO", "3 s", "Flanders", "PTR"],
    "QTI.md": ["QTI-24", "Inseguro", "Incerto", "Wubbels", "extract_qti.py"],
    "MTSS.md": ["Tier 1", "enabled", "Formas_de_Uso"],
    "SCIENTIFIC_TRACEABILITY.md": ["source_reference", "validation_status", "CAP4"],
    "SCIENTIFIC_REPRODUCIBILITY.md": ["rules_version", "fias_model_hash", "conformance"],
    "DATABASE_MODEL.md": ["UUID", "sync_status", "BLOB"],
    "ENTITY_DICTIONARY.md": ["classificacao_fias", "pred_role_constrained"],
    "PRIVACY.md": ["retenção", "TCLE", "ALUNO", "biometria"],
    "FUTURE_SYNC.md": ["PENDING_SYNC", "CONFLICT"],
    "FUTURE_SYNC_API.md": ["device_id", "version"],
}
# Documentos que DESCREVEM o vocabulário proibido podem citá-lo entre crases; o teste ignora trechos em `...`.
import re


@pytest.mark.parametrize("name,terms", REQUIRED.items())
def test_doc_exists_with_key_terms(name, terms):
    text = (DOCS / name).read_text(encoding="utf-8")
    for t in terms:
        assert t in text, f"{name} sem '{t}'"


@pytest.mark.parametrize("name", REQUIRED)
def test_doc_language(name):
    text = re.sub(r"`[^`]*`", "", (DOCS / name).read_text(encoding="utf-8"))
    assert find_forbidden(text) == [], name
```
Run: → FAIL (docs inexistentes).

- [ ] **Step 2: RESEARCH_INVENTORY.md** — seções: 1. Fontes consultadas (lista de arquivos com caminho); 2. FIAS (categorias, grupos, protocolo 3 s, regras de desambiguação CAP4 l.277 citadas literalmente, matriz, índices — com o que é definido e o que não é); 3. QTI (duas versões: QTI-64 da dissertação sem mapeamento/pontuação vs QTI-24 do sistema, decisão tomada, status de validação e autorização); 4. MTSS Tier 1 (Tab. fias-tier1 completa, CAP4 l.285/287, lacuna dos critérios por aula, FU como documento de apoio sem fonte primária); 5. Triangulação (três planos, métricas CAP5, ausência de algoritmo); 6. AIED Unplugged (CAP4 l.115 vs CEP l.55 — divergência dos princípios); 7. ASR/diarização (nenhum modelo nomeado na dissertação; Whisper só na RSL; metas WER/DER ≤ 25% sem citação); 8. Métricas-alvo (tabela de `metric_targets.json`); 9. Divergências entre documentos (nomes FIAS, rótulos QTI, 3 versões do mapeamento TalkMoves→FIAS, UFERSA × UERN); 10. Lista completa de PENDING_SCIENTIFIC_VALIDATION (spec §17 + inventário item 7).

- [ ] **Step 3: ANALISE_MODELOS_EXISTENTES.md** — conteúdo obrigatório (spec §14): inventário de artefatos por frente (BERT EN, ELECTRA EN, BERTimbau PT-BR, SLMs LoRA, ONNX mobile) com métricas de DOCUMENTACAO_EXPERIMENTOS.md; modelo escolhido e porquê (teste de campo A06); `id2label` genérico e mapa índice+1; tokenizer (cased, vocab 29.794, max 256); formato de par (text_a = turno anterior, text_b = turno atual; cat. 10 = text_b vazio; papel não entra no modelo); discrepância `token_type_ids` (treino zeros vs benchmark segmentos; 0,7773 → 0,7915 em n=211) e decisão; padding fixo 256; ONNX (opset 17, entradas/saída, softmax fora do grafo); hiperparâmetros (seed 42, lr 2e-5, 10 épocas, batch 16); F1 por classe; seleção no conjunto de teste (viés otimista); licenças; arquivos pickle proibidos; riscos de domain shift; recomendação: não treinar novo modelo antes de avaliar em aulas brasileiras reais.

- [ ] **Step 4: MODELS.md** — como o registro funciona, tabela dos artefatos (caminho, SHA-256 completo, tamanho), `FIAS_ED_EXPERIMENTS_DIR`, uso de `verify_models.py`, política: não baixar silenciosamente, não carregar pickle, preferir safetensors/ONNX; seção reservada "ASR e diarização" apontando para os subprojetos 2 e 3.

- [ ] **Step 5: FIAS.md, QTI.md, MTSS.md** — cada um explica, para o pesquisador e para quem mantém o código: o que o arquivo de regras contém, cada regra/índice com fórmula, fonte e status, e como alterar (editar JSON → subir `rules_version` → regenerar conformance → rodar pytest). FIAS.md inclui a divergência da sigla PTR e a restrição por papel como `engineering_decision`. QTI.md inclui tabela de rótulos (sistema × dissertação × EN × NL), fórmula completa de octantes/Agency/Communion, formas de entrada, mínimo de 10 respostas, aviso de licença e procedimento `extract_qti.py --check`. MTSS.md inclui a Tab. fias-tier1, cada regra com condição e texto, por que os cortes FU estão `enabled: false`, e a garantia de que o sistema nunca emite rótulos de conformidade.

- [ ] **Step 6: SCIENTIFIC_TRACEABILITY.md e SCIENTIFIC_REPRODUCIBILITY.md** — Traceability: tabela de abreviações de fonte com caminhos completos; significado de cada `validation_status`; como `find_untraced` garante a cobertura; matriz regra → fonte (gerada à mão a partir dos JSON). Reproducibility: campos do `Processamento` (spec §9 e seção 44 do prompt original: app_version, rules_version, asr_model, asr_model_hash, diarization_model, fias_model, fias_model_hash, parameters, hardware, device, audio_duration, processing_time, created_at, transcript_source), papel dos casos de `conformance`, seeds, versões de dependências, snapshot de integridade das fontes.

- [ ] **Step 7: DATABASE_MODEL.md e ENTITY_DICTIONARY.md** — Database: diagrama textual das relações (professor 1–N turma, aula N–1 turma/disciplina, aula 1–N audio, transcricao 1–N segmento, segmento 1–1 classificacao_fias, …), campos comuns, UUIDv7, soft delete, áudio em filesystem (sem BLOB), mapeamento previsto para PostgreSQL (Web) e Room (Android). Dictionary: para cada uma das 20 entidades, tabela campo | tipo | obrigatório | descrição, idêntica aos schemas da Task 11.

- [ ] **Step 8: PRIVACY.md** — seções do prompt §49: dados coletados (por entidade), finalidade, localização (Web: PC do pesquisador, Docker, volume local; Android: armazenamento privado), retenção (5 anos após a conclusão, destruição certificada — CEP l.95; CAP5 l.109), acesso (pesquisador e orientador — TCLE Anexo A; professor vê só as próprias aulas), exclusão (real para áudio e transcrição), anonimização/pseudonimização (ALUNO, sem nomes; NER antes de exportar — PENDING), exportação. Seção "Não fazemos": biometria de voz, reconhecimento facial, identificação individual por voz, envio a APIs externas. Seção "Divergências a resolver": UFERSA × UERN; modo cloud/LLM não coberto pelos termos. **Não inventar base legal da LGPD**: escrever "Base legal: a definir pelo pesquisador com o CEP (PENDING)".

- [ ] **Step 9: FUTURE_SYNC.md e FUTURE_SYNC_API.md** — Sync: estados LOCAL_ONLY → PENDING_SYNC → SYNCED / CONFLICT; `version` inteiro incrementado a cada alteração; `device_id`; estratégia proposta (last-writer-wins por entidade com detecção de conflito por `version`, resolução manual para CONFLICT); áudio nunca sincroniza sem autorização explícita (CEP l.85). Não implementado nesta fase. API: esboço de endpoints (`POST /sync/push` com lote de entidades e `version` esperada; `GET /sync/pull?since=`), formato JSON baseado nos schemas de entidades, autenticação a definir, tudo marcado como proposta.

- [ ] **Step 10: Rodar testes e commit**

Run: `.venv/Scripts/python -m pytest tests/test_docs.py -v` → PASS.
```bash
git add fias-ed-shared/docs fias-ed-shared/engine-py/tests/test_docs.py
git commit -m "docs(shared): inventário científico, análise dos modelos, regras, dados, privacidade e sincronização futura"
```

---

### Task 14: Referências de interface e DESIGN_SYSTEM.md

**Files:**
- Create: `fias-ed-shared/docs/UI_REFERENCES.md`
- Create: `fias-ed-shared/docs/DESIGN_SYSTEM.md`
- Modify: `engine-py/tests/test_docs.py` (acrescentar os dois documentos)

- [ ] **Step 1: Pesquisa de referências** — usar navegação web (WebFetch/web-fetch agent) em páginas **públicas, sem login**: Dribbble, Behance, Land-book, Awwwards, SaaSFrame e sites de produtos reais (ex.: ferramentas de feedback docente e observação de aula, softwares científicos, sistemas institucionais de saúde/educação, dashboards B2B maduros). Mínimo **10** referências relevantes, priorizando educação, saúde, ferramentas acadêmicas e dashboards de dados. Para cada uma registrar: nome; URL; tela analisada; elemento relevante; como pode inspirar o FIAS-ED; o que **não** copiar. Incluir no topo: data da pesquisa; fontes não consultadas por exigirem login (Mobbin, Refero, Figma Community) e o motivo; síntese de 5–8 princípios extraídos (ex.: hierarquia editorial em relatórios, densidade de tabelas, estados vazios humanos). Só registrar URL efetivamente acessada; se uma página falhar, trocar por outra.

- [ ] **Step 2: DESIGN_SYSTEM.md** — derivado de `tokens.json` (valores idênticos). Seções exigidas pelo prompt §8: cores (paleta, papéis, proporção de uso 65–75% branco+bege / 10–15% navy / 8–12% teal / 5–10% sky, tabela de contraste e pares proibidos), tipografia (hierarquia display→caption; Rokkitt só ≥24 px e nunca em tabelas/inputs/números; Ubuntu 400/500/700; fontes locais), spacing (escala 4–64), grid (12 colunas ≥900 px, 4 colunas <600 px, gutter lateral 16 px no celular), radius (4/6 px), borders, shadows (apenas foco e diálogos), botões (primário navy/branco, secundário teal/branco ou contorno, terciário texto), inputs, tabelas, cards (só quando agrupam dados), dialogs, tabs, badges (status do processamento, nunca desempenho), gráficos (cores por grupo FIAS, rótulos diretos, sem 3D), loading (mensagens humanas do prompt §36), empty states, error states, breakpoints. Seção "Vocabulário" com os termos a usar e a evitar (prompt, seções de abertura e §7). Seção "Checklist visual final" = prompt §84. Seção "Revisões com Impeccable" explicando que acontecem sobre telas reais no subprojeto 2.

- [ ] **Step 3: Testes**

Acrescentar a `REQUIRED` em `tests/test_docs.py`:
```python
    "UI_REFERENCES.md": ["URL", "Mobbin", "não copiar"],
    "DESIGN_SYSTEM.md": ["#2F4156", "Rokkitt", "Ubuntu", "breakpoints", "empty state"],
```
e um teste de contagem:
```python
def test_at_least_ten_references():
    text = (DOCS / "UI_REFERENCES.md").read_text(encoding="utf-8")
    assert text.count("https://") >= 10
```
Run: `.venv/Scripts/python -m pytest tests/test_docs.py -v` → PASS.

- [ ] **Step 4: Commit**
```bash
git add fias-ed-shared/docs/UI_REFERENCES.md fias-ed-shared/docs/DESIGN_SYSTEM.md fias-ed-shared/engine-py/tests/test_docs.py
git commit -m "docs(shared): referências de interface e design system"
```

---

### Task 15: README, ARCHITECTURE e verificação final

**Files:**
- Create: `README.md` (raiz de `sistemas/`)
- Create: `ARCHITECTURE.md` (raiz)
- Create: `fias-ed-shared/README.md`

- [ ] **Step 1: README.md (raiz)** — o que é o FIAS-ED (mensagem "Grave sua aula. Melhore sua prática docente."), os três subprojetos e seu estado (shared: concluído; web e android: próximos), onde ficam fontes científicas e modelos (somente leitura), como rodar os testes do shared, links para docs.

- [ ] **Step 2: ARCHITECTURE.md (raiz)** — diagrama textual: Browser → React → FastAPI → PostgreSQL → pipeline local (Web) e Android offline (Compose → Room/SQLite → WorkManager → whisper.cpp/ONNX); papel do shared (regras JSON + schemas + conformance consumidos por ambos; motor Python importado pelo Web; motor Kotlin a implementar no subprojeto 3 passando nos mesmos casos); fluxo do professor (prompt §13) mapeado para os status; decisões tomadas (monorepo, JSON declarativo + conformance, MTSS descritivo, QTI-24, restrição por papel, token_type_ids zero); futuro (sync, FUTURE_SYNC.md).

- [ ] **Step 3: `fias-ed-shared/README.md`** — estrutura da pasta, comandos:
```bash
cd fias-ed-shared/engine-py
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,tools]"
.venv/Scripts/python -m pytest
cd ..
engine-py/.venv/Scripts/python scripts/verify_models.py
engine-py/.venv/Scripts/python scripts/extract_qti.py --check
engine-py/.venv/Scripts/python scripts/build_tokens.py
```
e o procedimento para mudar uma regra (editar JSON → subir `rules_version` → `generate_conformance.py` → revisar diff → pytest → commit).

- [ ] **Step 4: Verificação completa**

Run (de `fias-ed-shared/engine-py`): `.venv/Scripts/python -m pytest -v` → todos PASS.
Run (de `fias-ed-shared`):
```bash
engine-py/.venv/Scripts/python scripts/verify_models.py          # OK — todos os modelos conferem
engine-py/.venv/Scripts/python scripts/extract_qti.py --check    # OK — qti_config.json idêntico à fonte
engine-py/.venv/Scripts/python scripts/source_snapshot.py verify "$TEMP/fias_sources_before.json"   # OK — nenhuma alteração
```
Conferir os 9 critérios de aceite do spec §16, um a um, e registrar o resultado no corpo do commit.

- [ ] **Step 5: Commit**
```bash
git add README.md ARCHITECTURE.md fias-ed-shared/README.md
git commit -m "docs: README e arquitetura do FIAS-ED; subprojeto shared concluído"
```
