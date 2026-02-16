# =========================================================
# Caliente Backend — Production Dockerfile
# Imagen ligera basada en Python 3.12 slim (~150MB vs ~800MB Ubuntu)
# =========================================================

FROM python:3.12-slim AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependencias del sistema para PostgreSQL y compilacion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python primero (cache de Docker)
COPY src/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar codigo fuente
COPY src/ /app/

# Script de arranque
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Directorio donde vive manage.py
WORKDIR /app/core

ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]
