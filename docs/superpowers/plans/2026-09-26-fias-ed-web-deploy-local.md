# Implantação local para a coleta em sala — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o FIAS-ED roda num único computador, numa rede sem internet, e os celulares dos estudantes respondem ao questionário pela rede local — sem nenhum token nem IP de estudante em log, com o limite de respostas garantido pelo banco, e instalável numa máquina sem internet a partir de um pacote.

**Architecture:** a imagem `web` ganha um segundo `server` no nginx (8081) que serve só as rotas do estudante; um serviço novo, `web-lan`, publica essa porta no IP da sala, e só quando o professor abre a coleta. A URL do link passa a vir de configuração e o `Secure` do cookie de consentimento segue o esquema dela. Duas restrições parciais no banco (um link vivo por coleta, uma coleta viva por data) tornam impossíveis as corridas que hoje só o código evita. Scripts POSIX sh sobem a coleta, montam o pacote offline e o instalam.

**Tech Stack:** nginx (nginx-unprivileged 1.27), Docker Compose v2, FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 16, React 19 + Vitest, POSIX sh (Git Bash no Windows).

**Spec:** `docs/superpowers/specs/2026-09-26-fias-ed-web-deploy-local-design.md`

## Global Constraints

- **Nenhum token de link nem IP de estudante em log** — acesso e erro do nginx, API, logs do Docker. Vale com a API fora do ar.
- **A regra do comentário do `nginx.conf` permanece:** quem quiser log nas rotas do estudante tem de mascarar token e IP no formato do log antes; não basta apagar um `access_log off`.
- **Não simular navegador.** O percurso em celular é do pesquisador. `curl` é cliente HTTP, não navegador, e é como se prova o que dá para provar daqui.
- **Nada em `fias-ed-shared/`** (somente leitura).
- **Scripts em POSIX sh** — rodam no Git Bash, no bash/dash do Linux e no `sh` do BusyBox. Sem `[[ ]]`, sem arrays, sem `local`, sem `pipefail`.
- **Todo script que chama `docker` exporta `MSYS_NO_PATHCONV=1`**, e caminho de pasta do host passado em `-v` sai de `pwd -W` no Git Bash e de `pwd` no Linux (convenção do `fias-ed-web/README.md` §7). Sem isso o Git Bash reescreve `/saida` como `C:/Program Files/Git/saida` — o diretório `fias-ed-web/deploy/nginx.conf;C` que apareceu na W3b foi exatamente isso.
- **Nunca** `docker compose down -v`, nunca apagar dado do banco de dev, nunca `git clean`. O banco tem trabalho do pesquisador.
- **O pacote offline nunca contém `.env` nem o token do Hugging Face**, e é gerado **fora** do repositório.
- Vocabulário proibido em texto visível: "avalia", "avaliação", "nota", "desempenho", "ranking". Todo texto em português do Brasil.
- Um commit por tarefa, em português, no padrão do repositório (`feat(escopo): ...`, `fix(...)`, `test(...)`, `docs(...)`), terminando com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Conferir o `git diff` antes de todo commit.
- **Mutação:** aplicar, rodar e restaurar em passos separados, nunca encadeados numa linha só. Se o classificador de segurança bloquear uma mutação, **não contornar**: dizer no relatório e, se der, construir o cenário dentro do próprio teste.
- **O container `db-test` persiste** entre `docker compose run`, e o alembic não reaplica revisão já registrada. Antes de confiar num número do backend: `docker compose -f docker-compose.test.yml build api-test`; e, se a verificação depende do esquema, recriar o `db-test` de verdade.
- **Números de partida (HEAD `6f01c42`):** motor 267; backend **550 passed, 6 deselected**; frontend **229 passed em 22 arquivos**.
- Comandos das suítes, a partir de `fias-ed-web/`:
  - backend: `docker compose -f docker-compose.test.yml run --rm api-test pytest -q`
  - frontend: `cd frontend && npx vitest run && npm run lint && npm run build`
  - motor: `cd ../fias-ed-shared/engine-py && ./.venv/Scripts/python.exe -m pytest -q`

## Review Focus

1. **O computador está em mais de uma rede privada** (Wi-Fi + VirtualBox, VPN ou hotspot) → o script não escolhe sozinho: lista as redes e exige `--ip`. *Teste: Task 6, `deploy/testes/filtro-de-rede.sh`, caso "duas redes reais".*
2. **A API cai ou reinicia no meio da coleta** → o estudante vê erro, e nenhum log grava token nem IP. *Teste: Task 1, passo 6, e Task 9.*
3. **O professor clica duas vezes em "Gerar link"** → um único link vivo, sem erro 500. *Testes: Task 3, `test_criar_link_espera_quem_esta_criando_outro_para_a_mesma_coleta`; Task 4, `test_dois_pedidos_simultaneos_de_link_reusam_a_mesma_coleta`.*
4. **O computador reinicia no meio da coleta** → `web-lan` não volta sozinho (a porta da sala fica fechada até alguém reabrir), e a tela do professor em 8080 volta normalmente. *Verificação: Task 1, passo 7 (política de reinício inspecionada).*
5. **O IP da sala muda depois de o link ser gerado** → o link projetado deixa de funcionar; o professor vê o endereço junto do QR e gera outro, que desativa o antigo. *Testes: Task 2, `test_a_url_do_link_vem_da_url_publica_configurada`; Task 3, `test_criar_um_segundo_link_revoga_o_primeiro`.*

## Mapa de arquivos

| Arquivo | Tarefa | Responsabilidade |
|---|---|---|
| `fias-ed-web/deploy/nginx.conf` | 1 | os dois servidores; nada de token nem IP em log |
| `fias-ed-web/docker-compose.yml` | 1, 2 | serviço `web-lan`; nome da imagem do banco; `PUBLIC_URL` na API |
| `fias-ed-web/.env.example` | 2 | documenta as variáveis que o script define |
| `fias-ed-web/backend/app/core/config.py` | 2 | `public_url` |
| `fias-ed-web/backend/app/qti/routes.py` | 2 | URL do link a partir da configuração |
| `fias-ed-web/backend/app/publico/routes.py` | 2, 3 | `Secure` pelo esquema; revalidação do link com a trava |
| `fias-ed-web/backend/app/qti/links.py` | 3 | um link vivo por coleta |
| `fias-ed-web/backend/app/ciclos/routes.py` | 3 | comentário que ficou falso |
| `fias-ed-web/backend/alembic/versions/0011_um_link_vivo_por_coleta.py` | 3 | criar |
| `fias-ed-web/backend/app/qti/service.py` | 4 | tratar a corrida contra a restrição |
| `fias-ed-web/backend/app/models.py` | 3, 4 | espelhar os índices no modelo |
| `fias-ed-web/backend/alembic/versions/0012_uma_coleta_viva_por_data.py` | 4 | criar |
| `fias-ed-web/frontend/src/design/components/QrCode.tsx` | 5 | criar |
| `fias-ed-web/frontend/src/pages/Acompanhamentos.tsx` | 3, 5 | aviso de substituição; QR |
| `fias-ed-web/deploy/subir-coleta.sh` | 6 | criar |
| `fias-ed-web/deploy/testes/filtro-de-rede.sh` | 6 | criar |
| `docs/deploy-local.md` | 7 | criar — o runbook |
| `docs/ESTADO_DE_VALIDACAO.md` | 7 | limitação do HTTP em claro |
| `fias-ed-web/README.md` | 7 | apontar para o runbook |
| `fias-ed-web/deploy/empacotar.sh`, `fias-ed-web/deploy/instalar.sh` | 8 | criar |
| `THIRD_PARTY_LICENSES.md` | 5 | a biblioteca de QR |

---

## Task 1: o servidor dos celulares, e nenhum segredo em log

**Files:**
- Modify: `fias-ed-web/deploy/nginx.conf`
- Modify: `fias-ed-web/docker-compose.yml`

**Interfaces:**
- Produces: servidor na porta **8081** da imagem `fias-ed-web-web:local`, cuja página `/` contém o texto literal **`Conexão com o FIAS-ED funcionando`** (a Task 6 procura a palavra `funcionando`). Serviço **`web-lan`**, profile **`coleta`**, `restart: "no"`, publicado em `${FIAS_ED_LAN_IP:-127.0.0.1}:${FIAS_ED_LAN_PORT:-8081}:8081`. Imagem do banco nomeada **`fias-ed-web-db:local`** (a Task 8 salva as três imagens pelo nome).

Não existe suíte que suba o nginx: a prova desta tarefa são comandos com a saída real colada no relatório.

- [x] **Step 1: Registrar o vazamento de hoje, antes de mexer**

Com o sistema no ar (`docker compose ps`):

```sh
curl -s -o /dev/null http://localhost:8080/responder/TOKEN_ANTES_DA_TASK_1
docker compose logs web --tail 5 | grep TOKEN_ANTES_DA_TASK_1
```

Esperado: uma linha com o token e um IP. Cole no relatório — é o "antes".

- [x] **Step 2: Escrever o `nginx.conf` novo**

Substitua o arquivo inteiro por este. O servidor 8080 é o de hoje com duas mudanças (`error_log` em `/publico/`, e o `location /responder/` novo); o 8081 é novo.

```nginx
# Dois servidores na mesma imagem (docs/superpowers/specs/2026-09-26-fias-ed-web-deploy-local-design.md, §3.1).
#
# 8080 — o sistema inteiro, para o professor. O serviço `web` publica esta porta só
#        em 127.0.0.1: não sai da máquina.
# 8081 — só o que o estudante usa. O serviço `web-lan` (profile "coleta", aberto por
#        deploy/subir-coleta.sh) publica esta porta no IP da rede da sala. É a única
#        porta que os celulares alcançam.
#
# Regra dos dois: token de link e IP de estudante não entram em log nenhum. §7 item 1
# da spec da W3 (docs/superpowers/specs/2026-09-24-fias-ed-web-w3-qti-mtss-design.md):
# "Nenhuma identidade de respondente é persistida. Sem nome, sem matrícula, sem
# endereço de rede, sem identificador de dispositivo." Quem quiser log nas rotas do
# estudante precisa antes mascarar token e IP no formato do log — não basta apagar um
# `access_log off`.

server {
    listen 8080;
    server_name _;
    server_tokens off;
    # Fixo em 1536m (= MAX_UPLOAD_BYTES padrão, 1,5 GB). Se mudar MAX_UPLOAD_BYTES no .env, mude aqui também.
    client_max_body_size 1536m;
    # Acima do limite o nginx responde antes da API; devolve o mesmo JSON de erro da API
    # (AUDIO_TOO_LARGE). Se mudar o limite, mude também o texto em @too_large.
    error_page 413 @too_large;
    root /usr/share/nginx/html;

    # deploy/subir-coleta.sh recria a API toda vez que abre ou fecha a coleta (muda a URL
    # dos links), e o contêiner recriado pode ganhar outro IP. Com o nome fixo no
    # proxy_pass, o nginx resolve uma vez só, na subida, e passaria a mandar tudo para o
    # IP velho (502). Com variável + resolver, ele pergunta de novo ao DNS do Docker.
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $api http://api:8000;

    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header X-Frame-Options "DENY" always;

    location /api/ {
        proxy_pass $api;
        proxy_http_version 1.1;
        proxy_request_buffering off;
        # Sem buffer na resposta: a reprodução do áudio (até 1,5 GB, com Range) passa direto,
        # sem ser copiada para arquivos temporários do nginx. As respostas JSON são pequenas.
        proxy_buffering off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /publico/ {
        # O log de acesso padrão do nginx grava o token do link (na URL) em claro e o IP
        # de quem respondeu, num arquivo no disco do host, sem rotação — um terceiro
        # lugar além dos dois que o docstring de app/qti/links.py promete para o
        # segredo. Achado da verificação final da W3b (2026-09-26). A aplicação já
        # registra o molde da rota (/publico/qti/{token}, sem o valor) e nenhum IP — o
        # custo aceito aqui é só o diagnóstico de problema pontual do estudante.
        access_log off;
        # O log de erro também leva `client: <IP>` e a linha da requisição, com o token,
        # quando a API não responde. Só o nível crítico passa.
        error_log /dev/stderr crit;
        proxy_pass $api;
        proxy_http_version 1.1;
        proxy_request_buffering off;
        # A única porta sem autenticação do sistema não tem por que aceitar corpo grande —
        # 32k basta para as 24 respostas do questionário (inteiros de 1 a 5, algumas
        # centenas de bytes). O limite de 1,5 GB é para o áudio da aula, numa rota
        # autenticada.
        client_max_body_size 32k;
        # proxy_buffering no padrão (ligado), ao contrário do /api/: o `off` de lá existe para
        # a reprodução de áudio com Range; aqui as respostas são JSON pequeno.
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /responder/ {
        # A página que o estudante abre carrega o token no caminho (/responder/<token>):
        # mesmo motivo do /publico/. Achado da preparação da fatia de implantação.
        access_log off;
        error_log /dev/stderr crit;
        try_files $uri /index.html;
    }

    location @too_large {
        default_type application/json;
        return 413 '{"error_code":"AUDIO_TOO_LARGE","message":"O arquivo passa de 1,5 GB. Tente exportar o áudio em MP3 ou M4A, que ocupam menos espaço."}';
    }

    location /assets/ {
        try_files $uri =404;
        expires 7d;
    }

    location / {
        try_files $uri /index.html;
    }
}

server {
    listen 8081;
    server_name _;
    server_tokens off;
    root /usr/share/nginx/html;

    # Mesmo motivo do 8080: a API é recriada ao abrir e fechar a coleta.
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $api http://api:8000;

    # Só estudantes chegam por aqui. Nenhum log de acesso, e o de erro só no nível
    # crítico: em nível `error` o nginx registra o IP do cliente e a linha da
    # requisição — com o token — quando a API não responde.
    access_log off;
    error_log /dev/stderr crit;

    # 24 inteiros de 1 a 5 são algumas centenas de bytes. O 1,5 GB do 8080 é para o
    # áudio da aula, numa rota autenticada que esta porta nem serve.
    client_max_body_size 32k;

    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header X-Frame-Options "DENY" always;

    location /publico/ {
        proxy_pass $api;
        proxy_http_version 1.1;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
        proxy_set_header Host $host;
        # A API não precisa do IP do estudante, então não o recebe: com valor vazio o
        # nginx não envia o cabeçalho.
        proxy_set_header X-Forwarded-For "";
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /responder/ {
        try_files $uri /index.html;
    }

    location /assets/ {
        try_files $uri =404;
        expires 7d;
    }

    # Teste de alcance: o professor abre este endereço no próprio celular antes da
    # turma (docs/deploy-local.md). deploy/subir-coleta.sh procura a palavra
    # "funcionando" aqui para confirmar que a porta responde.
    location = / {
        default_type "text/html; charset=utf-8";
        return 200 '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>FIAS-ED</title></head><body><p>Conexão com o FIAS-ED funcionando.</p><p>Aguarde o link ou o QR code do professor.</p></body></html>';
    }

    # Todo o resto — /api/ incluído — não existe nesta porta: login e dados do professor
    # ficam fora do alcance dos celulares.
    location / {
        return 404;
    }
}
```

