#!/bin/sh
# Testa volume_de_modelos_ok do empacotar.sh: recusa volume ausente ou vazio, sem
# criar o volume ausente no processo, e aceita o volume real de modelos.
#   sh deploy/testes/volume-de-modelos.sh
set -eu
export MSYS_NO_PATHCONV=1
EMPACOTAR_SO_FUNCOES=1
. "$(dirname "$0")/../empacotar.sh"

falhas=0
confere() {  # nome do caso, "ok"|"falha" esperado, comando a rodar
  # Nomes de variável prefixados com "_caso_": o comando testado (volume_de_modelos_ok)
  # não usa `local` (fora do POSIX) e reatribui `nome` de verdade nesta mesma shell —
  # colidir com esse nome aqui apagaria o do caso antes do echo abaixo.
  _caso_nome="$1"; _caso_esperado="$2"; shift 2
  if "$@" >/dev/null 2>&1; then _caso_obtido=ok; else _caso_obtido=falha; fi
  if [ "$_caso_obtido" = "$_caso_esperado" ]; then
    echo "ok     $_caso_nome"
  else
    echo "FALHA  $_caso_nome"; echo "       esperado: [$_caso_esperado]"; echo "       obtido:   [$_caso_obtido]"
    falhas=$((falhas + 1))
  fi
}

# Caso 1: volume que não existe (nome gerado com data/hora, para não colidir com nada).
inexistente="fias-ed-web-teste-volume-inexistente-$(date +%Y%m%d%H%M%S)"
confere "volume inexistente: a função falha" falha volume_de_modelos_ok "$inexistente"
if docker volume inspect "$inexistente" >/dev/null 2>&1; then
  echo "FALHA  volume inexistente: a checagem criou o volume (docker volume inspect deveria vir antes, sozinho)"
  falhas=$((falhas + 1))
  docker volume rm "$inexistente" >/dev/null 2>&1 || true
else
  echo "ok     volume inexistente: continua não existindo depois da checagem"
fi

# Caso 2: volume criado vazio pelo próprio teste.
vazio="fias-ed-web-teste-volume-vazio-$(date +%Y%m%d%H%M%S)"
docker volume create "$vazio" >/dev/null
confere "volume vazio: a função falha" falha volume_de_modelos_ok "$vazio"
docker volume rm "$vazio" >/dev/null 2>&1 || true

# Caso 3: o volume real de modelos.
confere "fias-ed-web_models: a função passa" ok volume_de_modelos_ok fias-ed-web_models

if [ "$falhas" -eq 0 ]; then echo "todos os casos passaram"; else echo "$falhas falha(s)"; exit 1; fi
