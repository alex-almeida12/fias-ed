# FIAS-ED Web

## 1. O que é

FIAS-ED Web, fatia **W1**: entrada com usuário e senha, contas de professor
(criadas pelo administrador), cadastro de escolas, turmas e disciplinas, aulas,
envio do áudio da aula e conferência automática do arquivo (formato, duração,
canais). O ciclo da aula em W1 vai de `DRAFT` a `AUDIO_VALIDATED`; a transcrição
e a análise ficam para a W2.

Spec: [`../docs/superpowers/specs/2026-09-22-fias-ed-web-w1-fundacao-design.md`](../docs/superpowers/specs/2026-09-22-fias-ed-web-w1-fundacao-design.md).

## 2. Pré-requisitos

- Docker Desktop com Docker Compose v2.
- Python 3 no Windows, só para rodar `scripts/smoke.py` (usa apenas a
  biblioteca padrão; funciona a partir do Python 3.10).

## 3. Primeira instalação

Todos os comandos rodam dentro de `fias-ed-web/`.

1. Crie o arquivo de configuração:
   ```bash
   cp .env.example .env
   ```
2. Troque as três senhas do `.env` (`POSTGRES_PASSWORD`,
   `FIAS_ED_MIGRATOR_PASSWORD`, `FIAS_ED_APP_PASSWORD`) por valores longos
   usando **só letras, números, `-` e `_`** (elas vão dentro de URLs de
   conexão). O `.env` é ignorado pelo Git; nunca o versione.
3. Suba o sistema:
   ```bash
   docker compose up -d --build
   ```
4. Crie o administrador (a senha é pedida duas vezes, sem aparecer na tela).
   **No PowerShell ou no Prompt de Comando (cmd)**:
   ```bash
   docker compose run --rm api python -m app.cli create-admin --username <usuario> --display-name "<Nome>"
   ```
   **No Git Bash** o terminal (mintty) não é um TTY para o Docker: sem ajuda,
   o comando acima não mostra o pedido de senha e a senha digitada aparece na
   tela. Use uma das duas formas:
   - com `winpty` (o pedido de senha oculto funciona como no PowerShell):
     ```bash
     winpty docker compose run --rm api python -m app.cli create-admin --username <usuario> --display-name "<Nome>"
     ```
   - sem TTY, passando a senha pelo stdin (duas linhas: senha e repetição).
     Leia a senha com `read -s` antes, para ela não aparecer na tela nem ficar
     no histórico do shell (nunca escreva a senha direto no comando):
     ```bash
     read -s -p "Senha: " PW; echo
     printf '%s\n%s\n' "$PW" "$PW" | docker compose run -T --rm api python -m app.cli create-admin --username <usuario> --display-name "<Nome>"
     unset PW
     ```
5. Popule o diretório de modelos (veja **Modelos**, logo abaixo). Sem isso a
   entrada de áudio funciona, mas o processamento da aula para no primeiro
   passo que precisa de modelo.
6. Abra **http://localhost:8080** (use `localhost`, não o IP: o cookie de
   sessão é `Secure` e o navegador só o aceita em HTTP puro para `localhost`).

O projeto Compose se chama `fias-ed-web` e o banco `fias_ed_web` (os volumes
ficam como `fias-ed-web_pgdata` e `fias-ed-web_audio_store`). O nome
`fias-ed` não é usado de propósito: pode existir outro projeto com esse nome
na mesma máquina.

### Modelos

Os três modelos ficam no volume `fias-ed-web_models`, montado em `/models`.
Eles **não** estão no Git (pesam cerca de 1 GB) e não são baixados quando o
sistema sobe: `api` e `worker` montam `/models` **somente leitura** e rodam com
`HF_HUB_OFFLINE=1` e `TRANSFORMERS_OFFLINE=1`. Em execução, nada sai para a
rede atrás de peso — se faltar um arquivo, o serviço recusa em vez de baixar.

| Modelo | Para quê | De onde vem |
|---|---|---|
| `faster-whisper-small` | Transformar áudio em texto | Hugging Face |
| `pyannote/speaker-diarization-3.1` | Separar as vozes da sala | Hugging Face |
| BERTimbau FIAS (Frente 3) | Classificação FIAS das falas | `artigos selecionados/experimentos/` |

