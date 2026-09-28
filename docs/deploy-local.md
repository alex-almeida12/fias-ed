# Runbook: o dia da coleta em sala (sem internet)

Este guia é para o pesquisador, no dia da coleta, com a turma chegando. Frases
curtas, um comando por passo, e depois de cada passo o que você deve ver na
tela.

## 1. Para que serve

O FIAS-ED roda inteiro neste computador. Os celulares dos estudantes respondem
ao questionário pela rede local da sala — nada vai para a internet.

## 2. Antes do dia (com internet, na sua máquina)

Com este repositório e internet, monte o pacote que vai para a sala:

```bash
deploy/empacotar.sh <pasta fora do repositório>
```

**O que sai:** uma pasta de aproximadamente 2 GB, com as imagens Docker
(`imagens/`), os modelos (`modelos.tar`), a conferência de integridade
(`SHA256SUMS`), o arquivo do Compose, os dois scripts (`instalar.sh` e
`subir-coleta.sh`) e este runbook.

Leve essa pasta inteira, sem descompactar nada, num pendrive. O maior
arquivo do pacote (`modelos.tar`) fica perto de 1,2 GB — nenhum arquivo do
pacote chega nos 4 GB que um pendrive **FAT32** recusa —, mas **exFAT ou
NTFS** continua sendo a escolha mais segura, por precaução.

**Se a máquina da coleta não tiver Docker Desktop**, baixe o instalador
aqui, com internet, e leve-o também no pendrive. Instalá-lo sem internet
exige **virtualização e WSL2 habilitados** na máquina de destino.

**Se você souber que a máquina da coleta roda algum serviço de rede alheio
ao FIAS-ED** (por exemplo, um banco de dados instalado direto na máquina,
escutando na rede), planeje pará-lo no dia, antes de abrir a coleta, e
religá-lo ao terminar. Se houver, como administrador: `Stop-Service <nome
do serviço>` para parar, e `Start-Service <nome do serviço>` para religar
depois.

## 3. Instalar na máquina da coleta (uma vez, sem internet)

Pré-requisitos, já na máquina da sala:

- Docker instalado **e aberto**.
- No Windows, Git Bash instalado (leve o instalador offline no pendrive, se
  a máquina não tiver Git Bash).
- Processador x86-64.

**Copie a pasta do pacote do pendrive para o disco antes de instalar** —
por exemplo, para `Documentos\fias-ed`. Não rode nada direto do pendrive:
o `instalar.sh` grava o `.env`, com as senhas novas do banco, dentro da
própria pasta do pacote; rodando do pendrive, as senhas saem da máquina
junto com ele na próxima vez que você o tirar. É dessa pasta, já no disco,
que todos os comandos deste runbook rodam daqui em diante — inclusive os do
dia da coleta.

De dentro dela:

```bash
deploy/instalar.sh
```

Depois, crie a primeira conta:

```bash
docker compose run --rm api python -m app.cli create-admin --username <nome> --display-name "<Nome>"
```

A senha é pedida duas vezes, sem aparecer na tela. **Se o Git Bash disser
"the input device is not a TTY"**, rode esse mesmo comando no PowerShell — o
terminal do Git Bash não repassa o teclado para a senha.

**Libere a porta no firewall, uma vez, como administrador** (PowerShell):

```powershell
New-NetFirewallRule -DisplayName "FIAS-ED coleta" -Direction Inbound -Protocol TCP -LocalPort 8081 -RemoteAddress LocalSubnet -Action Allow -Profile Any
```

Três avisos sobre essa regra:
- Se um dia você precisar rodar com `FIAS_ED_LAN_PORT=8082` (ver
  "Diagnóstico"), ela não cobre a 8082 — crie outra igual, trocando o
  `-LocalPort`.
- Uma regra de **bloqueio** vence uma regra de permissão. Se a porta
  continuar fechada mesmo com esta regra, liste as regras de bloqueio de
  entrada: `Get-NetFirewallRule -Direction Inbound -Action Block`.