**Confira o `dist/index.html` do build do frontend:** se ele referenciar algum arquivo na raiz (`/favicon.svg`, `/manifest.webmanifest`...), a tela do estudante pela 8081 precisa carregá-lo — acrescente um `location = /<arquivo>` com `try_files $uri =404;` para cada um e diga no relatório. O que está em `/assets/` já é servido.

- [x] **Step 3: Compose — o serviço `web-lan` e o nome da imagem do banco**

No serviço `db`, logo depois do bloco `build:`, acrescente:

```yaml
    image: fias-ed-web-db:local
```

Depois do serviço `web`, acrescente:

```yaml
  # A única porta que os celulares alcançam (docs/deploy-local.md). Mesma imagem do
  # `web`, publicando só a 8081 — o servidor que serve só as rotas do estudante.
  # Profile "coleta": não sobe com `docker compose up`; quem abre é
  # deploy/subir-coleta.sh, no IP da rede da sala. Sem o script, FIAS_ED_LAN_IP cai
  # em 127.0.0.1 — o padrão é não expor nada.
  # restart "no": depois de reiniciar o computador, a porta da sala não reabre
  # sozinha; e, se o IP da sala tiver sumido, só este serviço falha — o `web` do
  # professor continua de pé.
  web-lan:
    <<: *hardening
    image: fias-ed-web-web:local
    restart: "no"
    profiles: ["coleta"]
    ports:
      - "${FIAS_ED_LAN_IP:-127.0.0.1}:${FIAS_ED_LAN_PORT:-8081}:8081"
    networks: [edge]
    depends_on:
      api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8081/"]
      interval: 10s
      timeout: 3s
      retries: 10
```

O `restart: "no"` vem **depois** do `<<: *hardening` e prevalece sobre o `unless-stopped` dele (chave explícita vence chave mesclada no YAML).

- [x] **Step 4: Construir e validar a configuração dentro da imagem**

```sh
docker compose build web
docker run --rm --entrypoint nginx fias-ed-web-web:local -t
```

Esperado: `nginx: configuration file /etc/nginx/nginx.conf test is successful`. Testar dentro da imagem evita montar arquivo do Windows no contêiner — foi montando assim que a W3b criou o diretório `deploy/nginx.conf;C`. Se esse diretório vazio ainda existir, apague-o (`rmdir "deploy/nginx.conf;C"`) e diga no relatório.

- [x] **Step 5: A matriz de rotas, com a 8081 presa em loopback para o teste**

```sh
docker compose up -d --no-build web
FIAS_ED_LAN_IP=127.0.0.1 docker compose --profile coleta up -d --no-build web-lan
curl -s http://127.0.0.1:8081/ | grep -c "Conexão com o FIAS-ED funcionando"          # 1
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081/api/health            # 404
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081/aulas                 # 404
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081/login                 # 404
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://127.0.0.1:8081/responder/X   # 200 text/html
curl -s -i http://127.0.0.1:8081/publico/qti/TOKEN_MATRIZ | head -1                  # HTTP/1.1 404 (da API)
curl -s http://127.0.0.1:8081/publico/qti/TOKEN_MATRIZ                               # {"error_code":"LINK_INVALIDO",...}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/health            # 200 — o professor não mudou
```

Carregue também um arquivo de `/assets/` pela 8081 (pegue o nome no `index.html` servido) e confira 200.

- [x] **Step 6: Nenhum token nem IP em log — inclusive com a API fora do ar**

```sh
curl -s -o /dev/null http://127.0.0.1:8080/responder/TOKEN_DEPOIS_8080
curl -s -o /dev/null http://127.0.0.1:8081/responder/TOKEN_DEPOIS_8081
curl -s -o /dev/null http://127.0.0.1:8081/publico/qti/TOKEN_DEPOIS_8081
docker compose stop api
curl -s -o /dev/null http://127.0.0.1:8080/publico/qti/TOKEN_API_FORA_8080
curl -s -o /dev/null http://127.0.0.1:8081/publico/qti/TOKEN_API_FORA_8081
docker compose start api
docker compose --profile coleta logs web web-lan --since 10m | grep -c "TOKEN_"
```

Esperado: `0`. Cole também `docker compose --profile coleta logs web-lan --since 10m | wc -l` — a 8081 não deve ter escrito nada que contenha endereço de cliente. Se o `grep` achar alguma linha, a tarefa não terminou.

- [x] **Step 6b: A API recriada não derruba o nginx**

```sh
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$(docker compose ps -q api)"
docker compose up -d --no-build --force-recreate --no-deps api
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$(docker compose ps -q api)"
sleep 15
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/health            # 200, sem reiniciar o web
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081/publico/qti/X          # 404 da API, não 502
```

Cole os dois IPs. Se forem iguais, a prova não exercitou a troca: diga isso, e force-a — pare a API, suba um contêiner qualquer na rede `fias-ed-web_edge` para ocupar o IP antigo (`docker run -d --rm --name ocupa-ip --network fias-ed-web_edge fias-ed-web-web:local`), suba a API de novo, repita os dois `curl`, e remova o `ocupa-ip`.

- [x] **Step 7: Exposição e política de reinício**

```sh
docker compose --profile coleta ps --format '{{.Service}} {{.Ports}}'
docker inspect --format '{{.HostConfig.RestartPolicy.Name}}' "$(docker compose --profile coleta ps -q web-lan)"
```

Esperado: só `web` (`127.0.0.1:8080->8080/tcp`) e `web-lan` (`127.0.0.1:8081->8081/tcp`) publicam porta; `db`, `api` e `worker` sem nenhuma. A política de `web-lan` é `no`.

- [ ] **Step 8: Mutação — o log de acesso volta em `/responder/`** — não feito: o classificador de segurança bloqueou a reconstrução com o log reativado; evidência equivalente no relatório da Task 1 (ledger, Ruling 5)

1. Apague a linha `access_log off;` do `location /responder/` do servidor 8080.
2. `docker compose build web && docker compose up -d --no-build web`, depois `curl -s -o /dev/null http://127.0.0.1:8080/responder/TOKEN_MUTACAO` e `docker compose logs web --since 2m | grep -c TOKEN_MUTACAO` → tem de dar `1`.
3. Restaure a linha, reconstrua, suba de novo, e repita o `curl` com outro token: `0`.

Três passos separados. Cole as saídas.

- [x] **Step 9: Fechar a 8081 e comitar**

```sh
docker compose --profile coleta rm --stop --force web-lan
git add fias-ed-web/deploy/nginx.conf fias-ed-web/docker-compose.yml
git commit
```

Mensagem: `feat(deploy): a porta dos celulares serve só o estudante, e nenhum log guarda token ou IP`, com o antes/depois do Step 1/6 resumido no corpo.

---

## Task 2: a URL do link vem da configuração, e o cookie funciona em HTTP

**Files:**
- Modify: `fias-ed-web/backend/app/core/config.py`
- Modify: `fias-ed-web/backend/app/qti/routes.py:51-66` (`gerar_link`)
- Modify: `fias-ed-web/backend/app/publico/routes.py` (`_COOKIE_KWARGS` e seus dois usos)
- Modify: `fias-ed-web/docker-compose.yml` (ambiente da `api`)
- Modify: `fias-ed-web/.env.example`
- Test: `fias-ed-web/backend/tests/test_qti_link_rotas.py`, `fias-ed-web/backend/tests/test_rotas_publicas.py`

**Interfaces:**
- Consumes: nada das tarefas anteriores.
- Produces: `Settings.public_url: str`, padrão `"http://localhost:8080"`, lido da variável de ambiente **`PUBLIC_URL`** do contêiner; no host, a variável de interpolação é **`FIAS_ED_PUBLIC_URL`** (a Task 6 a define). `gerar_link` devolve `url = f"{public_url sem barra final}/responder/{token}"`. O cookie `fias_qti_consentimento` é `Secure` se e somente se `public_url` começa com `https://`.

Por que: o professor gera o link em `localhost:8080`, e o estudante abre em `IP:8081`. `request.base_url` daria o endereço do professor. E um cookie `Secure` vindo de `http://` fora de localhost é descartado pelos navegadores atuais — na sala, sem TLS, o estudante aceitaria o convite e levaria 409 em todo envio.

- [x] **Step 1: Escrever os testes que falham**

Em `test_qti_link_rotas.py` (acrescente `from app.core.config import get_settings` aos imports):

```python
def test_a_url_do_link_vem_da_url_publica_configurada(db, client, ciclo, monkeypatch):
    """O professor gera o link em localhost:8080; o estudante abre em IP:8081. A URL
    não pode sair do cabeçalho da requisição do professor — sai da configuração."""
    monkeypatch.setenv("PUBLIC_URL", "http://192.168.137.1:8081")
    get_settings.cache_clear()
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.status_code == 201
    url = r.json()["url"]
    assert url.startswith("http://192.168.137.1:8081/responder/")
    assert "testserver" not in url


def test_sem_configuracao_o_link_aponta_para_esta_maquina(db, client, ciclo, monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    get_settings.cache_clear()
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/link",
                    json={"n_estudantes": 30, "dias": 7, "coletado_em": "2026-09-01"})
    assert r.json()["url"].startswith("http://localhost:8080/responder/")
```

Em `test_rotas_publicas.py` (use o auxiliar de consentimento que o arquivo já tiver; se não houver, este):

```python
def _atributos_do_cookie(set_cookie: str) -> list[str]:
    return [parte.strip().lower() for parte in set_cookie.split(";")]


def test_em_http_o_cookie_de_consentimento_nao_e_secure(db, client_publico, coleta_nativa, monkeypatch):
    """Na sala, sem TLS, a URL pública é http://IP:8081. Os navegadores descartam cookie
    Secure vindo de http fora de localhost, e o estudante receberia 409 em todo envio."""
    monkeypatch.setenv("PUBLIC_URL", "http://192.168.137.1:8081")
    get_settings.cache_clear()
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    r = client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    assert r.status_code == 201
    atributos = _atributos_do_cookie(r.headers["set-cookie"])
    assert atributos[0].startswith("fias_qti_consentimento=")
    assert "secure" not in atributos
    assert "httponly" in atributos
    assert "samesite=strict" in atributos
    assert "path=/publico" in atributos


def test_em_https_o_cookie_de_consentimento_e_secure(db, client_publico, coleta_nativa, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://fias.exemplo")
    get_settings.cache_clear()
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    r = client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    assert "secure" in _atributos_do_cookie(r.headers["set-cookie"])
```