Quem popula o volume é `scripts/setup_models.py`, uma vez, na instalação.
Cada repositório é baixado numa revisão fixada no próprio script, para que
duas máquinas instaladas em semanas diferentes fiquem com os mesmos pesos.

**Antes de rodar o setup**, três coisas:

1. Crie um token de **leitura** em <https://huggingface.co/settings/tokens>.
2. Abra as duas páginas abaixo **logado na conta dona do token** e aceite as
   condições de uso de cada uma. Sem isso o download volta `403`, e o script
   diz exatamente isso:
   - <https://huggingface.co/pyannote/speaker-diarization-3.1>
   - <https://huggingface.co/pyannote/segmentation-3.0>
3. Preencha no `.env`:
   ```
   HUGGINGFACE_TOKEN=<o token>
   FIAS_ED_EXPERIMENTS_DIR=../../artigos selecionados/experimentos
   ```
   O `.env` é ignorado pelo Git. **O token nunca entra em arquivo versionado,
   em log nem em mensagem de erro** — nem o `.env.example`, que traz só o nome
   da variável.

Depois:

```bash
docker compose --profile setup run --rm setup-models
```

O script termina com `MODELOS OK`. Ele é o único serviço do Compose que usa
rede para buscar peso, e por isso fica atrás do profile `setup`: um
`docker compose up` não o levanta. Ele lê o diretório dos experimentos
**somente leitura** e nunca escreve lá.

Os testes que carregam os modelos de verdade são marcados `lento` e ficam
**fora** da suíte padrão (que roda sem peso e sem GPU). Para rodar só eles,
com o volume dos modelos:

```bash
docker compose -f docker-compose.test.yml run --rm -v fias-ed-web_models:/models:ro api-test pytest -q -m lento
```

### Escolha do modelo de ASR

O tamanho do Whisper está em `ASR_SIZE` no `.env` (`small`). A escolha foi
medida, não chutada — `scripts/medir_asr.py` mede tempo e pico de memória dos
três tamanhos, com **os mesmos parâmetros do produto** (CPU, `int8`,
`language="pt"`, `temperature=0.0`, `vad_filter=True`):

```bash
docker compose -f docker-compose.test.yml run --rm \
    -v fias-ed-web_models:/models:ro api-test python /app/scripts/medir_asr.py
```

Máquina de referência: o container do projeto, **16 CPUs e 15,5 GB de RAM**,
**sem GPU** (o `torch` instalado é o `+cpu`, e `app/ml/asr_whisper.py` fixa
`device="cpu"`). Não há VRAM em jogo: o orçamento é de RAM. O áudio é fala
sintetizada pelo libflite, o mesmo recurso das fixtures dos testes `lento`; um
tom puro não serviria, porque o VAD do Whisper o descarta inteiro e a medição
viraria o custo do VAD.

**Medido** (uma execução por célula; repetindo a célula decisiva — `small` em
10 min — deu 99,5 s contra 100,2 s, 0,7% de diferença, e a mesma contagem de
segmentos):

| Modelo | Duração do áudio | Carga do modelo | Transcrição | s por min de áudio | Pico de memória | Segmentos |
|---|---|---|---|---|---|---|
| tiny | 2,5 min | 0,2 s | 4,5 s | 1,8 | 0,43 GB | 38 |
| tiny | 5 min | 0,2 s | 9,8 s | 2,0 | 0,52 GB | 90 |
| tiny | 10 min | 0,2 s | 14,7 s | 1,5 | 0,78 GB | 25 |
| base | 2,5 min | 0,2 s | 5,3 s | 2,1 | 0,49 GB | 6 |
| base | 5 min | 0,2 s | 8,6 s | 1,7 | 0,57 GB | 11 |
| base | 10 min | 0,2 s | 29,8 s | 3,0 | 0,87 GB | 51 |
| small | 2,5 min | 0,6 s | 29,2 s | 11,7 | 1,07 GB | 13 |
| small | 5 min | 0,5 s | 51,6 s | 10,3 | 1,08 GB | 18 |
| small | 10 min | 0,5 s | 100,2 s | 10,0 | 1,14 GB | 70 |

