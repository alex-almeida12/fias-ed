# FIAS-ED Web — implantação local para a coleta em sala

**Data:** 2026-09-26
**Origem:** comissão do pesquisador (2026-09-26) e plano aprovado por ele na mesma data.
**Fatia anterior:** W3b (coleta nativa), encerrada em `6f01c42`.

## 1. Ambiente decidido pelo pesquisador

A aplicação roda num único computador — o pessoal do pesquisador ou um da instituição
—, numa rede **sem internet**. Os celulares dos estudantes chegam a ela pela rede
local (Wi-Fi ou hotspot). Não há domínio nem possibilidade de certificado público.

## 2. A verificação que decidiu o desenho

A regra do pesquisador: se alguma página acessada pelo estudante grava áudio no
navegador, contexto seguro é obrigatório e a fatia inclui TLS autoassinado; se não,
HTTP na rede local é aceitável e entra declarado como limitação.

**Resultado:** nenhuma ocorrência de `getUserMedia`, `MediaRecorder`, `mediaDevices`
ou `AudioContext` em todo `fias-ed-web/frontend/src`. Nenhuma página grava áudio —
nem a do estudante, nem as do professor. **O desenho é HTTP na rede local.**

**O que a regra não cobria, e esta spec cobre:** o cookie de consentimento é
`Secure`, e os navegadores atuais descartam cookie `Secure` vindo de `http://` fora
de localhost. Em `http://192.168.x.x` o estudante aceitaria o convite e receberia
409 em todo envio. O `Secure` desse cookie passa a seguir o esquema da URL pública
(§3.3).

## 3. Desenho

### 3.1 Dois servidores, uma porta na rede

A mesma imagem `web` passa a ter dois `server` no nginx:

- **8080 — o sistema inteiro, para o professor.** Publicado só em `127.0.0.1`, pelo
  serviço `web`, como hoje. Não sai da máquina.
- **8081 — só o que o estudante usa.** Publicado pelo serviço novo `web-lan`, no IP
  da rede da sala. Serve `/responder/`, `/assets/`, `/publico/` e, em `/`, uma
  página curta "Conexão com o FIAS-ED funcionando", usada como teste de alcance.
  Todo o resto — `/api/` incluído — devolve 404: login e dados do professor ficam
  fora do alcance dos celulares.

`web-lan` fica num profile `coleta`, com `restart: "no"`: só existe enquanto alguém
abriu a coleta de propósito. Sem o script, a porta 8081 não existe; depois de
reiniciar o computador, não volta sozinha. Se o IP da sala sumir, só `web-lan`
falha — a tela do professor em 8080 continua de pé.

Banco e API continuam **sem porta publicada**. O banco está na rede `fias_net`
(`internal: true`).

### 3.2 A URL do link vem de configuração

`gerar_link` monta a URL a partir de `PUBLIC_URL` (variável `FIAS_ED_PUBLIC_URL` no
host; padrão `http://localhost:8080`), não mais de `request.base_url`. O professor
está em `localhost:8080` e o estudante em `IP:8081`: o cabeçalho da requisição daria
o endereço errado. Isso também fecha o achado da W3b de que a URL perdia a porta.

### 3.3 O cookie de consentimento

`secure` passa a ser `PUBLIC_URL.startswith("https://")`. Uma fonte de verdade: se
um dia houver TLS, liga sozinho. A sessão do professor continua `Secure` — ele usa
a própria máquina, e `localhost` é contexto seguro para os navegadores.

### 3.4 Nenhum token nem IP em log

Vazamentos achados na preparação desta fatia, além do `/publico/` que a W3b fechou:

- **`GET /responder/<token>`** — a página que o estudante abre — é registrada pelo
  log de acesso do nginx, com token e IP (comprovado em 2026-09-26).
- **`error_log`** do nginx registra `client: <IP>, request: "GET
  /publico/qti/<token>"` quando a API não responde.

No servidor 8081: sem `access_log`, `error_log` só em nível `crit`, e o nginx deixa
de repassar o IP do estudante à API (`X-Forwarded-For` vazio). No 8080: `access_log
off` e `error_log crit` em `/responder/` e `/publico/`. A regra do comentário do
`nginx.conf` permanece: quem quiser log nessas rotas tem de mascarar token e IP
antes.

### 3.5 Um link vivo por coleta, e a trava na coleta

A contagem de respostas é por coleta, mas a trava (`FOR UPDATE`) era na linha do
link e o teto é por link. Com dois links vivos na mesma coleta, dois envios
simultâneos por links diferentes travam linhas diferentes, leem a mesma contagem e
gravam os dois — estouram o limite e repetem o `response_index`. Decisão do
pesquisador: **corrigir**.

- **O banco garante um link vivo por coleta:** índice único parcial em `link_qti
  (coleta_id) WHERE revogado_em IS NULL AND deleted_at IS NULL`. Com um só link vivo,
  todo envio vivo disputa a mesma linha, e a trava do link passa a valer, na prática,
  como trava da coleta. A migração revoga (não apaga) os links excedentes que já
  existam, deixando o mais recente de cada coleta — no banco de dev, em 2026-09-26,
  eram 2 coletas com 2 links vivos cada, restos da verificação da W3b.