- Teste com o celular já na configuração de rede que vai valer no dia da
  coleta — o perfil de rede errado (ver "Diagnóstico", "Firewall do
  Windows") é a causa mais comum de a porta não abrir mesmo com a regra
  criada.

## 4. No dia da coleta

Em ordem:

1. **Abrir o Docker Desktop, se ele não estiver aberto.** Depois de reiniciar
   o computador ele não abre sozinho, e nada dos passos seguintes funciona
   sem ele.
2. **Ligar o computador na tomada e desativar a suspensão automática.**
   Configurações → Sistema → Energia: coloque tela e suspensão em
   **"Nunca"**, durante a coleta. Tela apagada esconde o QR code; suspensão
   pausa o Docker e derruba envios no meio da turma, e ao acordar o IP do
   computador pode ter mudado.
3. **Conferir a data e a hora do computador.** Uma máquina sem internet
   costuma atrasar o relógio, e é a data da coleta que decide com qual aula
   ela é comparada.
4. **Conectar o computador à rede da sala** (Wi-Fi ou hotspot).
5. Abrir a coleta:
   ```bash
   deploy/subir-coleta.sh
   ```
   **O que você vê**, na maioria das vezes:
   ```
   Coleta aberta.
     Tela do professor (só neste computador): http://localhost:8080
     Endereço para os celulares:              http://<IP-da-sala>:8081

   Antes da turma: no seu celular, conectado à mesma rede, abra http://<IP-da-sala>:8081
   e confira a mensagem "Conexão com o FIAS-ED funcionando".
   Depois gere o link em "Meus acompanhamentos" e projete o QR code.

   Ao terminar: deploy/subir-coleta.sh --encerrar
   ```
   **Se este computador estiver em mais de uma rede**, o script não escolhe
   por você e mostra algo como:
   ```
   Este computador está em mais de uma rede:
     <endereço> <nome da rede>
     <endereço> <nome da rede>
   Rode de novo escolhendo a da sala: deploy/subir-coleta.sh --ip <endereço>
   ```
   Rode de novo com `--ip <endereço>`, escolhendo o endereço da rede da sala.
6. **Teste com o seu celular**, na mesma rede: abra o endereço impresso
   (`http://<IP-da-sala>:8081`) e confira a frase "Conexão com o FIAS-ED
   funcionando."
7. Só então, na tela do professor, clique em **"Gerar link"** em "Meus
   acompanhamentos". **O link leva o endereço da rede no momento em que é
   gerado** — por isso ele vem depois do teste, nunca antes. Um diálogo
   sempre avisa que gerar outro link para a mesma data desativa o anterior.
   **Confira que o endereço escrito embaixo do QR code começa com o mesmo
   `http://<IP-da-sala>:8081` do passo 5.** Se for diferente, o script foi
   rodado de novo depois disso (ou ainda nem foi rodado) e o link não vai
   funcionar para a turma.
8. **Antes de projetar**, se o computador estiver em modo "Duplicar" com o
   projetor (o mais comum): **Win+P → Estender**, e arraste a janela do
   navegador para a tela do projetor. Assim só o que você escolher mostrar
   aparece lá — o passo 9 explica por quê. Clique em **"Mostrar para
   projetar"** e deixe o QR code na tela do projetor.
9. Para ver quantas respostas já chegaram, abra **"Ver o acompanhamento"**
   numa **nova aba** (botão direito → "Abrir link em nova aba"). **Não saia
   de "Meus acompanhamentos" nesta aba** enquanto a turma responde: ao sair,
   o QR code some e só volta gerando outro link — o que desativa o link que
   a turma está usando. Essa aba não atualiza sozinha: **aperte F5 nessa
   aba para atualizar a contagem**. **Não deixe essa aba na tela do
   projetor.** Com 10 respostas ou mais ela passa a mostrar o resultado
   parcial da percepção dos estudantes e a trajetória dos índices do
   professor — projetar isso para a turma contamina quem ainda vai
   responder e expõe dados do professor. É para isso que serve a tela
   estendida do passo 8: a aba de acompanhamento fica só no seu monitor, e
   você a olha sem que a turma veja.

## 5. Encerrar

```bash
deploy/subir-coleta.sh --encerrar
```

**O que você vê:** `Coleta encerrada: a porta dos celulares está fechada.`

Os dados ficam neste computador, nos volumes do Docker. Para levá-los, faça
o backup do banco e dos áudios — o `fias-ed-web/README.md` não vai no
pacote, então os comandos ficam aqui.

**Banco de dados** — Git Bash:
```bash
docker compose exec -T db pg_dump -U postgres -Fc fias_ed_web > backup-fias-ed-web.dump
```
PowerShell (o `>` do PowerShell 5.1 estraga arquivo binário; por isso o
`cmd /c`):
```powershell
cmd /c "docker compose exec -T db pg_dump -U postgres -Fc fias_ed_web > backup-fias-ed-web.dump"
```

**Áudios** — a imagem `alpine`, que o `fias-ed-web/README.md` usa para este
comando, **não existe nesta máquina sem internet.** Use a imagem da própria
API (Git Bash):
```bash
MSYS_NO_PATHCONV=1 docker run --rm -v fias-ed-web_audio_store:/dados:ro -v "$(pwd -W)":/backup --entrypoint tar fias-ed-web-api:local czf /backup/audios.tgz -C /dados .
```

O backup contém os áudios das aulas e dados pessoais (nomes de professores,
turmas, escolas). Guarde-o em local protegido.

## 6. Diagnóstico

**O celular não abre o endereço de teste.**

- *Dados móveis ligados:* o celular (Android principalmente) pode mandar o
  tráfego pelos dados móveis quando o Wi-Fi não tem internet. Desligue os
  dados móveis, ou aceite "usar esta rede mesmo sem internet".
- *Isolamento de clientes do Wi-Fi institucional:* redes de instituição
  costumam impedir que um aparelho enxergue outro. Sintoma: o computador tem
  IP, o celular está na mesma rede, e mesmo assim nada abre. Alternativa: o
  **hotspot de um celular Android** ou um roteador portátil — o hotspot do
  próprio Windows costuma exigir uma conexão para compartilhar, e não liga
  sem internet.
- *Firewall do Windows:* **mantenha a rede como Pública** — não marque como
  Privada. Uma sala cheia de aparelhos que você não controla é justamente o
  que o Windows entende por rede Pública (numa máquina de instituição, com
  domínio, o perfil é Domínio); o perfil Privada assume uma rede de
  confiança, baixa a proteção do computador nela, e pode até deixar a porta
  8081 mais fechada em vez de mais aberta, se alguma regra do sistema só
  valer no perfil Público. A regra que libera a 8081 é criada uma vez, na
  instalação (§3, "Instalar"). Se a porta continuar fechada mesmo com a
  rede Pública e essa regra criada, confira se uma regra de **bloqueio**
  está vencendo: `Get-NetFirewallRule -Direction Inbound -Action Block`.

**O link projetado parou de funcionar.** Causa provável: o IP do computador
mudou (reconectou, trocou de rede) ou outro link foi gerado para a mesma
data. O que fazer: rode `deploy/subir-coleta.sh` de novo e gere outro link; o
antigo é desativado sozinho.

**"Este link não está mais disponível".** Causa provável: o link expirou, foi
revogado ou foi substituído por outro. O que fazer: gere outro link.

**Depois de reiniciar o computador, a porta dos celulares não volta.** É de
propósito. O que fazer: rode `deploy/subir-coleta.sh` de novo.

**O script diz "A porta não respondeu em `http://<endereço>`."** O que
fazer:
```bash
docker compose --profile coleta ps
docker compose --profile coleta logs web-lan
```
Se a porta 8081 estiver ocupada por outro programa:
```bash
FIAS_ED_LAN_PORT=8082 deploy/subir-coleta.sh
```

**O navegador do celular avisa que a conexão não é segura.** Causa: é o HTTP
(veja "Limitações", abaixo). O Chrome está passando a avisar antes de abrir
sites em HTTP; pelo anunciado, endereços de rede privada ficam fora do aviso
por padrão. Se aparecer mesmo assim, toque em continuar.

**No diálogo "Mostrar para projetar", em telas de projetor baixas
(1280×720), é preciso rolar para chegar ao botão de fechar.** É de
propósito — o QR code em si aparece inteiro, sem precisar de rolagem.

## 7. Limitações

- **Tráfego em claro na rede local.** Quem estiver na mesma rede, com as
  ferramentas certas, vê o token e as respostas passando. As respostas não
  têm identidade, mas o aparelho de origem é visível na rede.
- A marca de "já respondi" é burlável em aba anônima.
- O limite de respostas vem do número que o professor informa, não de
  cadastro.
- O link é um segredo compartilhado pela turma.
