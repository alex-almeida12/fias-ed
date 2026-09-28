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

confere "esta máquina, 2026-09-26" \
  "$(printf '10.3.2.66 Ethernet\n192.168.3.197 Wi-Fi')" "$(candidatos <<'FIM'
172.25.80.1 vEthernet (WSL (Hyper-V firewall))
169.254.119.12 Conexão de Rede Bluetooth
192.168.80.1 vEthernet (Default Switch)
169.254.148.143 Conexão Local* 1
169.254.128.39 Conexão Local* 9
10.3.2.66 Ethernet
192.168.3.197 Wi-Fi
127.0.0.1 Loopback Pseudo-Interface 1
FIM
)"

for ip in 10.0.0.1 172.16.0.1 172.31.255.255 192.168.1.1; do
  eh_privado "$ip" || { echo "FALHA  $ip deveria ser privado"; falhas=$((falhas + 1)); }
done
for ip in 172.15.0.1 172.32.0.1 8.8.8.8 169.254.1.1 127.0.0.1; do
  if eh_privado "$ip"; then echo "FALHA  $ip não é privado"; falhas=$((falhas + 1)); fi
done

if [ "$falhas" -eq 0 ]; then echo "todos os casos passaram"; else echo "$falhas falha(s)"; exit 1; fi