**Linearidade, verificada e não suposta.** O custo por minuto *não* se mantém
constante dentro de uma mesma chamada: variou 1,33× no `tiny`, 1,72× no `base`
e 1,16× no `small` entre 2,5 e 10 min. A causa provável é o áudio sintético —
o texto se repete e o Whisper condiciona a decodificação no que já transcreveu,
o que muda a quantidade de segmentos (a coluna "Segmentos" oscila junto com o
tempo). **Por isso a projeção abaixo não usa regra de três sobre a duração.**
Ela usa o fato de que o produto corta o áudio em chunks de 10 min
(`JANELA_PADRAO_MS` em `app/audio/prepare.py`) e chama o ASR uma vez por chunk,
do zero: uma aula de 90 min é o chunk de 10 min — medido — repetido 9 vezes,
com uma carga de modelo só.

**Extrapolado** (9 × o chunk de 10 min medido; os números desta tabela **não**
foram medidos numa aula de 90 min):

| Modelo | Tempo numa aula de 90 min | Em múltiplos da duração do áudio | Pico de memória (medido, do chunk de 10 min) |
|---|---|---|---|
| tiny | ~2 min | 0,02× | 0,78 GB |
| base | ~4 min | 0,05× | 0,87 GB |
| small | ~15 min | 0,17× | 1,14 GB |

O pico de memória não é extrapolado: como o chunk de 10 min é o maior pedaço
que o ASR vê em produção, o pico medido nele é o pico de produção. Ele cresce
com a duração *dentro* de uma chamada (0,43 → 0,78 GB no `tiny` entre 2,5 e
10 min), e é justamente por isso que o número que vale é o do chunk inteiro.

**Critério:** o **maior** tamanho cujo tempo numa aula de 90 min fique abaixo
de 2× a duração do áudio e cujo pico de memória caiba com folga na máquina de
referência, lembrando que o `pyannote` roda em seguida.

**Escolhido: `small`** (`ASR_SIZE=small`). É o maior dos três, fica em 0,17× a
duração do áudio — bem abaixo do teto de 2× — e o pico de 1,14 GB ocupa 7% dos
15,5 GB da máquina. Os dois menores são mais baratos, mas não há motivo para
gastar o tamanho de modelo quando o maior cabe com folga dessa ordem.

Três limites do que está escrito aqui, para não valerem mais do que valem:

- **Não há medição de acerto.** WER e DER exigiriam áudio real de aula com
  transcrição e diarização de referência, que o projeto não tem. Os dois
  seguem `PENDING_SCIENTIFIC_VALIDATION`. A fala do libflite tem pronúncia
  inglesa: serve para medir tempo de processamento, não para medir acerto.
- **O orçamento de memória do `pyannote` é desconhecido.** Ele roda depois do
  ASR, no mesmo worker, e hoje não dá para medi-lo: os repositórios dele são
  *gated* no Hugging Face e os pesos não estão nesta máquina. A folga de 14 GB
  é grande, mas a conta final só fecha quando ele for medido.
- **`tiny` e `base` não são adotáveis como estão.** Eles têm revisão fixada em
  `scripts/setup_models.py` (para a medição), mas não têm entrada em
  `fias-ed-shared/scientific-config/models.json`, que este repositório não
  altera — e `app/ml/asr_whisper.py` recusa carregar um modelo que o registro
  não declare. Trocar o tamanho em produção exige a entrada lá primeiro.

Para baixar os pesos de um tamanho só (a medição precisa dos três em disco):

```bash
docker compose --profile setup run --rm -e FIAS_ED_ASR_SIZE=tiny \
    setup-models python /app/scripts/setup_models.py --somente-asr
```

### Tamanho máximo do áudio

