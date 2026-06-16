#!/usr/bin/env bash
# Build script for Render deployment
set -o errexit

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
cd web
python manage.py collectstatic --noinput

echo "=== Running database migrations ==="
python manage.py migrate --noinput

echo "=== Build complete ==="
