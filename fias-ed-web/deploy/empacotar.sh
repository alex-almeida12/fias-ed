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

# Sucesso só se o volume <nome> EXISTE e não está vazio. `docker volume inspect` vem
# primeiro e sozinho de propósito: ele nunca cria volume, e é o que garante que a
# checagem de "vazio" logo abaixo (um `docker run -v`, que cria um volume vazio na hora
# se ele ainda não existir) só roda depois de já sabermos que o volume é real — senão a
# própria checagem criaria o volume que deveria acusar como ausente. A checagem de vazio
# usa a imagem da API (fias-ed-web-api:local): ela já tem `/models` e um `sh`, e este
# script já a exige construída antes de chamar esta função. Achado da revisão final da
# fatia (ledger, entrada "REVISAO FINAL"): sem isto, um volume `fias-ed-web_models`
# inexistente vira, silenciosamente, um `modelos.tar` vazio no pacote — o defeito só
# aparece na máquina sem internet, quando ela for processar áudio.
volume_de_modelos_ok() {  # nome do volume
  nome="$1"
  docker volume inspect "$nome" >/dev/null 2>&1 || return 1
  docker run --rm -v "$nome:/models:ro" --entrypoint sh fias-ed-web-api:local \
    -c '[ -n "$(ls -A /models 2>/dev/null)" ]'
}

empacotar() {
  destino="${1:-}"
  if [ -z "$destino" ]; then echo "Uso: deploy/empacotar.sh <pasta de destino, fora do repositório>" >&2; exit 2; fi
  cd "$(dirname "$0")/.."                                   # fias-ed-web/
  raiz=$(cd "$(git rev-parse --show-toplevel)" && pwd)      # mesmo formato do `pwd` abaixo
  if [ -e "$destino" ]; then criada=nao; else criada=sim; fi
  mkdir -p "$destino"
  destino=$(cd "$destino" && pwd)
  case "$destino/" in
    "$raiz"/*)
      # A pasta só foi criada para normalizar o caminho; recusada, não fica para trás no repositório.
      if [ "$criada" = sim ]; then rmdir "$destino"; fi
      echo "Recusado: $destino fica dentro do repositório. O pacote tem gigabytes e não pode virar commit por engano." >&2; exit 2 ;;
  esac
  if [ -n "$(ls -A "$destino")" ]; then echo "Recusado: $destino não está vazia." >&2; exit 2; fi

  echo "1/5 construindo as imagens"
  docker compose build api web db

  if ! volume_de_modelos_ok fias-ed-web_models; then
    echo "Recusado: o volume de modelos não existe ou está vazio neste computador. Instale os modelos antes (fias-ed-web/README.md, seção dos modelos) e rode de novo." >&2
    exit 2
  fi

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
}

if [ "${EMPACOTAR_SO_FUNCOES:-}" != 1 ]; then
  empacotar "${1:-}"
fi
