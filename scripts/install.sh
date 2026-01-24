set -e

echo " Actualizando Backend "
apt-get update && apt-get upgrade -y

echo " Instalando Python y dependencias de compilacion "
apt-get install -y --no-install-recommends \
    git nano curl ca-certificates \
    python3 pip \
    build-essential libpq-dev postgresql-client

echo " Limpieza "
apt-get clean
rm -rf /var/lib/apt/lists/*