- `criar_link` trava a coleta, revoga os links não revogados dela e cria o novo, na
  mesma transação — dois cliques simultâneos se enfileiram em vez de esbarrar no
  índice. O diálogo avisa: gerar outro link para a mesma data desativa o anterior.
- `responder` revalida o link **com a trava na mão**: ele pode ter sido substituído
  entre a validação e a trava.

*Mudança feita ao escrever o plano, sobre o que foi aprovado em conversa ("a trava
passa para a linha da coleta"):* mover a trava do envio para a coleta não tinha teste
determinístico razoável. O envio já esbarra na linha da coleta de qualquer jeito — a
chave estrangeira do INSERT e a atualização da contagem a travam —, então, sob
disputa, as duas versões esperam; só em momentos diferentes, que só se distinguem
olhando as travas internas do Postgres. A garantia pelo banco tem teste
determinístico, e o resultado para quem usa é o mesmo.

### 3.6 Uma coleta viva por (acompanhamento, data)

`UNIQUE (ciclo_id, coletado_em) WHERE deleted_at IS NULL` — **parcial**: uma UNIQUE
simples quebraria a reimportação, que apaga logicamente a coleta antiga e cria
outra na mesma data. Os três testes da W3a que montam duas coletas vivas na mesma
data para testar o desempate descrevem um estado que passa a ser impossível; viram
testes de que o banco recusa. As duas funções que criam coleta tratam a violação
vinda de uma requisição concorrente, em vez de devolver 500.

### 3.7 QR code na tela do professor

O QR projetado em sala precisa conter o token, e o token só existe na tela do
professor, no instante em que o link é gerado. O diálogo de gerar link mostra o QR
— grande, para projetar —, em `--color-navy` sobre `--color-white` (o projeto não
tem tema escuro). Biblioteca sem dependências de execução, empacotada no build. O
QR vive só em memória, como a URL.

### 3.8 Script de subida — `deploy/subir-coleta.sh`

Descobre o IP da rede da sala (ignora adaptadores virtuais; só aceita endereço
privado; com mais de um candidato, lista e exige `--ip`), sobe `web-lan` e a API
com a URL pública certa, confere de verdade que a porta responde e imprime o
endereço. `--encerrar` remove `web-lan` e devolve a URL padrão.

### 3.9 Empacotamento offline

`deploy/empacotar.sh` (máquina com internet) gera, **fora do repositório**: as três
imagens (`docker save`, um arquivo cada), o volume de modelos (1,18 GB, sem
credencial nenhuma — conferido), o compose, os scripts, o runbook e `SHA256SUMS`.
Nunca o `.env`. `deploy/instalar.sh` (máquina sem internet) confere as somas,
carrega as imagens, restaura os modelos pelo próprio serviço `setup-models`, gera
um `.env` novo com senhas aleatórias e sobe com `--no-build`.

Scripts em **POSIX sh**: rodam no Git Bash, no bash do Linux e no `sh` do BusyBox —
este último é o do Docker limpo em que o pacote é provado.

### 3.10 Runbook — `docs/deploy-local.md`

Antes do dia, no dia, encerrar, diagnóstico e limitações. Inclui o que vai aparecer
em sala: relógio do computador (define a data da coleta), dados móveis do celular
desviando o tráfego, hotspot do Windows que exige conexão para compartilhar, IP que
muda depois de o link ser gerado, isolamento de clientes do Wi-Fi institucional,
firewall e perfil de rede.

## 4. Limitações declaradas

Entram no runbook e no `docs/ESTADO_DE_VALIDACAO.md`:

1. **Tráfego em claro na rede local.** Quem estiver na mesma rede, com as
   ferramentas certas, vê o token e as respostas passando. As respostas não têm
   identidade, mas o aparelho de origem é visível na rede.
2. As três da W3b continuam valendo: a marca de "já respondi" é burlável em aba
   anônima; o limite vem do número que o professor informa; o link é um segredo
   compartilhado pela turma.

## 5. Pré-requisitos, fora desta fatia

Docker instalado no destino (instalá-lo sem internet exige levar o instalador e ter
virtualização e WSL2 habilitados); máquina x86-64; pendrive em exFAT ou NTFS (FAT32
recusa arquivo acima de 4 GB); Git Bash, se o destino for Windows — o instalador
offline dele entra na lista do que transportar.

## 6. Fora do escopo

Percurso visual em celular (do pesquisador, manual); anotações DER e WER (do
pesquisador); regeneração do `.docx` (depois desta fatia); atualização do
`transformers`; TLS.

## 7. Critérios de aceite

1. Todas as suítes atuais verdes.
2. De um segundo dispositivo na mesma rede, a URL impressa abre a aplicação e o
   fluxo do estudante completa — **verificação manual do pesquisador**, com o
   celular físico.
3. O runbook executado de ponta a ponta pelo agente, exceto o passo do celular.
4. Nenhum token nem IP em log nenhum, inclusive com a API fora do ar.
5. Banco e API inalcançáveis pelo IP da rede; a 8080 inalcançável pelo IP da rede.
6. O pacote sobe num Docker sem imagens e sem rede.

## 8. Restrições que permanecem

`access_log off` nas rotas do estudante e a regra do comentário do `nginx.conf`;
nenhum token ou IP em log; não simular navegador; nada em `fias-ed-shared/`; o
token do Hugging Face só em `<scratchpad>/.hftoken`, nunca em arquivo versionado ou
transportado.
