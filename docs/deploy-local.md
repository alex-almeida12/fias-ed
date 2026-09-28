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

Leve essa pasta inteira, sem descompactar nada, num pendrive **exFAT ou
NTFS**. Um pendrive **FAT32 recusa arquivo acima de 4 GB** — e as imagens ou
os modelos passam disso.

## 3. Instalar na máquina da coleta (uma vez, sem internet)

Pré-requisitos, já na máquina da sala:

- Docker instalado **e aberto**.
- No Windows, Git Bash instalado (leve o instalador offline no pendrive, se
  a máquina não tiver Git Bash).
- Processador x86-64.

De dentro da pasta do pacote (a que veio do pendrive):

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

## 4. No dia da coleta

Em ordem:

1. **Abrir o Docker Desktop, se ele não estiver aberto.** Depois de reiniciar
   o computador ele não abre sozinho, e nada dos passos seguintes funciona
   sem ele.
2. **Conferir a data e a hora do computador.** Uma máquina sem internet
   costuma atrasar o relógio, e é a data da coleta que decide com qual aula
   ela é comparada.
3. **Conectar o computador à rede da sala** (Wi-Fi ou hotspot).
4. Abrir a coleta:
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
5. **Teste com o seu celular**, na mesma rede: abra o endereço impresso
   (`http://<IP-da-sala>:8081`) e confira a frase "Conexão com o FIAS-ED
   funcionando."
6. Só então, na tela do professor, clique em **"Gerar link"** em "Meus
   acompanhamentos". **O link leva o endereço da rede no momento em que é
   gerado** — por isso ele vem depois do teste, nunca antes. Se já existir um
   link para a mesma data, um diálogo avisa que gerar outro desativa o
   anterior.
7. Clique em **"Mostrar para projetar"** e deixe o QR code na tela.
8. Acompanhe a contagem de respostas na mesma tela.

## 5. Encerrar

```bash
deploy/subir-coleta.sh --encerrar
```

**O que você vê:** `Coleta encerrada: a porta dos celulares está fechada.`

Os dados ficam neste computador, nos volumes do Docker. Para levá-los, siga o
backup de `fias-ed-web/README.md`, §7 (Backup e restauração) — com uma
diferença numa máquina sem internet: **a imagem `alpine` que o README usa
para os áudios não existe aqui.** Use a imagem da própria API:

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v fias-ed-web_audio_store:/dados:ro -v "$(pwd -W)":/backup --entrypoint tar fias-ed-web-api:local czf /backup/audios.tgz -C /dados .
```

O comando do banco é o mesmo do README §7; só o dos áudios troca de imagem.

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
- *Firewall do Windows:* a rede precisa estar como **Privada**
  (Configurações → Rede e Internet → propriedades da rede). Se ainda assim
  bloquear, crie uma regra de entrada para a porta 8081 (precisa de
  administrador):
  ```powershell
  New-NetFirewallRule -DisplayName "FIAS-ED coleta" -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow -Profile Private
  ```

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