O fixture `app_instance` limpa o cache de `get_settings` ao nascer e ao morrer, então o `cache_clear()` dentro do teste só precisa vir depois do `setenv`.

- [x] **Step 2: Rodar e ver falhar**

```sh
docker compose -f docker-compose.test.yml build api-test
docker compose -f docker-compose.test.yml run --rm api-test pytest -q tests/test_qti_link_rotas.py tests/test_rotas_publicas.py
```

Esperado: os dois testes de URL falham (`https://testserver/...`), e o de http falha (`secure` presente).

- [x] **Step 3: Implementar**

`config.py`, dentro de `Settings`, depois de `device_id`:

```python
    # Endereço que vai dentro do link do estudante. Na sala, deploy/subir-coleta.sh o
    # define como http://<IP da rede>:8081 (FIAS_ED_PUBLIC_URL no host). O padrão serve
    # a quem usa tudo nesta máquina.
    public_url: str = "http://localhost:8080"
```

`qti/routes.py`, em `gerar_link`: tire o parâmetro `request: Request` (e o `Request` do import, se ficar sem uso) e monte a URL assim:

```python
    base = get_settings().public_url.rstrip("/")
    return {"id": str(link.id),
            "url": f"{base}/responder/{token}",
            "expira_em": link.expira_em.isoformat(),
            "limite_respostas": link.limite_respostas}
```

com `from app.core.config import get_settings`. Mantenha o comentário sobre o token viajar só nesta resposta.

`publico/routes.py`: troque a constante `_COOKIE_KWARGS` por uma função, e use-a nos dois lugares que hoje passam `**_COOKIE_KWARGS`:

```python
def _cookie_kwargs() -> dict:
    # `Secure` segue o esquema da URL pública. Na sala, sem TLS, ela é http://IP:8081,
    # e os navegadores descartam cookie Secure vindo de http fora de localhost — o
    # estudante aceitaria o convite e levaria 409 em todo envio. Se um dia houver TLS,
    # a URL passa a https e o Secure volta sozinho.
    seguro = get_settings().public_url.startswith("https://")
    return {"httponly": True, "secure": seguro, "samesite": "strict", "path": "/publico"}
```

Atualize o comentário grande que hoje fica acima de `COOKIE_CONSENTIMENTO` para não afirmar mais que o cookie é sempre `Secure`.

`docker-compose.yml`: hoje o ambiente da `api` define a âncora `&api-env` e o `worker` a reusa (`environment: *api-env`). Mova o mapa para uma extensão no topo do arquivo, ao lado de `x-hardening` e `x-api-image`:

```yaml
x-api-env: &api-env
  DATABASE_URL: postgresql+psycopg://fias_ed_app:${FIAS_ED_APP_PASSWORD}@db:5432/fias_ed_web
  # ... (o resto das variáveis de hoje, sem mudança)
```

e deixe:

```yaml
  api:
    environment:
      <<: *api-env
      # Endereço que vai dentro do link do estudante; deploy/subir-coleta.sh o define na sala.
      PUBLIC_URL: ${FIAS_ED_PUBLIC_URL:-http://localhost:8080}
  worker:
    environment: *api-env
```

`PUBLIC_URL` só na `api`, de propósito: trocar a URL recria a `api`, e o `worker` não deve ser reiniciado no meio de um processamento de aula por causa disso.

`.env.example`, no fim:

```
# Definidas por deploy/subir-coleta.sh no dia da coleta — não precisam estar aqui.
#   FIAS_ED_LAN_IP      IP deste computador na rede da sala (padrão 127.0.0.1: fechado)
#   FIAS_ED_LAN_PORT    porta dos celulares (padrão 8081)
#   FIAS_ED_PUBLIC_URL  endereço que vai dentro do link do estudante (padrão http://localhost:8080)
```

- [x] **Step 4: Rodar e ver passar — e a suíte inteira**

```sh
docker compose -f docker-compose.test.yml build api-test
docker compose -f docker-compose.test.yml run --rm api-test pytest -q
docker compose config --quiet && echo compose-ok
```

Esperado: 554 passed (550 + 4), 6 deselected; `compose-ok`. Se algum teste antigo afirmar `https://testserver/responder/`, ele afirma o comportamento velho: atualize-o para a URL configurada e diga qual no relatório.

- [x] **Step 5: Mutações**

1. Volte `gerar_link` a usar `request.base_url` → `test_a_url_do_link_vem_da_url_publica_configurada` falha. Restaure.
2. Fixe `seguro = True` → `test_em_http_o_cookie_de_consentimento_nao_e_secure` falha. Restaure.
3. Fixe `seguro = False` → `test_em_https_o_cookie_de_consentimento_e_secure` falha. Restaure.

- [x] **Step 6: Commit**

`fix(publico): o link aponta para o endereço da sala, e o consentimento funciona sem TLS`

---

## Task 3: um link vivo por coleta, garantido pelo banco

**Files:**
- Create: `fias-ed-web/backend/alembic/versions/0011_um_link_vivo_por_coleta.py`
- Modify: `fias-ed-web/backend/app/models.py` (`LinkQTI`)
- Modify: `fias-ed-web/backend/app/qti/links.py` (`criar_link`)
- Modify: `fias-ed-web/backend/app/publico/routes.py` (`responder`)
- Modify: `fias-ed-web/backend/app/ciclos/routes.py` (comentário de `_links_vivos_por_ciclo`)
- Modify: `fias-ed-web/frontend/src/pages/Acompanhamentos.tsx` (texto do diálogo de gerar)
- Test: `fias-ed-web/backend/tests/test_link_qti.py`, `fias-ed-web/backend/tests/test_rotas_publicas.py`, `fias-ed-web/frontend/src/pages/Acompanhamentos.test.tsx`

**Interfaces:**
- Consumes: `criar_link(db, coleta, *, n_estudantes, dias) -> tuple[LinkQTI, str]` e `link_valido(db, token) -> LinkQTI | None`, de `app/qti/links.py`.
- Produces: índice único parcial **`uq_link_qti_um_vivo_por_coleta`** em `link_qti (coleta_id) WHERE revogado_em IS NULL AND deleted_at IS NULL`. `criar_link` mantém a assinatura e passa a: travar a coleta (`FOR UPDATE`), revogar os links não revogados dela, criar o novo — tudo numa transação.

**O problema, e por que a correção é esta.** A contagem de respostas é por coleta, o teto é por link, e a trava (`FOR UPDATE`) é na linha do link. Com dois links vivos na mesma coleta, dois envios simultâneos por links diferentes travam linhas diferentes, leem a mesma contagem e gravam os dois: o limite estoura e o `response_index` se repete (não há restrição que impeça). O banco de dev tem hoje **duas coletas com dois links vivos cada** (restos da verificação da W3b), então o estado existe de verdade.

A correção torna esse estado impossível: com um único link vivo por coleta, todo envio vivo disputa a mesma linha, e a trava do link já é, na prática, a trava da coleta. Falta fechar uma janela: um envio que passou por `link_valido` com o link ainda vivo, e cujo link é substituído antes de ele pegar a trava. Por isso `responder` revalida o link **com a trava na mão**.

- [x] **Step 1: Testes que falham — `test_link_qti.py`**

```python
import threading
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal, get_engine
from app.models import ColetaQTI, LinkQTI


def test_criar_um_segundo_link_revoga_o_primeiro(db, coleta_nativa):
    primeiro, token1 = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    segundo, token2 = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, token1) is None
    assert link_valido(db, token2).id == segundo.id


def test_criar_link_nao_revoga_o_de_outra_coleta(db, ciclo, coleta_nativa):
    outra = ColetaQTI(ciclo_id=ciclo.id, coletado_em=date(2026, 10, 1), origem="COLETA_NATIVA",
                      response_count=0, displayable=False, qti_config_version="1.0.0")
    db.add(outra)
    db.commit()
    _, token_da_outra = criar_link(db, outra, n_estudantes=30, dias=7)
    criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, token_da_outra) is not None


def test_o_banco_recusa_dois_links_vivos_na_mesma_coleta(db, coleta_nativa):
    """A garantia não pode depender só de criar_link: a restrição é do banco."""
    agora = dt.datetime.now(dt.timezone.utc)
    for sufixo in ("a", "b"):
        db.add(LinkQTI(coleta_id=coleta_nativa.id, token_hash=sufixo * 64,
                       expira_em=agora + dt.timedelta(days=7), limite_respostas=33))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_um_link_revogado_nao_impede_outro_vivo(db, coleta_nativa):
    """O índice é parcial: revogado ou apagado não conta."""
    agora = dt.datetime.now(dt.timezone.utc)
    db.add(LinkQTI(coleta_id=coleta_nativa.id, token_hash="a" * 64, revogado_em=agora,
                   expira_em=agora + dt.timedelta(days=7), limite_respostas=33))
    db.add(LinkQTI(coleta_id=coleta_nativa.id, token_hash="b" * 64,
                   expira_em=agora + dt.timedelta(days=7), limite_respostas=33))
    db.commit()


def test_criar_link_espera_quem_esta_criando_outro_para_a_mesma_coleta(db, coleta_nativa):
    """Dois cliques em "gerar link" disputam a coleta. Quem chega depois tem de esperar o
    primeiro terminar — senão não enxerga o link que ele criou, não o revoga, e o banco
    recusa o segundo link vivo com erro 500.

    A outra sessão trava a coleta com FOR NO KEY UPDATE, de propósito: esse modo conflita
    com o FOR UPDATE de criar_link, mas NÃO com o FOR KEY SHARE que a chave estrangeira do
    INSERT em link_qti pede. Então só um criar_link que trave a coleta de verdade espera —
    sem a trava, ele passaria direto e este teste cairia."""
    segurando = SessionLocal(bind=get_engine())
    segurando.execute(text("SELECT 1 FROM coleta_qti WHERE id = :id FOR NO KEY UPDATE"),
                      {"id": coleta_nativa.id})
    resultado = {}

    def gerar():
        with SessionLocal(bind=get_engine()) as s:
            coleta = s.get(ColetaQTI, coleta_nativa.id)
            resultado["link"], _ = criar_link(s, coleta, n_estudantes=30, dias=7)

    t = threading.Thread(target=gerar)
    t.start()
    t.join(timeout=1.0)
    try:
        assert t.is_alive(), "criar_link não esperou a trava da coleta"
    finally:
        segurando.commit()
        segurando.close()
        t.join(timeout=10)
    assert "link" in resultado
```

(`dt` e `pytest` o arquivo já importa; confira.)

- [x] **Step 2: Testes que falham — `test_rotas_publicas.py`**

`RESPOSTAS` é a constante que o arquivo já tem (`{str(i): 4 for i in range(1, 25)}`).

```python
def test_o_limite_segue_o_link_mais_recente(db, client_publico, coleta_nativa):
    _, token_antigo = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)   # teto 33
    _, token_novo = criar_link(db, coleta_nativa, n_estudantes=2, dias=7)      # teto 3
    assert client_publico.get(f"/publico/qti/{token_antigo}").status_code == 404
    assert client_publico.post(f"/publico/qti/{token_novo}/consentir",
                               json={"documento_versao": "1.0.0"}).status_code == 201
    codigos = [client_publico.post(f"/publico/qti/{token_novo}/responder",
                                   json={"respostas": RESPOSTAS}).status_code for _ in range(4)]
    assert codigos == [201, 201, 201, 409]


def test_link_substituido_entre_a_validacao_e_a_trava_nao_grava(db, client_publico, coleta_nativa,
                                                                monkeypatch):
    """A janela que a revalidação fecha: `link_valido` viu o link vivo e, antes de a
    trava ser tomada, o professor gerou outro — o que revoga este. Sem revalidar com a
    trava na mão, a resposta entraria por um link já desativado, em paralelo com as do
    link novo."""
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert client_publico.post(f"/publico/qti/{token}/consentir",
                               json={"documento_versao": "1.0.0"}).status_code == 201
    import app.publico.routes as rotas
    original = rotas.link_valido

    def valido_e_logo_substituido(sessao, tok):
        vivo = original(sessao, tok)
        with SessionLocal(bind=get_engine()) as outra:
            criar_link(outra, outra.get(ColetaQTI, coleta_nativa.id), n_estudantes=30, dias=7)
        return vivo

    monkeypatch.setattr(rotas, "link_valido", valido_e_logo_substituido)
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 404
    assert db.query(RespostaQTI).count() == 0
```

