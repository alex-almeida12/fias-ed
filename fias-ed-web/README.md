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
4. Crie o administrador (a senha é pedida duas vezes, sem aparecer na tela):
   ```bash
   docker compose run --rm api python -m app.cli create-admin --username <usuario> --display-name "<Nome>"
   ```
5. Abra **http://localhost:8080** (use `localhost`, não o IP: o cookie de
   sessão é `Secure` e o navegador só o aceita em HTTP puro para `localhost`).

O projeto Compose se chama `fias-ed-web` e o banco `fias_ed_web` (os volumes
ficam como `fias-ed-web_pgdata` e `fias-ed-web_audio_store`). O nome
`fias-ed` não é usado de propósito: pode existir outro projeto com esse nome
na mesma máquina.

### Tamanho máximo do áudio

O limite é 1,5 GB (`MAX_UPLOAD_BYTES=1610612736` no `.env`) e está repetido no
nginx (`client_max_body_size 1536m` em `deploy/nginx.conf`). **Os dois mudam
juntos**: ao alterar um, altere o outro e reconstrua com
`docker compose up -d --build`.

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
# frontend
cd frontend && npm ci && npm test && npm run lint
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
cd frontend && npm audit --audit-level=high
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
