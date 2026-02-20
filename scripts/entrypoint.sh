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

# Auto-seed if database is empty (first deployment)
USER_COUNT=$(python3 manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.count())" 2>/dev/null || echo "0")
if [ "$USER_COUNT" = "0" ]; then
  echo "No users found — running seed_users..."
  python3 manage.py seed_users
else
  echo "Database already has $USER_COUNT user(s) — skipping seed."
fi

echo "Starting server..."
exec "$@"