**Armadilha que este segundo teste existe para pegar:** depois de `link_valido`, o objeto do link já está no mapa de identidade da sessão da rota. Um `select(LinkQTI)...with_for_update()` comum devolve **o mesmo objeto, com os atributos velhos** (`revogado_em = None`), mesmo que o banco já diga outra coisa. A revalidação só funciona com `.execution_options(populate_existing=True)`. Se você revalidar sem isso, este teste falha — é o teste funcionando.

- [x] **Step 3: Teste que falha — o aviso no diálogo**

Em `Acompanhamentos.test.tsx`, no molde dos testes do diálogo de gerar link que já existem:

```tsx
test("o diálogo de gerar avisa que um novo link desativa o anterior da mesma data", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: /gerar link/i }));
  expect(within(screen.getByRole("dialog")).getByText(/desativa o anterior/i)).toBeInTheDocument();
});
```

- [x] **Step 4: Rodar e ver falhar**

Backend e frontend, com a imagem de teste reconstruída. Esperado: os testes novos falham; o de "banco recusa" falha porque o `commit` passa.

- [x] **Step 5: A migração**

`0011_um_link_vivo_por_coleta.py`, no estilo da `0010` (docstring longa com o porquê e a verificação feita):

```python
"""um link vivo por coleta

A contagem de respostas é por coleta, o teto é por link, e o FOR UPDATE de
app/publico/routes.py trava a linha do link. Com dois links vivos na mesma coleta,
dois envios por links diferentes travam linhas diferentes, leem a mesma contagem e
gravam os dois: o limite estoura e o response_index se repete. Achado da verificação
final da W3b; decisão do pesquisador (2026-09-26): corrigir, não só documentar.

Esta migração torna o estado impossível no banco: no máximo um link não revogado e
não apagado por coleta. Links já expirados contam — criar_link revoga todos os não
revogados da coleta antes de criar o novo, então o índice e o código concordam.

Dado existente. Antes de criar o índice, os links excedentes são REVOGADOS (não
apagados): em cada coleta fica vivo só o mais recente (created_at, depois id). No
banco de desenvolvimento, em 2026-09-26, eram 2 coletas com 2 links vivos cada,
restos da verificação da W3b:

    SELECT count(*), sum(n - 1) FROM (
      SELECT coleta_id, count(*) n FROM link_qti
      WHERE revogado_em IS NULL AND deleted_at IS NULL
      GROUP BY 1 HAVING count(*) > 1) x;
    -- 2 | 2

Revogar é o que a regra nova faria com eles de qualquer jeito, no próximo link
gerado; aqui só acontece antes.
"""
import sqlalchemy as sa
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    revogados = op.get_bind().execute(sa.text("""
        UPDATE link_qti SET revogado_em = now(), updated_at = now()
        WHERE revogado_em IS NULL AND deleted_at IS NULL
          AND id NOT IN (
            SELECT DISTINCT ON (coleta_id) id FROM link_qti
            WHERE revogado_em IS NULL AND deleted_at IS NULL
            ORDER BY coleta_id, created_at DESC, id DESC)
    """)).rowcount
    print(f"0011: {revogados} link(s) excedente(s) revogado(s)")
    op.create_index("uq_link_qti_um_vivo_por_coleta", "link_qti", ["coleta_id"], unique=True,
                    postgresql_where=sa.text("revogado_em IS NULL AND deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_link_qti_um_vivo_por_coleta", table_name="link_qti")
```

Confira os nomes `revision`/`down_revision` e o formato no topo da `0010` e siga-os. `LinkQTI` replica os campos de auditoria sem `EntityMixin`; confira que `updated_at` existe na tabela antes de usá-lo no `UPDATE` (existe: `models.py`, classe `LinkQTI`).

No modelo, em `LinkQTI`, espelhe o índice (o padrão da `0010` foi espelhar a restrição no modelo):

```python
    __table_args__ = (
        Index("uq_link_qti_um_vivo_por_coleta", "coleta_id", unique=True,
              postgresql_where=text("revogado_em IS NULL AND deleted_at IS NULL")),
    )
```

- [x] **Step 6: `criar_link` e a revalidação**

`links.py` — trave a coleta, revogue, crie, numa transação só:

```python
def criar_link(db: Session, coleta: ColetaQTI, *, n_estudantes: int, dias: int) -> tuple[LinkQTI, str]:
    agora = dt.datetime.now(timezone.utc)
    # Um link vivo por coleta (índice uq_link_qti_um_vivo_por_coleta, migração 0011).
    # A trava na coleta serializa dois pedidos simultâneos: quem chega depois espera,
    # enxerga o link que o primeiro criou e o revoga — em vez de esbarrar no índice.
    db.execute(select(ColetaQTI.id).where(ColetaQTI.id == coleta.id).with_for_update())
    db.execute(update(LinkQTI)
               .where(LinkQTI.coleta_id == coleta.id,
                      LinkQTI.revogado_em.is_(None),
                      LinkQTI.deleted_at.is_(None))
               .values(revogado_em=agora))
    token = secrets.token_urlsafe(32)
    link = LinkQTI(
        coleta_id=coleta.id,
        token_hash=_hash(token),
        expira_em=agora + dt.timedelta(days=dias),
        # (o comentário longo sobre aritmética inteira fica como está)
        limite_respostas=math.ceil(n_estudantes * 11 / 10),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link, token
```

(`update` vem de `sqlalchemy`.) Atualize o docstring do módulo se ele contradisser a regra nova.

`publico/routes.py`, em `responder`, onde hoje está a trava do link:

```python
    # O limite é conferido sob FOR UPDATE do LinkQTI, na mesma transação do INSERT.
    # Com um link vivo por coleta (migração 0011), todo envio vivo disputa esta mesma
    # linha. `populate_existing` é obrigatório: sem ele o SELECT devolve o objeto que
    # `link_valido` já carregou nesta sessão, com os atributos de antes.
    link_travado = db.execute(select(LinkQTI).where(LinkQTI.id == link.id)
                              .with_for_update()
                              .execution_options(populate_existing=True)).scalar_one()
    # Revalida com a trava na mão: entre `link_valido` e aqui o professor pode ter
    # gerado outro link para a mesma data — o que revoga este — ou revogado à mão.
    agora = dt.datetime.now(timezone.utc)
    if (link_travado.revogado_em is not None or link_travado.deleted_at is not None
            or link_travado.expira_em <= agora):
        db.rollback()
        raise _link_invalido()
```

O resto (contagem, limite, INSERT) segue igual. `_link_invalido()` devolve a mesma mensagem de sempre, de propósito.

`ciclos/routes.py`: o comentário de `_links_vivos_por_ciclo` diz que dois cliques deixam dois links vivos na mesma coleta — deixou de ser verdade. Reescreva: a lista continua lista porque um acompanhamento tem várias datas, cada uma com no máximo um link vivo.

`Acompanhamentos.tsx`: no diálogo de gerar link, acrescente o parágrafo:

> Gerar um novo link para a mesma data desativa o anterior: o QR code que estiver projetado deixa de funcionar.

- [x] **Step 7: Rodar e ver passar**

```sh
docker compose -f docker-compose.test.yml build api-test
docker compose -f docker-compose.test.yml rm -fsv db-test
docker compose -f docker-compose.test.yml run --rm api-test pytest -q
cd frontend && npx vitest run && npm run lint && npm run build
```

O `rm -fsv db-test` é obrigatório aqui: a migração nova precisa rodar num banco que não a tenha visto.

**Testes que afirmam o comportamento velho** (dois links vivos na mesma coleta, a lista `links_qti` com dois itens na mesma data, o teto do link mais permissivo) vão falhar. Eles estão certos em falhar: atualize-os para a regra nova, **não os afrouxe**, e liste no relatório cada um que mudou e por quê.

- [x] **Step 8: Mutações**

1. Tire o `UPDATE` que revoga, em `criar_link` → `test_criar_um_segundo_link_revoga_o_primeiro` falha. Restaure.
2. Tire a linha do `with_for_update()` sobre a coleta, em `criar_link` → `test_criar_link_espera_quem_esta_criando_outro_para_a_mesma_coleta` falha. Restaure.
3. Tire o `populate_existing=True` (mantenha a revalidação) → `test_link_substituido_entre_a_validacao_e_a_trava_nao_grava` falha. Restaure.
4. Tire o `postgresql_where` da migração, recrie o `db-test` → `test_um_link_revogado_nao_impede_outro_vivo` falha. Restaure e recrie de novo.

- [x] **Step 9: Aplicar no banco de desenvolvimento**

```sh
docker compose build api
docker compose run --rm migrate
docker compose exec -T db psql -U postgres -d fias_ed_web -tAc "select version_num from alembic_version"
docker compose up -d --no-build api worker
```

Esperado: a saída do migrate mostra `0011: 2 link(s) excedente(s) revogado(s)` (ou o número que houver, com a explicação), e a versão é `0011`.

- [x] **Step 10: Commit**

`fix(qti): um link vivo por coleta, garantido pelo banco, e o envio revalida o link com a trava`

---

## Task 4: uma coleta viva por acompanhamento e data

**Files:**
- Create: `fias-ed-web/backend/alembic/versions/0012_uma_coleta_viva_por_data.py`
- Modify: `fias-ed-web/backend/app/models.py` (`ColetaQTI`)
- Modify: `fias-ed-web/backend/app/qti/service.py` (`coleta_nativa_do_dia`, `importar_relatorio`)
- Test: `fias-ed-web/backend/tests/test_coleta_nativa_modelo.py`, `fias-ed-web/backend/tests/test_qti_import.py`, `fias-ed-web/backend/tests/test_triangulacao.py`, `fias-ed-web/backend/tests/test_export_w3.py`

**Interfaces:**
- Consumes: `coleta_nativa_do_dia(db, ciclo, data) -> ColetaQTI` e `importar_relatorio(db, ciclo, texto, coletado_em) -> ColetaQTI`.
- Produces: índice único parcial **`uq_coleta_qti_ciclo_data_viva`** em `coleta_qti (ciclo_id, coletado_em) WHERE deleted_at IS NULL`. Código de erro novo **`COLETA_CONCORRENTE`** (409) para a importação que perde a corrida.

**Parcial, e não simples:** reimportar na mesma data apaga logicamente a coleta antiga e cria outra na mesma data (`importar_relatorio`, "reimportar substitui"). Uma UNIQUE simples em `(ciclo_id, coletado_em)` quebraria isso.

**Três testes da W3a descrevem um estado que passa a ser impossível** — duas coletas vivas na mesma data, montadas de propósito para testar o desempate:

- `test_export_w3.py::test_duas_coletas_na_mesma_data_escolhem_sempre_a_mesma`
- `test_triangulacao.py::test_duas_coletas_na_mesma_data_escolhem_sempre_a_criada_por_ultimo`
- `test_triangulacao.py::test_duas_coletas_com_created_at_empatado_escolhem_sempre_a_de_maior_id`

Com o índice, o `coleta_em` do segundo lado estoura antes de o teste começar. Apague os três e ponha no lugar os testes de que o banco recusa (Step 1). **O código de desempate (`coleta_vigente`, a ordenação da exportação) fica como está** — é defesa inofensiva, e tirá-lo é refatoração fora do escopo. O banco de dev tem hoje 14 coletas vivas e **nenhuma** violação (conferido em 2026-09-26).

- [x] **Step 1: Testes que falham — `test_coleta_nativa_modelo.py`**

