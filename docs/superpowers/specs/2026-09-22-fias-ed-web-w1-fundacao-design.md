# Spec — Subprojeto 2, fatia W1: `fias-ed-web` — Fundação

Data: 2026-09-22
Autor da solicitação: Alex Almeida do Amaral (PPgCC UFERSA/UERN)
Status: aguardando revisão do pesquisador
Fonte dos requisitos: `docs/PROMPT_MESTRE.md` (citado como "prompt §N")
Depende de: `fias-ed-shared` (concluído; spec `2026-09-21-fias-ed-shared-design.md`)

---

## 0. Decomposição do subprojeto Web

O subprojeto Web foi dividido em quatro fatias verticais. Cada uma tem spec,
plano e implementação próprios e termina com o sistema utilizável de ponta a
ponta até um status da `Aula`:

| Fatia | Conteúdo | Termina em |
|---|---|---|
| **W1 Fundação** (este documento) | Compose, PostgreSQL + Alembic, autenticação, segurança base, React + design system, Home/Dashboard/Nova Aula, upload e validação | `AUDIO_VALIDATED` |
| W2 Pipeline | cópia de trabalho, normalização, chunks, ASR (faster-whisper), diarização (pyannote), "Qual destas vozes é você?", revisão da transcrição, classificação FIAS, tela FIAS | `FIAS_COMPLETED` |
| W3 Percepção e relatório | QTI (manual, CSV do avalie-seu-professor, OCR), triangulação, MTSS, sugestões, Relatório da Aula (PDF), exportação do dataset | `REPORT_READY` |
| W4 Auditorias | bandit/pip-audit/npm audit/gitleaks, testes do §76 completos, SECURITY_AUDIT.md, FINAL_SECURITY_CHECK.md, auditoria visual final (Impeccable), áudios longos (10–90 min) | — |

## 1. Objetivo de W1

Entregar a base segura e a identidade visual do FIAS-ED Web: o professor entra
com usuário e senha, cadastra uma aula, envia o áudio e vê o áudio validado.
Tudo o que W2–W4 constroem se apoia nesta fatia (containers, banco, sessão,
autorização, fila de tarefas, design system no React).

## 2. Implantação e acesso

- Roda **somente no PC do pesquisador**, via Docker Compose. O navegador acessa
  `http://localhost:8080`; a única porta publicada é `127.0.0.1:8080`
  (prompt §50). Nada é exposto na rede local nem na Internet.
- Sem TLS em W1: o acesso é apenas por localhost, onde navegadores tratam o
  contexto como seguro (cookies `Secure` funcionam). Acesso pela rede local
  fica fora do escopo (exigiria HTTPS com CA local).

## 3. Containers e estrutura

```
docker compose — rede interna "fias_net"
├── web     nginx (não-root): React compilado + proxy /api → api:8000
│           + cabeçalhos de segurança (§74)
├── api     FastAPI, Python 3.12, usuário não-root; importa fias_ed_engine
├── worker  mesma imagem do api; consome a tabela job
└── db      PostgreSQL 16, sem porta publicada, healthcheck
volumes nomeados: pgdata, audio_store (somente api e worker montam)
```

- Todos os containers: sem `privileged`, usuário não-root, healthcheck
  (prompt §73). Nenhuma pasta do Windows é montada.
- Cabeçalhos no nginx: `Content-Security-Policy` (`default-src 'self'`; sem
  `unsafe-inline` para scripts), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Permissions-Policy` negando câmera,
  microfone e geolocalização, `frame-ancestors 'none'`.
- Mesma origem para frontend e API: CORS permanece fechado (nenhum
  `allow_origins`; prompt §60). Em desenvolvimento, o Vite faz proxy de `/api`.

Estrutura de `fias-ed-web/`:

```
backend/
  app/
    core/      config (pydantic-settings), db, segurança, logging, erros
    auth/      login, logout, sessão, CSRF
    users/     professor, administração de contas, create-admin (CLI)
    catalog/   escola, turma, disciplina
    aulas/     aula, status, exclusão
    audio/     upload, armazenamento, validação (ffprobe)
    jobs/      tabela job, worker
    admin/     leitura das aulas dos professores + registro de acesso
  alembic/
  tests/
