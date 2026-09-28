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