```python
import datetime as dt
from datetime import date

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal, get_engine
from app.models import ColetaQTI
from app.qti.service import coleta_nativa_do_dia


def _coleta(ciclo, data, **extra):
    return ColetaQTI(ciclo_id=ciclo.id, coletado_em=data, origem="COLETA_NATIVA", response_count=0,
                     displayable=False, qti_config_version="1.0.0", **extra)


def test_o_banco_recusa_duas_coletas_vivas_na_mesma_data(db, ciclo):
    db.add(_coleta(ciclo, date(2026, 9, 1)))
    db.add(_coleta(ciclo, date(2026, 9, 1)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_uma_coleta_apagada_nao_impede_outra_na_mesma_data(db, ciclo):
    """O índice é parcial — é o que mantém a reimportação funcionando."""
    db.add(_coleta(ciclo, date(2026, 9, 1), deleted_at=dt.datetime.now(dt.timezone.utc)))
    db.add(_coleta(ciclo, date(2026, 9, 1)))
    db.commit()


def test_dois_pedidos_simultaneos_de_link_reusam_a_mesma_coleta(db, ciclo):
    """Dois cliques em "gerar link": os dois procuram a coleta do dia, não acham, e os
    dois tentam criá-la. Aqui a corrida é reproduzida sem thread: logo antes do INSERT
    desta sessão, outra sessão cria e comita a mesma coleta. O índice recusa a segunda;
    coleta_nativa_do_dia tem de reler e devolver a que ganhou, sem erro 500."""
    disparou = []

    def outra_sessao_chega_antes(sessao, contexto, instancias):
        # Só no flush que vai inserir a coleta — nunca num flush anterior qualquer.
        if disparou or not any(isinstance(o, ColetaQTI) for o in sessao.new):
            return
        disparou.append(True)
        with SessionLocal(bind=get_engine()) as outra:
            outra.add(_coleta(ciclo, date(2026, 9, 1)))
            outra.commit()

    event.listen(db, "before_flush", outra_sessao_chega_antes)
    try:
        coleta = coleta_nativa_do_dia(db, ciclo, date(2026, 9, 1))
    finally:
        event.remove(db, "before_flush", outra_sessao_chega_antes)
    assert disparou, "a corrida não foi montada: o flush da coleta não aconteceu"
    db.commit()
    vivas = db.query(ColetaQTI).filter(ColetaQTI.deleted_at.is_(None)).all()
    assert len(vivas) == 1
    assert coleta.id == vivas[0].id
```

Em `test_qti_import.py`, a corrida do lado da importação, com o `_csv(12)` que o arquivo já tem:

```python
def test_importacao_que_perde_a_corrida_devolve_409_e_nao_500(db, client, ciclo):
    disparou = []

    def outra_importacao_chega_antes(sessao, contexto, instancias):
        # Só no flush que vai inserir a coleta. A rota faz outros flushes antes (a
        # sessão do professor atualiza `last_seen_at`); disparar num deles criaria a
        # coleta concorrente cedo demais, a importação a acharia como "anterior", e o
        # teste passaria sem corrida nenhuma.
        if disparou or not any(isinstance(o, ColetaQTI) for o in sessao.new):
            return
        disparou.append(True)
        with SessionLocal(bind=get_engine()) as outra:
            outra.add(ColetaQTI(ciclo_id=ciclo.id, coletado_em=date(2026, 9, 1),
                                origem="IMPORTACAO_EXTERNA", response_count=12, displayable=True,
                                qti_config_version="1.0.0"))
            outra.commit()

    login(client, "professora-ciclo")
    # A rota usa a própria sessão, não a `db` do teste: escute na classe Session —
    # depois do login, e removendo no fim para não vazar para os outros testes.
    event.listen(Session, "before_flush", outra_importacao_chega_antes)
    try:
        r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                        data={"coletado_em": "2026-09-01"},
                        files={"arquivo": ("export.csv", _csv(12), "text/csv")})
    finally:
        event.remove(Session, "before_flush", outra_importacao_chega_antes)
    assert disparou, "a corrida não foi montada: o flush da coleta não aconteceu"
    assert r.status_code == 409
    assert r.json()["error_code"] == "COLETA_CONCORRENTE"
```

(`Session` de `sqlalchemy.orm`.)

- [x] **Step 2: Apagar os três testes de desempate**

Apague as três funções listadas acima. Não apague `coleta_em`, `coleta_vigente` nem nada fora dessas três funções.

- [x] **Step 3: Rodar e ver falhar**

Esperado: os dois testes de banco falham (o `commit` duplicado passa); o de corrida passa por acaso ou falha — sem o índice não há `IntegrityError` para tratar, então ele pode passar com **duas** coletas vivas: confira que a asserção `len(vivas) == 1` é a que cai.

- [x] **Step 4: A migração**

`0012_uma_coleta_viva_por_data.py`, mesmo estilo da `0011`:

```python
"""uma coleta viva por acompanhamento e data

coleta_nativa_do_dia reusa a coleta viva da data, e importar_relatorio apaga
logicamente a anterior antes de criar a nova: as duas funções já mantêm, no código,
"no máximo uma coleta viva por (ciclo, data)". Faltava o banco. Sem ele, dois
pedidos simultâneos — dois cliques em "gerar link", ou duas importações — passam os
dois pela consulta, não acham nada e criam duas coletas vivas; a triangulação passa a
escolher entre elas pelo desempate, e o professor vê números de uma coleta que não é
a que ele acabou de enviar.

Parcial (WHERE deleted_at IS NULL) de propósito: a reimportação cria uma coleta nova
na mesma data de uma que ela acabou de apagar logicamente.

Dado existente, conferido no banco de desenvolvimento em 2026-09-26: 14 coletas
vivas, nenhuma violação. Se uma instalação tiver violação, esta migração PARA com a
contagem, sem apagar nada: qual das coletas vale é decisão humana.
"""
import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicadas = op.get_bind().execute(sa.text("""
        SELECT count(*) FROM (
          SELECT ciclo_id, coletado_em FROM coleta_qti WHERE deleted_at IS NULL
          GROUP BY 1, 2 HAVING count(*) > 1) d
    """)).scalar_one()
    if duplicadas:
        raise RuntimeError(
            f"{duplicadas} par(es) (acompanhamento, data) com mais de uma coleta viva. "
            "Decida à mão qual vale antes de migrar; esta migração não apaga nada.")
    op.create_index("uq_coleta_qti_ciclo_data_viva", "coleta_qti", ["ciclo_id", "coletado_em"],
                    unique=True, postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_coleta_qti_ciclo_data_viva", table_name="coleta_qti")
```

No modelo `ColetaQTI`, espelhe:

```python
    __table_args__ = (
        Index("uq_coleta_qti_ciclo_data_viva", "ciclo_id", "coletado_em", unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )
```

- [x] **Step 5: Tratar a corrida nas duas funções**

`coleta_nativa_do_dia`: extraia a consulta e a decisão (reusar a nativa, recusar a importada) numa função interna, e envolva a criação num savepoint:

```python
def _coleta_viva_da_data(db: Session, ciclo: Ciclo, data: dt.date) -> ColetaQTI | None:
    return db.execute(
        select(ColetaQTI).where(ColetaQTI.ciclo_id == ciclo.id,
                                ColetaQTI.coletado_em == data,
                                ColetaQTI.deleted_at.is_(None))
    ).scalars().first()


def _reusar_ou_recusar(existente: ColetaQTI) -> ColetaQTI:
    if existente.origem == "COLETA_NATIVA":
        return existente
    raise AppError(409, "COLETA_JA_EXISTE",
                   "Já existe um relatório importado para esta data. Use outra data, "
                   "ou apague a coleta importada antes de gerar o link.")


def coleta_nativa_do_dia(db: Session, ciclo: Ciclo, data: dt.date) -> ColetaQTI:
    """(docstring de hoje, mais:) A restrição uq_coleta_qti_ciclo_data_viva
    (migração 0012) é quem decide a corrida entre dois pedidos simultâneos; aqui
    só se relê o que ganhou e se aplica a mesma regra."""
    existente = _coleta_viva_da_data(db, ciclo, data)
    if existente is not None:
        return _reusar_ou_recusar(existente)
    cfg = load_rules("qti_config")
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=data, origem="COLETA_NATIVA",
                       response_count=0, displayable=False,
                       qti_config_version=cfg["rules_version"], cabecalho_recebido=None)
    try:
        with db.begin_nested():
            db.add(coleta)
            db.flush()
    except IntegrityError:
        # Outro pedido criou a coleta desta data entre a consulta e o INSERT.
        return _reusar_ou_recusar(_coleta_viva_da_data(db, ciclo, data))
    return coleta
```

`importar_relatorio`: logo depois de `anterior.deleted_at = utcnow()`, acrescente `db.flush()` — a ordem "apaga a anterior, depois cria a nova" não pode depender da ordem interna do unit of work. E envolva o `db.add(coleta); db.flush()` assim:

```python
    try:
        with db.begin_nested():
            db.add(coleta)
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "COLETA_CONCORRENTE",
                       "Outra importação para esta data terminou agora. Recarregue a página "
                       "e confira qual relatório ficou.") from exc
```

O projeto centraliza mensagens em `app/core/messages.py`: registre `COLETA_CONCORRENTE` lá, no molde da entrada `QTI_SEM_RESPOSTAS`, e use `error_message("COLETA_CONCORRENTE")` no lugar do texto literal acima.

- [x] **Step 6: Rodar e ver passar**

```sh
docker compose -f docker-compose.test.yml build api-test
docker compose -f docker-compose.test.yml rm -fsv db-test
docker compose -f docker-compose.test.yml run --rm api-test pytest -q
```

Conte: 3 testes a menos (os de desempate) e os novos a mais. Diga o número de partida e o de chegada no relatório, com a conta.

- [x] **Step 7: Mutações**

1. Tire o `postgresql_where` da migração (recrie o `db-test`) → `test_uma_coleta_apagada_nao_impede_outra_na_mesma_data` e o teste de reimportação (`test_reimportar_na_mesma_data_substitui_em_vez_de_duplicar`) falham. Restaure e recrie.
2. Tire o `try/except IntegrityError` de `coleta_nativa_do_dia` → `test_dois_pedidos_simultaneos_de_link_reusam_a_mesma_coleta` falha. Restaure.
3. Tire o `try/except` de `importar_relatorio` → `test_importacao_que_perde_a_corrida_devolve_409_e_nao_500` falha com 500. Restaure.

- [x] **Step 8: Aplicar no banco de desenvolvimento**

```sh
docker compose build api && docker compose run --rm migrate
docker compose exec -T db psql -U postgres -d fias_ed_web -tAc "select version_num from alembic_version"   # 0012
docker compose up -d --no-build api worker
```

- [x] **Step 9: Commit**

`fix(qti): uma coleta viva por acompanhamento e data, e a corrida vira 409 em vez de 500`

---

## Task 5: o QR code na tela do professor

**Files:**
- Create: `fias-ed-web/frontend/src/design/components/QrCode.tsx`, `fias-ed-web/frontend/src/design/components/QrCode.test.tsx`
- Modify: `fias-ed-web/frontend/src/pages/Acompanhamentos.tsx`, `fias-ed-web/frontend/src/pages/Acompanhamentos.test.tsx`
- Modify: `fias-ed-web/frontend/src/test-utils.tsx` (leitor de QR para os testes)
- Modify: `fias-ed-web/frontend/src/design/components.css` (ou o CSS de componentes que o projeto usa)
- Modify: `fias-ed-web/frontend/package.json`, `package-lock.json`
- Modify: `THIRD_PARTY_LICENSES.md`

**Interfaces:**
- Consumes: `LinkQtiGerado` (`src/api/types.ts`): `{id, url, expira_em, limite_respostas}`.
- Produces: `QrCode({ valor: string; rotulo: string; className?: string })` → `<svg role="img" aria-label={rotulo}>`; módulos escuros como `<rect>` dentro de `<g class="qr__modulos">`, com a zona de silêncio de 4 módulos incluída no `viewBox`. `lerQr(svg: SVGSVGElement): string | null` em `src/test-utils.tsx`.

**Por que na tela e não no script:** o QR projetado precisa conter o token, e o token só existe na tela do professor, no instante em que o link é gerado — nem o banco o reconstrói.

**Dependências:**
- Execução: **`uqr`** (MIT, sem dependências, ESM, com tipos) — `encode(texto, { border: 4, ecc: "M" })` devolve `{ data: boolean[][], size }`, com a borda incluída. Confira a API e a licença na versão que instalar; se algo não bater, `qrcode-generator` (MIT) é a alternativa. **Diga qual usou.**
- Teste: **`jsqr`** (Apache-2.0, sem dependências), só em `devDependencies` — o leitor independente que prova que o desenho decodifica.
- `npm audit --audit-level=high` tem de continuar limpo. Registre a de execução em `THIRD_PARTY_LICENSES.md`, no formato das entradas que já existem.

- [x] **Step 1: O leitor de QR dos testes, em `test-utils.tsx`**

```tsx
import jsQR from "jsqr";

/** Rasteriza o SVG do <QrCode> (módulos escuros sobre fundo claro) e o decodifica com
 * um leitor independente. É o que prova que o desenho é um QR de verdade e que ele
 * carrega exatamente o texto pedido — e não só que o componente recebeu o texto. */
export function lerQr(svg: SVGSVGElement): string | null {
  const lado = Number(svg.getAttribute("viewBox")!.split(" ")[2]);
  const escala = 8;
  const px = lado * escala;
  const rgba = new Uint8ClampedArray(px * px * 4).fill(255);
  svg.querySelectorAll(".qr__modulos rect").forEach((r) => {
    const x = Number(r.getAttribute("x"));
    const y = Number(r.getAttribute("y"));
    for (let dy = 0; dy < escala; dy++) {
      for (let dx = 0; dx < escala; dx++) {
        const i = ((y * escala + dy) * px + (x * escala + dx)) * 4;
        rgba[i] = rgba[i + 1] = rgba[i + 2] = 0;
      }
    }
  });
  return jsQR(rgba, px, px)?.data ?? null;
}
```

