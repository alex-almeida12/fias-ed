# Contexto de build: raiz do monorepo (precisa de fias-ed-shared/).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    SHARED_DIR=/opt/fias-ed-shared AUDIO_STORE=/data/audio
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /data/audio && chown app:app /data/audio
COPY fias-ed-shared /opt/fias-ed-shared
# Editável: o motor localiza rules/ e schemas/ relativo ao próprio código.
RUN pip install -e /opt/fias-ed-shared/engine-py
WORKDIR /app
COPY fias-ed-web/backend /app

FROM base AS dev
RUN pip install -e ".[dev]"
USER app

FROM base AS prod
RUN pip install -e .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
