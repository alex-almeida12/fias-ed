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
# O setuptools entra na mesma linha, e antes do torch de propósito. A imagem base não traz
# setuptools nenhum; quem o puxa é o requisito `setuptools; python_version >= "3.12"` do
# torch — e aquele pip roda com --index-url do PyTorch, cujo índice de wheels CPU só
# hospeda até a 78.1.0, com a CVE-2025-47273 (path traversal em `PackageIndex.download`,
# corrigida na 78.1.1). Instalado aqui, do PyPI, o requisito do torch já chega satisfeito
# e o índice do PyTorch não tem o que rebaixar. Mexer no `requires` do [build-system] não
# resolveria: aquilo vale para o ambiente isolado de construção, não para a imagem.
RUN pip install --upgrade "pip>=26.2" "setuptools>=78.1.1"
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