frontend/
  src/
    app/       rotas, layout, guarda de sessão
    design/    tokens.css (do shared), fontes locais, componentes base
    pages/     Home, Dashboard, NovaAula, Aula, admin/Contas, admin/Aulas
    api/       cliente fetch tipado (envia X-CSRF-Token)
  tests/
deploy/
  nginx.conf
  db-init/     cria fias_ed_migrator e fias_ed_app
docker-compose.yml
.env.example
README.md
```

- O contexto de build Docker é a raiz do monorepo, para copiar
  `fias-ed-shared/` (motor Python, schemas, `design-tokens/build/tokens.css`,
  fontes em `design-tokens/fonts/`). Nenhuma fonte é carregada de CDN
  (prompt §6).

## 4. Banco de dados

- Usuários (prompt §51): o superusuário do Postgres só é usado pelo script de
  init. `fias_ed_migrator` é dono do schema e roda o Alembic;
  `fias_ed_app` tem apenas `SELECT, INSERT, UPDATE, DELETE` nas tabelas e
  `USAGE` nas sequências. A API e o worker conectam como `fias_ed_app`.
- Segredos (prompt §52): senhas no `.env` (ignorado pelo Git); apenas
  `.env.example` é versionado, sem valores reais.
- Todas as consultas via SQLAlchemy com parâmetros; nenhuma concatenação de
  SQL (prompt §58).

### 4.1 Tabelas de W1

Tabelas do modelo lógico (seguem `fias-ed-shared/schemas/entities/`, com a
base comum `id` UUID, `created_at`, `updated_at`, `deleted_at`, `version`,
`sync_status`, `device_id`):

| Tabela | Campos específicos (schema) | Observações |
|---|---|---|
| `professor` | `username`, `display_name`, `role` (ADMIN_LOCAL, PROFESSOR) | + `password_hash`, `is_active`, `must_change_password`, `failed_logins`, `locked_until` — só no banco, nunca na API nem na exportação |
| `escola` | `name`, `municipality`, `region` | cadastro comum a todos os professores (ver §4.3) |
| `turma` | `escola_id` (opcional), `professor_id`, `name`, `school_year`, `level` | |
| `disciplina` | `professor_id`, `name` | |
| `aula` | `professor_id`, `turma_id`, `disciplina_id`, `lesson_date`, `status`, `note`, `error_code` | |
| `audio` | `aula_id`, `original_filename`, `internal_filename`, `path`, `mime_type`, `size_bytes`, `duration_ms`, `sha256`, `channels`, `sample_rate`, `is_original`, `derived_from_audio_id` | `path` relativo ao volume `audio_store` |
| `processamento` | campos do schema | criado em W1 com `app_version`, `rules_version`, `audio_duration_ms`, `status`; demais campos preenchidos em W2 |

Tabelas internas (fora do modelo lógico compartilhado, não exportadas):

| Tabela | Campos |
|---|---|
| `sessao` | `id`, `professor_id`, `acting_as_professor_id` (só admin), `token_sha256`, `csrf_token_sha256`, `created_at`, `last_seen_at`, `expires_at` |
| `job` | `id`, `type`, `aula_id`, `status` (queued, running, done, failed), `attempts`, `error_code`, `locked_at`, `created_at`, `finished_at` |
| `acesso_admin` | `id`, `admin_id`, `professor_id` (dono dos dados), `resource`, `resource_id`, `action` (`read`, `create`, `update`, `delete`, `upload`, `process`), `created_at` |

### 4.3 Escola como cadastro comum

No modelo do shared, `Escola` é a instituição; o vínculo com o professor é
feito pela `Turma` (`professor_id`). Vários professores dão aula na mesma
escola, por isso a escola **não tem dono** e o schema do shared não muda:

- qualquer professor escolhe uma escola existente ou cria uma nova (nome,
  município, região);
- ao criar, o sistema procura escolas com o mesmo nome (sem diferenciar
  maiúsculas, acentos e espaços extras) no mesmo município e oferece usar a
  existente;
- o ADMIN_LOCAL corrige dados de escolas e junta duplicatas (as turmas da
  escola removida passam para a escola mantida; a removida recebe
  `deleted_at`);
- turma e disciplina continuam pertencendo ao professor.

### 4.2 Compatibilidade com o shared

Teste automatizado (início do `schema_compatibility_test`, prompt §79): para
cada tabela do modelo lógico, toda propriedade do schema correspondente existe
como coluna, com tipo compatível, nulabilidade compatível com `required` e o
mesmo conjunto de valores para enums.

## 5. Autenticação (prompt §53)

- **Sem autocadastro.** O primeiro ADMIN_LOCAL é criado por
  `docker compose run --rm api python -m app.cli create-admin`; a senha é
  pedida no terminal (nunca por argumento nem variável de ambiente).
- O ADMIN_LOCAL cria contas de professor, desativa contas e redefine senhas.
- Senha: mínimo 12 caracteres. Hash **Argon2id** (`argon2-cffi`, parâmetros
  padrão do perfil RFC 9106 da biblioteca). Hash é refeito no login se os
  parâmetros mudarem.
- **Sessão no servidor:** cookie `fias_session` com token aleatório de 256
  bits; o banco guarda só o SHA-256 do token. Cookie `HttpOnly`,
  `SameSite=Strict`, `Secure`, `Path=/`. Expira após 2 h de inatividade ou
  12 h absolutas. Logout apaga a linha. Troca ou redefinição de senha apaga
  todas as sessões do professor.
- **Senha provisória:** quando o admin cria a conta ou redefine a senha, o
  sistema gera uma senha provisória aleatória (mostrada uma única vez ao
  admin) e marca `must_change_password`; no primeiro acesso, o professor só
  consegue trocar a senha antes de usar o sistema.
- **CSRF (prompt §61):** token por sessão, entregue em cookie legível
  `fias_csrf` e exigido no cabeçalho `X-CSRF-Token` em POST/PUT/PATCH/DELETE;
  comparação em tempo constante.
- **Bloqueio:** 5 falhas seguidas para o mesmo usuário bloqueiam o login por
  15 min. Mensagem de erro única ("Usuário ou senha incorretos") para usuário
  inexistente, senha errada ou conta bloqueada/desativada.

## 6. Autorização (prompt §54)

- **PROFESSOR:** lê e altera apenas os próprios dados. Toda consulta filtra
  por `professor_id` do usuário atual. Recurso de outro professor → **404**
  (não revela existência).
- **ADMIN_LOCAL:**
  - administra contas e escolas;
  - vê a lista de aulas de todos os professores (filtro por professor);
  - **pode fazer tudo o que o professor faz, em nome de qualquer professor:**
    escolhe um professor ("Agir como") e passa a usar as mesmas telas e rotas
    do professor sobre os dados dele — criar aulas, enviar e substituir áudio,
    processar, excluir e, nas fatias seguintes, revisar falantes e
    transcrição, lançar o QTI e gerar o relatório. O professor escolhido fica
    em `sessao.acting_as_professor_id`; todas as rotas de professor usam o
    "professor efetivo" (o próprio usuário, ou o escolhido pelo admin);
  - a aula continua pertencendo ao professor (`professor_id` dele), mesmo
    quando criada pelo admin;
  - uma faixa fixa no topo da tela mostra "Você está agindo como:
    <nome do professor>" com o botão **Voltar à minha conta**;
  - **cada leitura ou alteração** do admin em dados de outro professor gera
    uma linha em `acesso_admin`; o professor vê, na própria aula, o aviso
    "Alterada pelo administrador em <data>" quando houver alteração feita
    pelo admin;
  - pode ter aulas próprias, nas quais age como professor comum.
- `PRIVACY.md` do shared é atualizado: o pesquisador (ADMIN_LOCAL) tem acesso
  total às aulas dos professores, e toda leitura ou alteração dele é
  registrada.

## 7. Aula, upload e validação do áudio

### 7.1 Fluxo (prompt §13, §15, §16)

1. **Nova Aula:** turma (criação inline, escola opcional), disciplina
   (criação inline), data, observação opcional → `aula.status = DRAFT`.
2. **Selecionar áudio:** upload em streaming para
   `audio_store/tmp/<uuid>`, com SHA-256 calculado durante a escrita e
   interrupção ao ultrapassar o limite. Concluído, o arquivo é movido para
   `audio_store/original/<uuid>.<ext>` com permissão somente leitura;
   `aula.status = AUDIO_IMPORTED`. O nome original é guardado apenas em
   `original_filename` (texto), nunca usado para montar caminhos — o caminho
   é sempre derivado do UUID (prompt §56).
   **Substituir o áudio** só é permitido antes do início da análise (status
   `DRAFT`, `AUDIO_IMPORTED`, `AUDIO_VALIDATED` ou `ERROR`) e exige
   confirmação em diálogo: "Substituir o áudio? O arquivo anterior será
   apagado." O arquivo anterior é apagado fisicamente depois que o novo
   termina de ser recebido; a aula volta para `AUDIO_IMPORTED`. A partir do
   início da análise (W2), trocar o áudio exige criar uma nova aula, para não
   misturar resultados de áudios diferentes (a API responde
   `AUDIO_LOCKED`).
3. **Processar aula:** cria um `job` do tipo `validate_audio`. O worker
   executa `ffprobe` com lista de argumentos (sem `shell=True`, sem
   `os.system`; prompt §57) e verifica:
   - extensão ∈ {mp3, wav, m4a, aac, flac};
   - formato detectado pelo ffprobe compatível com a extensão;
   - MIME derivado do formato detectado (nunca do cabeçalho do navegador),
     dentro do enum de `audio.mime_type`;
   - tamanho, duração, canais e sample rate registrados.
   Sucesso → `audio` preenchido, `aula.status = AUDIO_VALIDATED`.
   Falha → `aula.status = ERROR` com `error_code`:
   `AUDIO_FORMAT_MISMATCH`, `AUDIO_UNSUPPORTED_FORMAT`, `AUDIO_TOO_LONG`,
   `AUDIO_TOO_SHORT`, `AUDIO_CORRUPTED`, `AUDIO_TOO_LARGE`. O professor pode
   enviar outro arquivo. Em W2, o pipeline continua a partir de
   `AUDIO_VALIDATED`.

Mapa extensão → formato ffprobe → MIME:

| Extensão | `format_name` aceito | MIME |
|---|---|---|
| mp3 | `mp3` | `audio/mpeg` |
| wav | `wav` | `audio/wav` |
| m4a | `mov,mp4,m4a,3gp,3g2,mj2` com stream de áudio AAC/ALAC | `audio/mp4` |
| aac | `aac` | `audio/aac` |
| flac | `flac` | `audio/flac` |

### 7.2 Limites (configuráveis no `.env`)

- Tamanho máximo: **1,5 GB** (`MAX_UPLOAD_BYTES`); o nginx aplica o mesmo
  limite (`client_max_body_size`).
- Duração: **1 min** a **150 min** (`MIN_AUDIO_SECONDS`, `MAX_AUDIO_SECONDS`).
- O arquivo precisa ter pelo menos um stream de áudio.

### 7.3 Preservação do original (prompt §17)

O arquivo em `audio_store/original/` nunca é modificado. Cópia de trabalho e
normalização pertencem a W2 (`is_original = false`,
`derived_from_audio_id`).

### 7.4 Jobs

- O worker pega um job por vez com `SELECT … FOR UPDATE SKIP LOCKED`,
  consultando a fila a cada 2 s.
- Job `running` com `locked_at` há mais de 30 min volta para `queued`;
  máximo de 3 tentativas, depois `failed` e `aula.status = ERROR`
  (`error_code = JOB_FAILED`).
- Tipos de job em W1: `validate_audio`. W2 acrescenta os demais.

### 7.5 Exclusão (prompt §49)

- O professor exclui uma aula: arquivos de áudio apagados fisicamente na
  hora; linhas de `aula`, `audio`, `processamento` recebem `deleted_at` e
  somem de todas as consultas.
- Ações do admin sobre contas (três ações distintas):
  - **Desativar:** login impedido e sessões apagadas; dados mantidos; o
    admin continua acessando e agindo sobre as aulas do professor e pode
    **reativar** a conta.
  - **Redefinir senha:** gera senha provisória (§5).
  - **Excluir conta:** ação separada, que exige digitar o nome de usuário
    para confirmar; apaga fisicamente todos os áudios do professor e marca
    `deleted_at` no professor e em todas as suas turmas, disciplinas, aulas,
    áudios e processamentos. Não é possível excluir a própria conta nem o
    último ADMIN_LOCAL ativo.

## 8. API

Prefixo `/api`. Respostas JSON com modelos Pydantic (prompt §55); limites de
tamanho em todos os campos de texto (nomes ≤ 120, observação ≤ 2000).

| Método e rota | Perfil | Função |
|---|---|---|
| `POST /api/auth/login` | público | cria sessão |
| `POST /api/auth/logout` | autenticado | apaga sessão |
| `GET /api/auth/me` | autenticado | usuário atual |
| `POST /api/auth/password` | autenticado | troca a própria senha |
| `GET/POST /api/turmas`, `/api/disciplinas` | professor efetivo | listar/criar próprias |
| `GET/POST /api/escolas` | professor efetivo | listar/criar (cadastro comum; `POST` devolve possíveis duplicatas) |
| `GET/POST /api/aulas` | professor efetivo | listar/criar |
| `GET/DELETE /api/aulas/{id}` | professor efetivo | detalhe/excluir |
| `PUT /api/aulas/{id}/audio` | professor efetivo | upload/substituição (streaming) |
| `GET /api/aulas/{id}/audio` | professor efetivo | reprodução do original (suporta `Range`) |
| `POST /api/aulas/{id}/processar` | professor efetivo | enfileira `validate_audio` |
| `POST /api/admin/agir-como`, `DELETE /api/admin/agir-como` | admin | começa/termina a ação em nome de um professor |
| `GET /api/admin/aulas[?professor_id=]` | admin | lista de aulas de todos os professores |
| `GET/POST /api/admin/contas`, `PATCH /api/admin/contas/{id}`, `POST /api/admin/contas/{id}/senha-provisoria`, `DELETE /api/admin/contas/{id}` | admin | contas (desativar/reativar via `PATCH`) |
| `PATCH /api/admin/escolas/{id}`, `POST /api/admin/escolas/{id}/juntar` | admin | corrigir e juntar escolas |

"Professor efetivo" = o próprio usuário, ou o professor escolhido pelo admin
em "agir como".
| `GET /api/health` | interno | healthcheck |

Erros: handler global responde `{"error_code": "...", "message": "..."}` em
português, sem stack trace nem detalhes internos.

## 9. Logs (prompt §65)

JSON estruturado com `aula_id`, `processamento_id`, `job_id`, `status`,
duração e `error_code`. Nunca: senha, token, cookie, texto de transcrição,
respostas do QTI, nome de arquivo original, nome de turma ou de professor.
Um teste verifica que um fluxo completo não grava esses valores no log.

## 10. Frontend

- React + TypeScript + Vite + React Router. Cliente `fetch` próprio (envia
  `credentials: "same-origin"` e `X-CSRF-Token`). Sem biblioteca de
  componentes: componentes base próprios seguindo
  `fias-ed-shared/docs/DESIGN_SYSTEM.md`, usando `tokens.css` e as fontes
  locais Ubuntu/Rokkitt do shared.
- Proibido `dangerouslySetInnerHTML` (regra de lint; prompt §59). Todo texto
  vindo do usuário é renderizado como texto.
- Linguagem da interface segue o prompt (seções iniciais, §7) e o
  vocabulário do DESIGN_SYSTEM.md; status sempre em linguagem humana.

### 10.1 Telas

| Tela | Conteúdo |
|---|---|
| **Home** (§14) | "FIAS-ED"; título em Rokkitt "Grave sua aula. Melhore sua prática docente."; descrição "Envie o áudio de uma aula e conheça melhor os padrões de interação que acontecem em sala." em Ubuntu; formulário de entrada ao lado. Após login → Dashboard. |
| **Dashboard — Minhas aulas** | lista (data, turma, disciplina, status humano); botão **Adicionar aula**; estado vazio acolhedor. |
| **Nova Aula / Upload** (§15) | campos Turma, Disciplina, Data, Observação opcional; área "Adicionar áudio da aula" com o texto "Selecione o arquivo de áudio gravado durante sua aula."; botões **Selecionar áudio** e **Processar aula**; barra de progresso do envio; erros explicados em português. |
| **Aula** | status humano, mensagem do §36 enquanto houver job ativo (W1: "Preparando sua aula..."), dados do áudio, player do original, enviar outro áudio em caso de erro, excluir aula (com confirmação em diálogo próprio). |
| **Trocar senha** | obrigatória no primeiro acesso com senha provisória. |
| **Admin — Contas** | criar professor (mostra a senha provisória uma vez), desativar/reativar, redefinir senha, excluir conta (confirmação digitando o nome de usuário). |
| **Admin — Aulas dos professores** | lista de aulas de todos os professores com filtro por professor; botão **Agir como este professor**. |
| **Admin — Escolas** | corrigir dados e juntar duplicatas. |

Status em linguagem humana — todos os 17 status definidos já em W1 (W2 e W3
apenas passam a usá-los). Um único módulo do frontend mapeia status → texto;
um teste garante que todo valor do enum de `aula.status` tem texto.

| Status | Texto na tela |
|---|---|
| `DRAFT` | Aguardando o áudio da aula |
| `AUDIO_IMPORTED` | Áudio recebido, pronto para processar |
| `AUDIO_VALIDATED` | Áudio conferido |
| `PREPROCESSING`, `TRANSCRIBING`, `TRANSCRIBED`, `DIARIZING` | Analisando sua aula… |
| `READY_FOR_SPEAKER_REVIEW` | Confirme qual voz é a sua |
| `READY_FOR_TRANSCRIPT_REVIEW` | Revise a transcrição, se quiser |
| `READY_FOR_FIAS`, `FIAS_COMPLETED` | Padrões de interação prontos |
| `WAITING_QTI` | Aguardando a percepção dos estudantes |
| `QTI_COMPLETED`, `TRIANGULATED`, `MTSS_INTERPRETED` | Preparando a interpretação pedagógica… |
| `REPORT_READY` | Relatório da aula disponível |
| `ERROR` | Precisa de atenção (seguido da mensagem do erro) |

Enquanto houver job ativo, a tela da aula mostra a mensagem do §36 da etapa
(W1: "Preparando sua aula...").

Mensagens de erro (sempre dizendo o que fazer):

| `error_code` | Mensagem |
|---|---|
| `AUDIO_FORMAT_MISMATCH`, `AUDIO_UNSUPPORTED_FORMAT` | Este arquivo não parece ser um áudio MP3, WAV, M4A, AAC ou FLAC. Tente exportar o áudio novamente no gravador. |
| `AUDIO_TOO_LONG` | O áudio tem mais de 2h30. Divida a gravação e envie cada parte como uma aula. |
| `AUDIO_TOO_SHORT` | O áudio tem menos de 1 minuto. Verifique se é o arquivo certo. |
| `AUDIO_CORRUPTED` | Não conseguimos ler este arquivo. Ele pode estar incompleto; tente copiá-lo de novo do gravador. |
| `AUDIO_TOO_LARGE` | O arquivo passa de 1,5 GB. Tente exportar o áudio em MP3 ou M4A, que ocupam menos espaço. |
| `AUDIO_LOCKED` | A análise desta aula já começou. Para usar outro áudio, crie uma nova aula. |
| `JOB_FAILED` | Algo deu errado ao preparar sua aula. Tente processar novamente; se continuar, avise o administrador. |

Os limites citados nas mensagens (1,5 GB, 2h30, 1 minuto) vêm da configuração
(§7.2), não de texto fixo.

- Atualização de progresso: consulta ao status da aula a cada 3 s enquanto
  houver job `queued`/`running`.

### 10.2 Revisão visual (prompt §2, §84)

Home, Dashboard, Nova Aula e Upload passam pelo ciclo implementar → revisar
com Impeccable → corrigir → testar → revisar novamente, e pelo critério
visual final do §84 (checklist do DESIGN_SYSTEM.md). **Pré-requisito:** o
pesquisador instala o Impeccable antes da execução do plano
(`npx impeccable install --global --providers=claude -y`). Sem o plugin, as
tarefas de revisão visual param e aguardam a instalação.

## 11. Testes

- **Backend:** pytest contra PostgreSQL real (banco de teste separado no
  compose; `docker compose run --rm api pytest`). Cobre: compatibilidade com
  os schemas do shared; Argon2id; sessão (expiração por inatividade e
  absoluta, logout, invalidação ao trocar senha); CSRF; bloqueio após 5
  falhas; senha provisória e troca obrigatória; ownership; "agir como" do
  admin (rotas de professor sobre dados de outro professor, aula continua do
  professor, registro em `acesso_admin` de leituras e alterações, aviso
  "alterada pelo administrador"); desativar/reativar/excluir conta (não
  exclui a própria nem o último admin); escolas (detecção de duplicata,
  junção); substituição de áudio (permitida só antes da análise);
  upload e validação com áudios pequenos gerados no teste (WAV, FLAC, MP3,
  M4A e arquivo com extensão falsa); jobs (retomada de job travado, limite de
  tentativas); exclusão física dos arquivos; logs sem dados sensíveis.
- **Segurança (prompt §76, itens aplicáveis a W1):** login inválido, acesso
  sem autenticação, acesso a recurso de outro professor, SQL injection em
  filtros e campos, XSS (nome de turma com `<script>` exibido como texto),
  path traversal no nome do arquivo (`../`, `..\`), upload malformado,
  arquivo grande demais, extensão falsa, sessão inválida/expirada/forjada,
  endpoint administrativo acessado por professor, ausência de `X-CSRF-Token`.
- **Frontend:** Vitest + Testing Library (fluxo de login, troca obrigatória
  de senha, Nova Aula, upload, confirmação de substituição, faixa "agindo
  como", status humano para todo o enum, mensagens de erro, XSS renderizado
  como texto); ESLint.
- **Auditorias em W1:** `bandit`, `pip-audit`, `npm audit` (prompt §69–70).
  gitleaks e SECURITY_AUDIT.md ficam em W4.
- **Dependências (prompt §68):** cada dependência nova é registrada no
  README com licença e motivo; nenhuma com telemetria ativa.

## 12. Documentação

- `fias-ed-web/README.md`: pré-requisitos, `.env`, subir o sistema, criar o
  admin, rodar testes e auditorias, backup e restauração dos volumes
  (`pgdata`, `audio_store`), lista de dependências com licença.
- `fias-ed-shared/docs/PRIVACY.md`: acesso total do ADMIN_LOCAL às aulas
  dos professores, registro em `acesso_admin`, escola como cadastro comum,
  exclusão física de áudio, localização dos dados (volumes
  Docker no PC do pesquisador).
- `ARCHITECTURE.md` (raiz): containers, fila `job`, sessão, estado de W1.

## 13. Fora do escopo de W1

Cópia de trabalho, normalização, ASR, diarização, revisão de transcrição,
classificação FIAS (W2); QTI, OCR, triangulação, MTSS, sugestões, relatório,
PDF, exportação (W3); gitleaks, auditoria de segurança completa, auditoria
visual final, testes com áudios longos (W4); acesso pela rede local/HTTPS;
sincronização com Android; gravação dentro do app (OPTIONAL_FEATURE, §12).

## 14. Critérios de aceite de W1

1. `docker compose up` sobe `web`, `api`, `worker` e `db` saudáveis; apenas
   `127.0.0.1:8080` publicado.
2. Fluxo completo: `create-admin` → admin cria professor → professor entra
   com a senha provisória e troca a senha → cria aula → envia áudio →
   processa → aula em `AUDIO_VALIDATED`. Arquivo com extensão falsa →
   `ERROR` com `AUDIO_FORMAT_MISMATCH` e mensagem humana.
3. O admin age como o professor, cria e processa uma aula em nome dele; a
   aula aparece para o professor com o aviso "Alterada pelo administrador" e
   as ações constam em `acesso_admin`.
4. pytest e vitest verdes, incluindo os testes de segurança da §11.
5. Teste de compatibilidade das tabelas com os schemas do shared verde.
6. `bandit`, `pip-audit` e `npm audit` sem achados HIGH ou CRITICAL não
   tratados (tratamentos registrados no README).
7. Nenhum container como root ou privilegiado; API e worker conectam como
   `fias_ed_app`, que não tem permissão de DDL (teste).
8. Home, Dashboard, Nova Aula e Upload revisadas com Impeccable e aprovadas
   no critério do §84.
9. Cabeçalhos de segurança presentes nas respostas do nginx (teste).
10. Nenhum arquivo alterado em `artigos selecionados\` ou
   `avalie-seu-professor\`.