- [x] **Step 2: Testes que falham — `QrCode.test.tsx`**

```tsx
import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { lerQr } from "../../test-utils";
import { QrCode } from "./QrCode";

const URL_DO_LINK = "http://192.168.137.1:8081/responder/AbC-123_xyzTokenDeTeste0987654321abcdEFGH";

test("o QR desenhado decodifica exatamente para a URL do link", () => {
  const { container } = render(<QrCode valor={URL_DO_LINK} rotulo="QR code do link" />);
  expect(lerQr(container.querySelector("svg")!)).toBe(URL_DO_LINK);
});

test("o QR tem nome acessível", () => {
  const { getByRole } = render(<QrCode valor={URL_DO_LINK} rotulo="QR code do link" />);
  expect(getByRole("img", { name: "QR code do link" })).toBeInTheDocument();
});
```

- [x] **Step 3: Testes que falham — `Acompanhamentos.test.tsx`**

No molde do teste que já existe, "gerar o link mostra a url uma vez, com aviso de que não se recupera":

```tsx
async function gerarLink() {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
    "POST /api/ciclos/c1/qti/link": () => jsonResponse(
      { id: "lk1", url: "http://x/responder/tok123", expira_em: "2026-10-03T00:00:00Z", limite_respostas: 33 }, 201),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: /gerar link/i }));
  const dialog = screen.getByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/quantos estudantes/i), "30");
  await userEvent.click(within(dialog).getByRole("button", { name: /^gerar$/i }));
  await screen.findByText(/responder\/tok123/);
}

test("gerar o link mostra o QR code, que decodifica para a url devolvida", async () => {
  await gerarLink();
  const qr = screen.getByRole("img", { name: /qr code do link/i });
  expect(lerQr(qr as unknown as SVGSVGElement)).toBe("http://x/responder/tok123");
});

test("mostrar para projetar abre o QR grande num diálogo", async () => {
  await gerarLink();
  await userEvent.click(screen.getByRole("button", { name: /mostrar para projetar/i }));
  const dialogo = screen.getByRole("dialog");
  const qr = within(dialogo).getByRole("img", { name: /qr code do link/i });
  expect(lerQr(qr as unknown as SVGSVGElement)).toBe("http://x/responder/tok123");
});
```

(`lerQr` vem de `../test-utils`, junto dos outros auxiliares que o arquivo já importa. Se o teste que já existe, "gerar o link mostra a url uma vez...", puder usar `gerarLink()` também, troque — é o mesmo percurso.)

E, no teste que já existe "a tela não mostra o link antigo ao reabrir a lista", acrescente:

```tsx
  expect(screen.queryByRole("img", { name: /qr code/i })).not.toBeInTheDocument();
```

- [x] **Step 4: Rodar e ver falhar**

`cd frontend && npx vitest run` — os novos falham (componente e botão não existem).

- [x] **Step 5: Implementar**

```sh
cd frontend && npm install uqr && npm install -D jsqr
```

`QrCode.tsx`:

```tsx
import { encode } from "uqr";

type Props = { valor: string; rotulo: string; className?: string };

/** QR code em SVG puro — sem canvas, sem innerHTML, sem data: URL, então nada muda na
 * CSP. `border: 4` é a zona de silêncio que os leitores exigem; `ecc: "M"` aguenta
 * projetor desfocado e reflexo na tela sem inflar o desenho. */
export function QrCode({ valor, rotulo, className = "qr" }: Props) {
  const { data, size } = encode(valor, { border: 4, ecc: "M" });
  const modulos = [];
  for (let y = 0; y < data.length; y++) {
    for (let x = 0; x < data[y].length; x++) {
      if (data[y][x]) modulos.push(<rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} />);
    }
  }
  return (
    <svg className={className} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={rotulo}
      shapeRendering="crispEdges">
      <rect className="qr__fundo" width={size} height={size} />
      <g className="qr__modulos">{modulos}</g>
    </svg>
  );
}
```

CSS, no arquivo de componentes do projeto — só tokens:

```css
.qr { display: block; width: 100%; max-width: 16rem; height: auto; }
.qr--projetar { max-width: min(80vh, 90vw); margin-inline: auto; }
.qr__fundo { fill: var(--color-white); }
.qr__modulos { fill: var(--color-navy); }
```

(`--color-navy` sobre `--color-white` dá contraste de sobra para leitor de QR. O projeto não tem tema escuro, então não há inversão de cores a tratar.)

`Acompanhamentos.tsx`, onde hoje aparecem a URL, o botão "Copiar link" e o aviso "Guarde-o agora: não será possível vê-lo de novo.":

- o `<QrCode valor={linkGerado.url} rotulo="QR code do link para os estudantes" />` junto da URL, com a frase "Aponte a câmera do celular para o código.";
- um botão **"Mostrar para projetar"** que abre um `Dialog` (o componente do projeto) com `<QrCode ... className="qr qr--projetar" />` e a URL por extenso embaixo, para quem não conseguir ler o código;
- o QR vive no mesmo estado em memória que a URL (`linkGerado`) — **nada em `localStorage`, `sessionStorage` ou rota**, pela mesma razão da URL.

- [x] **Step 6: Rodar e ver passar**

`cd frontend && npx vitest run && npm run lint && npm run build && npm audit --audit-level=high`

- [x] **Step 7: Mutações**

1. No `QrCode`, troque `x={x} y={y}` por `x={y} y={x}` → o teste de decodificação falha. Restaure. (Há leitores que aceitam QR espelhado; se o `jsqr` decodificar mesmo assim, diga isso e use como mutação desenhar só os módulos das linhas pares — essa tem de derrubar o teste.)
2. Em `Acompanhamentos.tsx`, passe `valor={linkGerado.url.split("/responder/")[0]}` → o teste da tela falha. Restaure.

- [x] **Step 8: Commit**

`feat(web): o QR code do link na tela do professor, pronto para projetar`

---

## Task 6: o script que abre e fecha a coleta

**Files:**
- Create: `fias-ed-web/deploy/subir-coleta.sh`
- Create: `fias-ed-web/deploy/testes/filtro-de-rede.sh`

**Interfaces:**
- Consumes: serviço `web-lan` e variáveis `FIAS_ED_LAN_IP`/`FIAS_ED_LAN_PORT` (Task 1); `FIAS_ED_PUBLIC_URL` (Task 2); a palavra `funcionando` na página `/` da 8081 (Task 1).
- Produces: `deploy/subir-coleta.sh [--ip <endereço> | --encerrar]`; funções `eh_privado`, `enderecos`, `candidatos`, carregáveis sem executar nada com `SUBIR_COLETA_SO_FUNCOES=1`.

- [x] **Step 1: O teste do filtro, que falha**

`deploy/testes/filtro-de-rede.sh`:

```sh
#!/bin/sh
# Testa a escolha de rede do subir-coleta.sh com saídas no formato real do
# Get-NetIPAddress (Windows) e do `ip -4 -o addr` (Linux).
#   sh deploy/testes/filtro-de-rede.sh
set -eu
SUBIR_COLETA_SO_FUNCOES=1
. "$(dirname "$0")/../subir-coleta.sh"

falhas=0
confere() {  # nome, esperado, obtido
  if [ "$2" = "$3" ]; then
    echo "ok     $1"
  else
    echo "FALHA  $1"; echo "       esperado: [$2]"; echo "       obtido:   [$3]"
    falhas=$((falhas + 1))
  fi
}

confere "windows: só o Wi-Fi" "192.168.0.14 Wi-Fi" "$(candidatos <<'FIM'
172.29.160.1 vEthernet (WSL (Hyper-V firewall))
192.168.0.14 Wi-Fi
169.254.83.10 Conexão Local* 1
127.0.0.1 Loopback Pseudo-Interface 1
FIM
)"

confere "windows: hotspot do próprio computador" "192.168.137.1 Conexão Local* 10" "$(candidatos <<'FIM'
192.168.137.1 Conexão Local* 10
192.168.56.1 VirtualBox Host-Only Network
172.29.160.1 vEthernet (Default Switch)
FIM
)"

confere "linux: só o Wi-Fi" "10.42.0.7 wlp2s0" "$(candidatos <<'FIM'
172.17.0.1 docker0
172.18.0.1 br-3f2a9c1b
10.42.0.7 wlp2s0
FIM
)"

confere "duas redes reais: as duas aparecem, o script não escolhe" \
  "$(printf '192.168.0.14 Wi-Fi\n10.0.0.5 Ethernet')" "$(candidatos <<'FIM'
192.168.0.14 Wi-Fi
10.0.0.5 Ethernet
FIM
)"

confere "endereço público nunca é candidato" "" "$(echo '200.137.65.10 Ethernet' | candidatos)"

for ip in 10.0.0.1 172.16.0.1 172.31.255.255 192.168.1.1; do
  eh_privado "$ip" || { echo "FALHA  $ip deveria ser privado"; falhas=$((falhas + 1)); }
done
for ip in 172.15.0.1 172.32.0.1 8.8.8.8 169.254.1.1 127.0.0.1; do
  if eh_privado "$ip"; then echo "FALHA  $ip não é privado"; falhas=$((falhas + 1)); fi
done

if [ "$falhas" -eq 0 ]; then echo "todos os casos passaram"; else echo "$falhas falha(s)"; exit 1; fi
```

`sh deploy/testes/filtro-de-rede.sh` → falha (o script não existe).

- [x] **Step 2: O script**

`deploy/subir-coleta.sh`:

```sh
#!/bin/sh
# Abre ou fecha a coleta na rede da sala (docs/deploy-local.md).
#
#   deploy/subir-coleta.sh              descobre o IP deste computador e abre
#   deploy/subir-coleta.sh --ip X       abre no IP X (quando há mais de uma rede)
#   deploy/subir-coleta.sh --encerrar   fecha a porta dos celulares
#
# POSIX sh: roda no Git Bash (Windows), no bash/dash do Linux e no sh do BusyBox.
set -eu

# Git Bash: sem isto, caminhos de contêiner passados ao docker viram C:/Program Files/Git/...
export MSYS_NO_PATHCONV=1

PORTA="${FIAS_ED_LAN_PORT:-8081}"

eh_privado() {
  case "$1" in
    10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*) return 0 ;;
    *) return 1 ;;
  esac
}

# Uma linha "IP interface" por endereço IPv4 deste computador.
enderecos() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      powershell.exe -NoProfile -Command \
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { \$_.IPAddress + ' ' + \$_.InterfaceAlias }" \
        | tr -d '\r' ;;
    Linux)
      ip -4 -o addr show scope global | awk '{ split($4, a, "/"); print a[1], $2 }' ;;
    *)
      echo "Sistema não suportado: $(uname -s)" >&2
      return 2 ;;
  esac
}

# Lê "IP interface" e devolve só o que pode ser a rede da sala: endereço privado, fora
# dos adaptadores virtuais do Docker, do WSL, do Hyper-V e de máquinas virtuais.
candidatos() {
  while read -r ip interface; do
    case "$interface" in
      vEthernet*|*WSL*|*Loopback*|*VirtualBox*|*VMware*|docker*|br-*|veth*|virbr*|vboxnet*|vmnet*) continue ;;
    esac
    if eh_privado "$ip"; then echo "$ip $interface"; fi
  done
}

abrir() {
  ip_escolhido="$1"
  if [ -z "$ip_escolhido" ]; then
    lista=$(enderecos | candidatos)
    n=$(printf '%s\n' "$lista" | grep -c . || true)
    if [ "$n" -eq 0 ]; then
      echo "Nenhuma rede local encontrada. Conecte este computador ao Wi-Fi ou ao hotspot da sala e rode de novo." >&2
      exit 1
    fi
    if [ "$n" -gt 1 ]; then
      echo "Este computador está em mais de uma rede:" >&2
      printf '%s\n' "$lista" | sed 's/^/  /' >&2
      echo "Rode de novo escolhendo a da sala: deploy/subir-coleta.sh --ip <endereço>" >&2
      exit 1
    fi
    ip_escolhido=${lista%% *}
  fi
  if ! eh_privado "$ip_escolhido"; then
    echo "Recusado: $ip_escolhido não é endereço de rede privada. A porta dos celulares só abre em rede local." >&2
    exit 2
  fi

  url="http://$ip_escolhido:$PORTA"
  FIAS_ED_LAN_IP="$ip_escolhido" FIAS_ED_LAN_PORT="$PORTA" FIAS_ED_PUBLIC_URL="$url" \
    docker compose --profile coleta up -d --no-build

  # Confere de verdade, em vez de confiar no "Started" do compose.
  tentativas=0
  until curl -fsS --max-time 3 "$url/" 2>/dev/null | grep -q "funcionando"; do
    tentativas=$((tentativas + 1))
    if [ "$tentativas" -ge 30 ]; then
      echo "A porta não respondeu em $url. Veja \"Diagnóstico\" em docs/deploy-local.md." >&2
      exit 1
    fi
    sleep 1
  done

  cat <<FIM
Coleta aberta.
  Tela do professor (só neste computador): http://localhost:8080
  Endereço para os celulares:              $url

Antes da turma: no seu celular, conectado à mesma rede, abra $url
e confira a mensagem "Conexão com o FIAS-ED funcionando".
Depois gere o link em "Meus acompanhamentos" e projete o QR code.

Ao terminar: deploy/subir-coleta.sh --encerrar
FIM
}

encerrar() {
  docker compose --profile coleta rm --stop --force web-lan
  # Recria a API sem FIAS_ED_PUBLIC_URL: os links voltam a apontar para este computador.
  docker compose up -d --no-build api
  echo "Coleta encerrada: a porta dos celulares está fechada."
}

if [ "${SUBIR_COLETA_SO_FUNCOES:-}" != 1 ]; then
  cd "$(dirname "$0")/.."
  case "${1:-}" in
    --encerrar) encerrar ;;
    --ip)
      if [ -z "${2:-}" ]; then echo "Uso: deploy/subir-coleta.sh --ip <endereço>" >&2; exit 2; fi
      abrir "$2" ;;
    "") abrir "" ;;
    *) echo "Uso: deploy/subir-coleta.sh [--ip <endereço> | --encerrar]" >&2; exit 2 ;;
  esac
fi
```

