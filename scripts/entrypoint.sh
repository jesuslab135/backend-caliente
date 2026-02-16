#!/bin/bash
set -e

echo "Waiting for database..."
# Espera a que PostgreSQL acepte conexiones en el puerto configurado
until python3 -c "import socket; socket.create_connection(('${HOST:-db}', ${PORT:-5432}), timeout=1)" 2>/dev/null; do
  echo "Database not ready, waiting..."
  sleep 1
done
echo "Database is ready!"

# Ya estamos en /app/core (WORKDIR del Dockerfile)
echo "Applying migrations..."
python3 manage.py migrate --noinput

echo "Collecting static files..."
python3 manage.py collectstatic --noinput --clear 2>/dev/null || true

echo "Starting server..."
exec "$@"
