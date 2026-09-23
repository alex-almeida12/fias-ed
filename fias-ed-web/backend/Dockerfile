# Contexto de build: raiz do monorepo (precisa de fias-ed-shared/).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    SHARED_DIR=/opt/fias-ed-shared AUDIO_STORE=/data/audio
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /data/audio /models && chown app:app /data/audio /models
# pip-audit (Task 11) aponta CVEs corrigidas no próprio pip da imagem base; sem dependência
# nenhuma em pyproject.toml, a correção é atualizar a ferramenta de instalação aqui.
RUN pip install --upgrade "pip>=26.2"
# torch/torchaudio do índice de wheels CPU do PyTorch. O wheel do PyPI traz CUDA
# inteiro (gigabytes) e aqui não há GPU nenhuma para usá-lo. Vem antes do
# `pip install -e .` de propósito: assim o resolvedor já encontra a versão
# satisfeita e não a troca pela do PyPI.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch<2.9" "torchaudio<2.9"
COPY fias-ed-shared /opt/fias-ed-shared
# Editável: o motor localiza rules/ e schemas/ relativo ao próprio código.
RUN pip install -e /opt/fias-ed-shared/engine-py
WORKDIR /app
COPY fias-ed-web/backend /app
# Roda uma vez, na instalação, e não no produto em execução (veja o README).
COPY fias-ed-web/scripts /app/scripts

FROM base AS dev
RUN pip install -e ".[dev]"
USER app

FROM base AS prod
RUN pip install -e .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