Marque os dois como executáveis no Git (`git update-index --chmod=+x`), porque o Windows não guarda o bit.

- [x] **Step 3: O teste do filtro passa**

`sh deploy/testes/filtro-de-rede.sh` → `todos os casos passaram`. Rode também com `busybox sh`, se houver, ou dentro de um contêiner alpine: `docker run --rm -v "$(pwd -W):/w" -w /w alpine sh deploy/testes/filtro-de-rede.sh` (com `MSYS_NO_PATHCONV=1`).

- [x] **Step 4: Rodar de verdade nesta máquina**

```sh
deploy/subir-coleta.sh                       # sem --ip: cole a saída, seja qual for
deploy/subir-coleta.sh --ip <o IP privado do Wi-Fi desta máquina>
curl -s http://<IP>:8081/ | grep -c funcionando                     # 1
docker compose exec -T api python -c "from app.core.config import get_settings as g; print(g().public_url)"   # http://<IP>:8081
deploy/subir-coleta.sh --encerrar
curl -s --max-time 3 -o /dev/null -w "%{http_code}\n" http://<IP>:8081/   # 000: fechado
docker compose exec -T api python -c "from app.core.config import get_settings as g; print(g().public_url)"   # http://localhost:8080
```

**Isto abre a 8081 na rede em que a máquina estiver agora, pelo tempo do teste** — só as rotas do estudante, e o `--encerrar` fecha. O Windows pode mostrar um aviso de firewall pedindo permissão para o Docker na rede; se aparecer, registre e **não** mexa no firewall por conta própria.

- [x] **Step 5: Mutação**

Tire `vEthernet*|` do `case` de `candidatos` → o caso "windows: só o Wi-Fi" falha. Restaure.

- [x] **Step 6: Commit**

`feat(deploy): um comando abre a coleta no IP da sala e outro a fecha`

---

## Task 7: o runbook, e a limitação no documento da banca

**Files:**
- Create: `docs/deploy-local.md`
- Modify: `docs/ESTADO_DE_VALIDACAO.md` (a subseção de limitações da coleta nativa, §2.1, criada na W3b)
- Modify: `fias-ed-web/README.md` (§4 "Uso diário": uma linha apontando para o runbook)

**Interfaces:**
- Consumes: os comandos das Tasks 6 e 8 (`deploy/subir-coleta.sh [--ip X | --encerrar]`, `deploy/empacotar.sh <destino>`, `deploy/instalar.sh`), a página de alcance `http://<IP>:8081/`.
- Produces: `docs/deploy-local.md`, que a Task 8 copia para dentro do pacote.

Escrito para o pesquisador no dia da coleta, com a turma chegando — frases curtas, um comando por passo, o que se espera ver depois de cada um. Não é documento técnico.

- [x] **Step 1: Escrever `docs/deploy-local.md` com estas seções, nesta ordem**

1. **Para que serve** — duas frases: o sistema roda neste computador; os celulares respondem pela rede da sala; nada vai para a internet.
2. **Antes do dia (com internet, na sua máquina)** — `deploy/empacotar.sh <pasta fora do repositório>`; o que sai (≈3 GB); levar a pasta inteira num pendrive **exFAT ou NTFS** (FAT32 recusa arquivo acima de 4 GB).
3. **Instalar na máquina da coleta (uma vez, sem internet)** — pré-requisitos: Docker instalado e aberto; no Windows, Git Bash (leve o instalador offline se a máquina não tiver); x86-64. Rodar `deploy/instalar.sh` de dentro da pasta do pacote. Criar a primeira conta: `docker compose run --rm api python -m app.cli create-admin --username <nome> --display-name "<Nome>"`. **Se o Git Bash disser "the input device is not a TTY", rode esse comando no PowerShell** — o terminal do Git Bash não repassa o teclado para a senha.
4. **No dia da coleta** — em ordem:
   1. **Conferir data e hora do computador.** Máquina sem internet costuma ter relógio errado, e a data da coleta decide com qual aula ela é comparada.
   2. Conectar o computador à rede da sala (Wi-Fi ou hotspot).
   3. `deploy/subir-coleta.sh` (ou `--ip <endereço>` se ele listar mais de uma rede).
   4. **Teste com o seu celular**, na mesma rede: abrir o endereço impresso e ver "Conexão com o FIAS-ED funcionando".
   5. Só então gerar o link em "Meus acompanhamentos" — **o link leva o endereço da rede do momento em que é gerado**.
   6. "Mostrar para projetar" e deixar o QR na tela.
   7. Acompanhar a contagem de respostas.
5. **Encerrar** — `deploy/subir-coleta.sh --encerrar`. Onde os dados ficam (neste computador) e como levá-los: backup do banco pelo `fias-ed-web/README.md` §7, com uma diferença numa máquina sem internet: **a imagem `alpine` que o README usa para os áudios não existe lá** — use a da API: `docker run --rm -v fias-ed-web_audio_store:/dados:ro -v "$(pwd -W)":/backup --entrypoint tar fias-ed-web-api:local czf /backup/audios.tgz -C /dados .` (com `MSYS_NO_PATHCONV=1` no Git Bash).
6. **Diagnóstico** — cada item: o que se vê, a causa provável, o que fazer.
   - **O celular não abre o endereço de teste.**
     - Dados móveis ligados: o celular (Android principalmente) pode mandar o tráfego pelos dados móveis quando o Wi-Fi não tem internet. Desligar os dados móveis, ou aceitar "usar esta rede mesmo sem internet".
     - Isolamento de clientes do Wi-Fi institucional: redes de instituição costumam impedir que um aparelho enxergue outro. Sintoma: o computador tem IP, o celular está na mesma rede, e nada abre. Alternativa: o **hotspot de um celular Android** ou um roteador portátil — o hotspot do próprio Windows costuma exigir uma conexão para compartilhar e não liga sem internet.
     - Firewall do Windows: a rede precisa estar como **Privada** (Configurações → Rede e Internet → propriedades da rede). Se ainda assim bloquear, uma regra de entrada para a porta 8081 (precisa de administrador): `New-NetFirewallRule -DisplayName "FIAS-ED coleta" -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow -Profile Private`.
   - **O link projetado parou de funcionar** — o IP do computador mudou (reconectou, trocou de rede) ou outro link foi gerado para a mesma data. Rodar `deploy/subir-coleta.sh` de novo e gerar outro link; o antigo é desativado sozinho.
   - **"Este link não está mais disponível"** — o link expirou, foi revogado ou foi substituído. Gerar outro.
   - **Depois de reiniciar o computador, a porta dos celulares não volta** — é de propósito. Rodar `deploy/subir-coleta.sh` de novo.
   - **O script diz que a porta não respondeu** — `docker compose --profile coleta ps` e `docker compose --profile coleta logs web-lan`; porta 8081 ocupada por outro programa → `FIAS_ED_LAN_PORT=8082 deploy/subir-coleta.sh`.
   - **O navegador do celular avisa que a conexão não é segura** — é o HTTP (ver Limitações). O Chrome está passando a avisar antes de abrir sites em HTTP; pelo anunciado, endereços de rede privada ficam fora do aviso por padrão. Se aparecer, tocar em continuar.
7. **Limitações** — as quatro, com as palavras da spec §4: tráfego em claro na rede local (quem estiver na mesma rede, com as ferramentas certas, vê o token e as respostas; as respostas não têm identidade, mas o aparelho é visível na rede); a marca de "já respondi" é burlável em aba anônima; o limite vem do número que o professor informa; o link é um segredo compartilhado pela turma.

Todo comando no runbook é **exatamente** o que as Tasks 6 e 8 definem; se uma delas mudar um nome ou uma opção, este arquivo muda junto.

- [x] **Step 2: `ESTADO_DE_VALIDACAO.md`**

Na subseção das limitações da coleta nativa (a que a W3b criou, com "aba anônima"), acrescente um parágrafo sobre o tráfego em claro na rede local, com as mesmas palavras do runbook, e a razão: não há gravação de áudio no navegador (verificado), então a spec aceita HTTP na rede local, declarado. **O `.docx` não é regerado nesta fatia** — é a próxima, decidida pelo pesquisador.

- [x] **Step 3: README**

Em `fias-ed-web/README.md` §4, uma linha: coleta em sala sem internet → `docs/deploy-local.md`.

- [x] **Step 4: Conferir os comandos**

Cada comando do runbook que não dependa de celular, rode-o nesta máquina e confira que ele existe e aceita as opções escritas (`deploy/subir-coleta.sh --encerrar`, a linha do backup de áudio com `--entrypoint tar`, o `create-admin` com `--help`). Cole as saídas.

- [x] **Step 5: Commit**

`docs(deploy): o runbook do dia da coleta, e o HTTP em claro declarado à banca`

---

## Task 8: o pacote para a máquina sem internet, provado num Docker sem nada

**Files:**
- Create: `fias-ed-web/deploy/empacotar.sh`
- Create: `fias-ed-web/deploy/instalar.sh`

**Interfaces:**
- Consumes: imagens `fias-ed-web-api:local`, `fias-ed-web-web:local`, `fias-ed-web-db:local` (Task 1); volume `fias-ed-web_models`; `docs/deploy-local.md` (Task 7); `deploy/subir-coleta.sh` (Task 6).
- Produces: `deploy/empacotar.sh <destino fora do repositório>` → pasta com `SHA256SUMS`, `docker-compose.yml`, `.env.example`, `deploy/subir-coleta.sh`, `deploy/instalar.sh`, `docs/deploy-local.md`, `imagens/{api,web,db}.tar.gz`, `modelos.tar`. `deploy/instalar.sh`, rodado de dentro dessa pasta.

- [x] **Step 1: `empacotar.sh`**