O limite é 1,5 GB (`MAX_UPLOAD_BYTES=1610612736` no `.env`) e está repetido no
nginx (`client_max_body_size 1536m` em `deploy/nginx.conf`). **Os dois mudam
juntos**: ao alterar um, altere o outro e reconstrua com
`docker compose up -d --build`. Um arquivo acima do limite é recusado pelo
próprio nginx, antes de chegar à API; o nginx responde com o mesmo erro da API
(`AUDIO_TOO_LARGE`, bloco `location @too_large` em `deploy/nginx.conf`), e o
texto dessa mensagem, que cita "1,5 GB", também precisa ser ajustado.

## 4. Uso diário

```bash
docker compose up -d        # liga
docker compose stop         # desliga (os dados ficam nos volumes)
docker compose logs -f api worker
```

`docker compose ps` deve mostrar `db`, `api`, `worker` e `web` como
`healthy`, e `migrate` como `Exited (0)`: o `migrate` roda o Alembic uma vez e
sai, por isso é o único serviço sem healthcheck.

## 5. Testes

```bash
# backend (pytest, em banco de teste descartável do projeto fias-ed-web-test)
docker compose -f docker-compose.test.yml run --rm --build api-test pytest -q
# frontend (funciona igual no PowerShell e no Git Bash, sem sair de fias-ed-web/)
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run lint
# aceitação de ponta a ponta (com o sistema no ar)
python scripts/smoke.py --admin-user <usuario>
```

O teste de aceitação pede a senha do administrador (ou a lê da primeira linha
do stdin, quando não há terminal), cria uma conta temporária de professor,
percorre entrada, troca de senha, envio e conferência de áudio, extensão falsa
e "agir como", e no fim exclui a conta temporária (com as aulas, turmas e
disciplinas dela). A escola **"Escola de teste (smoke)"** fica no cadastro
comum de escolas (é reaproveitada nas próximas execuções). A conta
temporária e as aulas dela ficam no banco como registros excluídos
(`deleted_at`), sem áudio. O teste termina com `SMOKE OK`.

## 6. Auditorias

```bash
docker compose -f docker-compose.test.yml run --rm api-test bandit -r app --severity-level high
docker compose -f docker-compose.test.yml run --rm api-test pip-audit --skip-editable
npm --prefix frontend audit --audit-level=high
```

Última execução (2026-09-22):

| Ferramenta | Resultado |
|---|---|
| bandit (severidade alta) | `No issues identified.` |
| pip-audit | `No known vulnerabilities found` (os pacotes editáveis `fias-ed-engine` e `fias-ed-web-api` são pulados, como esperado) |
| npm audit (alta ou crítica) | `found 0 vulnerabilities` |

## 7. Backup e restauração

**Aviso:** o backup contém os áudios das aulas e dados pessoais (nomes de
professores, turmas, escolas). Guarde-o em local protegido, com o mesmo
cuidado dos dados originais.

Rode de `fias-ed-web/`, com o sistema no ar. Antes de restaurar, pare a API e
o worker (`docker compose stop api worker`) e ligue-os de novo no fim
(`docker compose start api worker`).

### Git Bash

```bash
# banco
docker compose exec -T db pg_dump -U postgres -Fc fias_ed_web > backup-fias-ed-web.dump
docker compose exec -T db pg_restore -U postgres -d fias_ed_web --clean --if-exists < backup-fias-ed-web.dump

# áudios
MSYS_NO_PATHCONV=1 docker run --rm -v fias-ed-web_audio_store:/dados:ro -v "$(pwd -W)":/backup alpine tar czf /backup/audios.tgz -C /dados .
MSYS_NO_PATHCONV=1 docker run --rm -v fias-ed-web_audio_store:/dados -v "$(pwd -W)":/backup alpine tar xzf /backup/audios.tgz -C /dados
```

(`MSYS_NO_PATHCONV=1` impede o Git Bash de reescrever `/dados` e `/backup`
como caminhos do Windows; `$(pwd -W)` dá a pasta atual no formato `C:/...`.)

### PowerShell

No PowerShell 5.1 o `>` estraga arquivos binários e o `<` não existe, por isso o banco
passa pelo `cmd /c`, que redireciona os bytes sem conversão:

```powershell
# banco
cmd /c "docker compose exec -T db pg_dump -U postgres -Fc fias_ed_web > backup-fias-ed-web.dump"
cmd /c "docker compose exec -T db pg_restore -U postgres -d fias_ed_web --clean --if-exists < backup-fias-ed-web.dump"

# áudios
docker run --rm -v fias-ed-web_audio_store:/dados:ro -v "${PWD}:/backup" alpine tar czf /backup/audios.tgz -C /dados .
docker run --rm -v fias-ed-web_audio_store:/dados -v "${PWD}:/backup" alpine tar xzf /backup/audios.tgz -C /dados
```

## 8. Segurança

- Única porta publicada: `127.0.0.1:8080` (serviço `web`); nada fica acessível
  pela rede local ou pela internet.
- O banco fica na rede interna `fias_net` (sem saída e sem porta publicada).
- A API e o worker conectam como `fias_ed_app`, que só tem `SELECT, INSERT,
  UPDATE, DELETE` (sem DDL). As migrações rodam no serviço `migrate`, com o
  usuário `fias_ed_migrator`.
- Todos os containers rodam como usuário não-root, com
  `no-new-privileges` e `cap_drop: ALL`; nenhum é `privileged`; nenhuma pasta
  do Windows é montada (os dados ficam em volumes Docker).
- O nginx envia `Content-Security-Policy` (com `frame-ancestors 'none'`),
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy` e `X-Frame-Options: DENY`.
- Senhas com hash Argon2id; sessão no servidor (cookie opaco `HttpOnly`,
  `Secure`, `SameSite=Strict`) com token CSRF.

## 9. Dependências

Nenhuma dependência envia telemetria.

| Dependência | Licença | Motivo |
|---|---|---|
| FastAPI, Starlette | MIT, BSD-3 | API HTTP |
| Uvicorn | BSD-3 | servidor ASGI |
| Pydantic, pydantic-settings | MIT | validação e configuração |
| SQLAlchemy, Alembic | MIT | acesso ao banco e migrações |
| psycopg 3 | LGPL-3.0 | driver PostgreSQL |
| argon2-cffi | MIT | hash de senha Argon2id |
| FFmpeg (ffprobe) | LGPL/GPL (pacote Debian) | leitura dos metadados do áudio |
| PyTorch, torchaudio (wheels de CPU) | BSD-3 | base dos modelos; sem CUDA, o alvo é CPU |
| Transformers | Apache-2.0 | carregamento do classificador |
| faster-whisper, CTranslate2 | MIT | transcrição |
| pyannote.audio | MIT | separação de vozes |
| huggingface-hub | Apache-2.0 | download dos pesos, só na instalação |
| spaCy, `pt_core_news_sm` | MIT, MIT + CC BY-SA 4.0 | pseudonimização de nomes |
| PostgreSQL 16 | PostgreSQL License | banco de dados |
| nginx (nginx-unprivileged) | BSD-2 | servidor web e proxy |
| React, React DOM, React Router | MIT | interface |
| Vite, TypeScript, Vitest, Testing Library, ESLint | MIT/Apache-2.0 | build e testes (só desenvolvimento) |

## 10. Divergências do spec (errata)

Resolvidas a favor dos schemas de `fias-ed-shared/` (o banco nunca diverge
deles):

- **Turma exige escola.** `turma.schema.json` exige `escola_id`; ao criar a
  turma, o professor escolhe ou cadastra a escola (o spec dizia "escola
  opcional").
- **`processamento` sem linhas em W1.** A tabela existe (compatível com o
  schema), mas o schema exige dados que só existem na W2 (modelo de ASR,
  hashes dos modelos); a primeira linha nasce na W2.
- **Tabela interna `audio_upload`.** O schema de `audio` exige duração,
  canais, taxa de amostragem e MIME, conhecidos só depois da conferência; o
  envio fica em `audio_upload` e a linha de `audio` é criada pelo job de
  validação.
- **`professor.username` obrigatório no Web.** No schema compartilhado o campo
  é opcional; no Web ele é obrigatório (é o login) e único
  (inclusive o de contas excluídas, que fica reservado).
