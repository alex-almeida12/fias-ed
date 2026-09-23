# Licenças de terceiros — FIAS-ED

Componentes que o FIAS-ED usa e não escreveu, com a licença de cada um e o
crédito que ela exige. Cobre os três subprojetos (`fias-ed-web`,
`fias-ed-android`, `fias-ed-shared`).

Gerado em 2026-09-22 a partir dos metadados dos pacotes instalados, dos
arquivos de licença já versionados e de `fias-ed-shared/scientific-config/models.json`.
Itens marcados **PENDENTE** exigem uma verificação manual descrita no lugar.

---

## 1. Restrição que limita o que o FIAS-ED pode se tornar

**O classificador FIAS não pode ser usado comercialmente.**

O modelo `fias-bertimbau-ptbr-frente3`, que faz a classificação das falas da
aula, foi ajustado sobre o dataset **TalkMoves**, cuja licença é
**CC BY-NC-SA 4.0**. O `NC` é *non-commercial*.

| O que | Situação |
|---|---|
| Uso em pesquisa acadêmica, incluindo esta dissertação | Permitido |
| Publicar resultados e o código | Permitido, mantendo a atribuição e a mesma licença (`SA`) |
| Vender o FIAS-ED, licenciar para uma rede de ensino, ou usar num serviço pago | **Não permitido** sem retreinar o classificador com outros dados |

A restrição vem dos **dados de treino**, não do código: os pesos base do
BERTimbau (`neuralmind/bert-base-portuguese-cased`) são MIT. Um classificador
treinado do zero com dados próprios removeria a limitação.

Fonte: `fias-ed-shared/scientific-config/models.json`, campo `license` de cada
modelo.

---

## 2. Modelos de IA

| Modelo | Onde é usado | Código | Dados de treino |
|---|---|---|---|
| `fias-bertimbau-ptbr-frente3` | Classificação FIAS (Web) | MIT (`neuralmind/bert-base-portuguese-cased`) | **CC BY-NC-SA 4.0** (TalkMoves) |
| `fias-bertimbau-ptbr-frente3-onnx-int8` | Classificação FIAS (Android) | MIT | **CC BY-NC-SA 4.0** |
| `pt_core_news_sm` 3.8.0 (spaCy) | Pseudonimização de nomes na transcrição | MIT | **CC BY-SA 4.0** |
| `pyannote/speaker-diarization-3.1` | Separação de vozes | PENDENTE — entra na Task 14 da fatia W2 | PENDENTE |
| `faster-whisper` (tamanho a definir) | Transcrição | PENDENTE — entra na Task 14 da fatia W2 | PENDENTE |

**PENDENTE — crédito exigido pelas licenças Creative Commons.** CC BY-NC-SA e
CC BY-SA exigem creditar autor e fonte pelo nome. Preencher abrindo os *model
cards*:

- TalkMoves (dados do BERTimbau): citar os autores do dataset e o artigo de origem.
- `pt_core_news_sm`: os dados são **UD Portuguese Bosque** e **WikiNER**; citar ambos.
- Ao acrescentar `pyannote` e `faster-whisper` na Task 14, registrar aqui no mesmo formato.

Textos canônicos das licenças (link basta, não é preciso copiar):

- CC BY-NC-SA 4.0 — https://creativecommons.org/licenses/by-nc-sa/4.0/
- CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/
- CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/

---

## 3. Fontes tipográficas

Já em conformidade: os textos das licenças estão versionados ao lado dos
arquivos de fonte, que é o que essas licenças exigem.

| Fonte | Licença | Texto no repositório |
|---|---|---|
| Ubuntu | Ubuntu Font Licence 1.0 | `fias-ed-shared/design-tokens/fonts/UFL.txt` |
| Rokkitt | SIL Open Font License 1.1 | `fias-ed-shared/design-tokens/fonts/OFL-Rokkitt.txt` |

Origem de cada arquivo e o SHA-256 conferido estão em
`fias-ed-shared/design-tokens/fonts/manifest.json`.

---

## 4. Frontend (`fias-ed-web/frontend`)

232 pacotes em `node_modules`, contando as dependências transitivas.
Distribuição por licença:

| Licença | Pacotes |
|---|---|
| MIT | 186 |
| Apache-2.0 | 17 |
| ISC | 11 |
| BSD-2-Clause | 8 |
| BSD-3-Clause | 3 |
| MIT-0 | 2 |
| MPL-2.0 | 2 |
| CC-BY-4.0 | 1 |
| CC0-1.0 | 1 |
| BlueOak-1.0.0 | 1 |

**O que de fato é distribuído.** Só o que entra no pacote compilado (`dist/`)
cria obrigação de aviso para quem recebe o sistema: `react`, `react-dom` e
`react-router`, os três **MIT**. O MIT exige que o aviso de copyright acompanhe
a distribuição — o build do Vite preserva os avisos dos pacotes incluídos.

**Os casos que não são MIT são todos de tempo de build**, não chegam ao
navegador do professor:

| Pacote | Licença | Papel |
|---|---|---|
| `caniuse-lite` | CC-BY-4.0 | Tabela de compatibilidade de navegadores, usada pelo build. **Exige atribuição** — a licença está declarada no próprio pacote. |
| `lightningcss`, `lightningcss-win32-x64-msvc` | MPL-2.0 | Minificador de CSS. MPL exige que modificações no próprio pacote sejam publicadas; não modificamos. |
| `mdn-data` | CC0-1.0 | Domínio público; sem obrigação. |
| `minimatch` | BlueOak-1.0.0 | Licença permissiva. |

Lista completa, se precisar reproduzir:

```bash
cd fias-ed-web/frontend && npm ls --all --json
```

---

## 5. Motor científico (`fias-ed-shared/engine-py`)

29 pacotes instalados no ambiente virtual:

| Licença | Pacotes |
|---|---|
| MIT | 9 |
| BSD | 4 |
| Apache-2.0 | 3 |
| MPL-2.0 | 1 |
| ISC | 1 |
| **Sem campo de licença nos metadados** | **11** |

**PENDENTE — os 11 sem campo.** O metadado do pacote não traz a licença; ela
está no arquivo `LICENSE` dentro de cada um. Para listar quais são:

```bash
cd fias-ed-shared/engine-py && .venv/Scripts/python -c "
from importlib.metadata import distributions
for d in distributions():
    m = d.metadata
    cls = [c for c in m.get_all('Classifier') or [] if c.startswith('License ::')]
    if not (m.get('License') or cls):
        print(m.get('Name'), m.get('Version'))
"
```

---

## 6. Backend (`fias-ed-web/backend`)

**PENDENTE — extração.** As dependências vivem na imagem Docker e não no
sistema de arquivos local, então a lista não pôde ser gerada aqui. Com o Docker
Desktop no ar:

```bash
cd fias-ed-web && docker compose -f docker-compose.test.yml run --rm api-test python -c "
from importlib.metadata import distributions
vistos = {}
for d in distributions():
    m = d.metadata
    lic = m.get('License') or ''
    cls = [c for c in m.get_all('Classifier') or [] if c.startswith('License ::')]
    if cls: lic = cls[0].split('::')[-1].strip()
    n = m.get('Name')
    if n and n not in vistos: vistos[n] = (m.get('Version'), lic or '(sem campo)')
for n, (v, l) in sorted(vistos.items()): print(f'{n}\t{v}\t{l}')
"
```

Dependências diretas declaradas em `backend/pyproject.toml`: `fastapi`,
`uvicorn`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `psycopg`, `alembic`,
`argon2-cffi`, `spacy`, `pt_core_news_sm`.

Ferramentas externas usadas por linha de comando, não empacotadas: **FFmpeg**
(`ffmpeg`, `ffprobe`) e **PostgreSQL 16**, ambos vindos das imagens oficiais.
PENDENTE: registrar a licença das imagens usadas no `docker-compose.yml`.

---

## 7. Como manter isto vivo

O arquivo envelhece a cada dependência nova. Duas regras:

1. Ao acrescentar um modelo de IA, registrar a licença em
   `fias-ed-shared/scientific-config/models.json` **e** na seção 2 daqui.
2. Ao acrescentar uma dependência com licença que exige atribuição
   (qualquer Creative Commons, MPL, EPL), registrar na seção correspondente.
   Licenças permissivas (MIT, BSD, ISC, Apache) entram na contagem agregada.

A restrição não comercial da seção 1 é a única com consequência sobre o que o
projeto pode se tornar. Se o classificador for retreinado com outros dados, esta
seção deve ser revista.
