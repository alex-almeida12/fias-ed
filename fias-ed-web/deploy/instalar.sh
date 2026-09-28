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
