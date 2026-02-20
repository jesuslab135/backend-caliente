set -e

echo " Actualizando Backend "
apt-get update && apt-get upgrade -y

echo " Instalando Python y dependencias de compilacion "
apt-get install -y --no-install-recommends \
    git nano curl ca-certificates \
    python3 python3-pip pip \
    build-essential libpq-dev postgresql-client \
    netcat-openbsd

echo " Instalando dependencias de sistema para Playwright/Chromium "
apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
    libcups2t64 libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxrandr2 libgbm1 libxcb1 libxkbcommon0 libpango-1.0-0 libcairo2 \
    libasound2t64 libatspi2.0-0t64 libglib2.0-0t64 fonts-liberation \
    xdg-utils wget

echo " Limpieza "
apt-get clean
rm -rf /var/lib/apt/lists/*