```sh
#!/bin/sh
# Monta o pacote para instalar o FIAS-ED num computador sem internet
# (docs/deploy-local.md, "Antes do dia"). Roda aqui, com internet e com o sistema
# instalado — os modelos saem do volume deste computador.
#
#   deploy/empacotar.sh <pasta de destino, fora do repositório>
set -eu
export MSYS_NO_PATHCONV=1

pasta_docker() {  # pasta do host no formato que o docker aceita em -v
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) (cd "$1" && pwd -W) ;;
    *) (cd "$1" && pwd) ;;
  esac
}

destino="${1:-}"
if [ -z "$destino" ]; then echo "Uso: deploy/empacotar.sh <pasta de destino, fora do repositório>" >&2; exit 2; fi
cd "$(dirname "$0")/.."                                   # fias-ed-web/
raiz=$(cd "$(git rev-parse --show-toplevel)" && pwd)      # mesmo formato do `pwd` abaixo
mkdir -p "$destino"
destino=$(cd "$destino" && pwd)
case "$destino/" in
  "$raiz"/*) echo "Recusado: $destino fica dentro do repositório. O pacote tem gigabytes e não pode virar commit por engano." >&2; exit 2 ;;
esac
if [ -n "$(ls -A "$destino")" ]; then echo "Recusado: $destino não está vazia." >&2; exit 2; fi

echo "1/5 construindo as imagens"
docker compose build api web db

echo "2/5 salvando as imagens"
mkdir -p "$destino/imagens"
for nome in api web db; do
  docker save "fias-ed-web-$nome:local" | gzip > "$destino/imagens/$nome.tar.gz"
done

echo "3/5 copiando os modelos (sem compressão: pesos não comprimem)"
docker run --rm --user "$(id -u):$(id -g)" \
  -v fias-ed-web_models:/models:ro -v "$(pasta_docker "$destino"):/saida" \
  --entrypoint tar fias-ed-web-api:local cf /saida/modelos.tar -C /models .

echo "4/5 compose, scripts e runbook"
mkdir -p "$destino/deploy" "$destino/docs"
cp docker-compose.yml .env.example "$destino/"
cp deploy/subir-coleta.sh deploy/instalar.sh "$destino/deploy/"
cp "$raiz/docs/deploy-local.md" "$destino/docs/"

echo "5/5 somas de conferência"
(cd "$destino" && find . -type f ! -name SHA256SUMS -exec sha256sum {} \; | sort -k 2 > SHA256SUMS)

du -sh "$destino"
echo "Pacote pronto em $destino. Leve a pasta inteira; na outra máquina, de dentro dela: deploy/instalar.sh"
```

- [x] **Step 2: `instalar.sh`**

```sh
#!/bin/sh
# Instala o FIAS-ED num computador sem internet, a partir do pacote de
# deploy/empacotar.sh (docs/deploy-local.md, "Instalar"). De dentro da pasta do pacote:
#   deploy/instalar.sh
set -eu
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

pasta_docker() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) (cd "$1" && pwd -W) ;;
    *) (cd "$1" && pwd) ;;
  esac
}

echo "1/5 conferindo o pacote"
sha256sum -c SHA256SUMS

echo "2/5 carregando as imagens"
for arquivo in imagens/*.tar.gz; do gunzip -c "$arquivo" | docker load; done

echo "3/5 configuração"
if [ -f .env ]; then
  echo "  .env já existe: mantido."
else
  aleatorio() { od -An -N24 -tx1 /dev/urandom | tr -d ' \n'; }
  {
    echo "POSTGRES_PASSWORD=$(aleatorio)"
    echo "FIAS_ED_MIGRATOR_PASSWORD=$(aleatorio)"
    echo "FIAS_ED_APP_PASSWORD=$(aleatorio)"
    # Sem o token do Hugging Face (o produto em execução não usa) e sem o diretório dos
    # experimentos: o caminho do .env.example aponta para fora do pacote, e o compose
    # criaria pastas lá ao montar.
    grep -Ev '^(POSTGRES_PASSWORD|FIAS_ED_MIGRATOR_PASSWORD|FIAS_ED_APP_PASSWORD|HUGGINGFACE_TOKEN|FIAS_ED_EXPERIMENTS_DIR)=' .env.example
  } > .env
  chmod 600 .env 2>/dev/null || true
  echo "  .env criado com senhas novas (não são mostradas)."
fi

echo "4/5 modelos"
if docker volume inspect fias-ed-web_models >/dev/null 2>&1; then
  echo "  volume de modelos já existe: mantido."
else
  # Pelo próprio serviço setup-models: é o que monta o volume com escrita, e o compose
  # cria o volume com as etiquetas dele (criado à mão, o compose reclamaria depois).
  docker compose run --rm --no-deps -v "$(pasta_docker .):/pacote:ro" \
    --entrypoint tar setup-models xf /pacote/modelos.tar -C /models
fi

echo "5/5 subindo"
docker compose up -d --no-build
echo "Pronto. Crie a primeira conta (no PowerShell, se o Git Bash reclamar de TTY):"
echo "  docker compose run --rm api python -m app.cli create-admin --username <nome> --display-name \"<Nome>\""
```

Executáveis no Git (`git update-index --chmod=+x`).

- [x] **Step 3: Nenhum segredo nas imagens nem no pacote**

```sh
for img in api web db; do
  echo "== $img"; docker run --rm --entrypoint sh "fias-ed-web-$img:local" -c \
    'find / -xdev \( -name ".env" -o -name ".hftoken" -o -path "*huggingface*token*" \) 2>/dev/null'
done
```

Esperado: nada. Depois de gerar o pacote (Step 4), varra-o pelas senhas do `.env` de desenvolvimento numa passada só — os valores ficam em variáveis, **contados, nunca impressos**:

```sh
v1=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
v2=$(grep '^FIAS_ED_MIGRATOR_PASSWORD=' .env | cut -d= -f2-)
v3=$(grep '^FIAS_ED_APP_PASSWORD=' .env | cut -d= -f2-)
[ -n "$v1" ] && [ -n "$v2" ] && [ -n "$v3" ] || echo "alguma senha vazia no .env: diga qual chave, não o valor"
( cat "$PACOTE"/*.yml "$PACOTE"/.env.example "$PACOTE"/deploy/* "$PACOTE"/docs/*
  for f in "$PACOTE"/imagens/*.tar.gz; do gunzip -c "$f"; done
  cat "$PACOTE"/modelos.tar ) | grep -a -c -F -e "$v1" -e "$v2" -e "$v3" || true
```

Esperado: `0`. Se der mais que zero, descubra qual das três e onde — sem imprimir o valor. O token do Hugging Face **não** entra nesta varredura: ele vive só em `<scratchpad>/.hftoken`, e esta tarefa não o lê. O que o protege é o Step 3 acima (nenhum arquivo de token nas imagens) e o volume de modelos já ter sido conferido sem credencial na preparação da fatia.

- [x] **Step 4: Gerar o pacote, fora do repositório**

```sh
PACOTE="<scratchpad>/pacote-fias-ed"
deploy/empacotar.sh "$PACOTE"
ls -la "$PACOTE" "$PACOTE/imagens"
deploy/empacotar.sh "$(git rev-parse --show-toplevel)/pacote-teste" ; echo "saída: $?"   # tem de recusar, 2
```

- [x] **Step 5: A prova — instalar num Docker sem imagens e sem rede**

```sh
docker pull docker:dind            # com internet, antes
docker run -d --privileged --network none --name fias-dind docker:dind
docker exec fias-dind sh -c 'i=0; until docker info >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 90 ] && exit 1; sleep 1; done'
docker exec fias-dind sh -c 'docker image ls -q | wc -l'          # 0: nenhuma imagem
docker exec fias-dind sh -c 'docker compose version'              # o plugin compose existe?
docker cp "$(cd "$PACOTE" && pwd -W)" fias-dind:/pacote   # Git Bash: o docker.exe precisa do caminho C:/...
docker exec fias-dind sh -c 'cd /pacote && sh deploy/instalar.sh'
docker exec fias-dind sh -c 'wget -qO- http://127.0.0.1:8080/api/health'
docker exec fias-dind sh -c 'cd /pacote && docker compose ps'
docker rm -f -v fias-dind
```

`--network none` é o que faz disto a prova: o daemon de dentro não alcança registro nenhum. Se a imagem `docker:dind` não trouxer o plugin `compose`, **pare e diga** — não o instale de dentro (não há rede) nem troque a prova por uma mais fraca sem registrar.

A imagem da API tem 3,7 GB: a cópia e o `load` levam minutos, e o conjunto ocupa ≈10 GB temporários no disco do Docker. O `docker rm -f -v` no fim devolve o espaço — confira com `docker system df` antes e depois.

- [x] **Step 6: Commit**

`feat(deploy): o pacote para a máquina sem internet, provado num Docker sem rede`

---

## Task 9: verificação final

**Files:** só o que a verificação apontar como defeito.

Esta tarefa não constrói nada. O produto é um relatório em que cada afirmação vem com o comando que a sustenta, e uma seção do que ficou por verificar e por quê.

- [x] **Step 1: A pilha no HEAD**

A W3b terminou com a pilha em execução atrás do HEAD. Antes de qualquer coisa:

```sh
docker compose build && docker compose run --rm migrate && docker compose up -d --no-build
docker compose exec -T db psql -U postgres -d fias_ed_web -tAc "select version_num from alembic_version"   # 0012
```

- [x] **Step 2: As suítes e as auditorias**

Motor, backend (imagem de teste reconstruída **e** `db-test` recriado), frontend (vitest, lint, build), `sh deploy/testes/filtro-de-rede.sh`, `bandit -r app --severity-level high`, `pip-audit --skip-editable`, `npm audit --audit-level=high`. Os 8 CVEs de `transformers 4.57.6` são conhecidos e **não** se atualiza nada — relate o que aparecer, com versão e identificador.

- [x] **Step 3: O runbook de ponta a ponta nesta máquina**

Siga `docs/deploy-local.md` na ordem, exceto os passos de celular:

1. relógio conferido (cole `date`);
2. `deploy/subir-coleta.sh` com o IP real do Wi-Fi;
3. uma conta de verificação criada pelo `create-admin` (no PowerShell se o Git Bash reclamar de TTY) — anote o nome, **nunca a senha**, e **desative a conta no fim**;
4. um acompanhamento novo, criado pela API como o professor — diga qual;
5. o link gerado por `POST /api/ciclos/{id}/qti/link` em `http://localhost:8080` → a `url` devolvida começa com `http://<IP>:8081/responder/`;
6. **o fluxo do estudante pelo IP da rede, com `curl` e um cookie jar** — `GET /publico/qti/{token}`, `POST .../consentir`, `POST .../responder` com 24 respostas → 201;
7. **a prova do cookie, antes e depois**: suba a API como se houvesse TLS —
   `FIAS_ED_LAN_IP=<IP> FIAS_ED_PUBLIC_URL=https://exemplo.invalido docker compose --profile coleta up -d --no-build` —, gere outro link (a `url` sai com `https://exemplo.invalido`; use só o token dela), e repita o fluxo pelo IP em HTTP com um cookie jar novo → o `curl` descarta o cookie, que agora é `Secure` (ele aplica a regra dos navegadores: não aceita cookie `Secure` vindo de `http://` fora de localhost), e o envio dá **409**. Volte a URL certa com `deploy/subir-coleta.sh --ip <IP>`, gere outro link → **201**. Se o `curl` desta máquina aceitar o cookie `Secure` em HTTP, **diga isso** — a prova vira só a do teste automatizado da Task 2, e o celular do pesquisador passa a ser a única prova de ponta a ponta;
8. `deploy/subir-coleta.sh --encerrar` → a 8081 fecha; um link gerado depois aponta para `http://localhost:8080`.

- [x] **Step 4: Nenhum token nem IP em log**

Com os tokens reais usados no Step 3:

```sh
docker compose --profile coleta logs --no-log-prefix web web-lan api worker | grep -c -F "<cada token usado>"
docker compose --profile coleta logs --no-log-prefix web-lan | wc -l
```

E com a API derrubada de propósito (`docker compose stop api`, uma chamada a `/publico/qti/<token>` pelas duas portas, `docker compose start api`). Esperado: zero ocorrências.

- [x] **Step 5: Exposição**

Com a coleta aberta: pelo IP da rede, `8081` responde; `8080`, `8000` e `5432` recusam (`curl --max-time 3` ou `Test-NetConnection <IP> -Port <porta>` no PowerShell). `docker compose --profile coleta ps --format '{{.Service}} {{.Ports}}'`: só `web` em `127.0.0.1:8080` e `web-lan` em `<IP>:8081`.

- [x] **Step 6: Os critérios de aceite da spec §7**

Um por um, com a evidência. O critério 2 (segundo dispositivo, celular físico) **não é verificável daqui**: diga isso e o motivo — daqui não se entra na rede como um aparelho de fora, e o firewall do Windows nem é atravessado por uma conexão da própria máquina ao próprio IP. O 6 cita o Step 5 da Task 8.

- [x] **Step 7: O que fica para o pesquisador**

Uma seção com: o teste com o celular físico (que é também o segundo dispositivo); o aviso de HTTP no navegador do celular, se houver; o aviso de firewall do Windows, se aparecer; o `create-admin` numa máquina Windows sem Git Bash; regenerar o `.docx`.

- [x] **Step 8: Arrumar o que a verificação deixou**

Desative a conta de verificação; feche a coleta (`deploy/subir-coleta.sh --encerrar`); apague o pacote de teste do scratchpad (≈3 GB) e cole o `docker system df` final. Nada de `down`, nada de apagar dado do banco de dev: o acompanhamento de verificação fica, e o relatório diz qual é.

- [x] **Step 9: Commit**

Só se houver conserto. Uma verificação que não acha nada é resultado, desde que se veja o que foi verificado.
