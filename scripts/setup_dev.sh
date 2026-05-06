#!/usr/bin/env bash
# Lokales Dev-Setup für Widerspruch
set -euo pipefail

echo "==> Prüfe Python-Version..."
python3 --version

echo "==> venv anlegen..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Dependencies installieren..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> .env prüfen..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "    .env wurde aus .env.example kopiert. Bitte Secrets eintragen!"
fi

echo "==> Postgres-Container starten..."
docker compose up -d
echo "    Warte 5 Sekunden auf Postgres..."
sleep 5

echo "==> Schema laden..."
PGPASSWORD=dev psql -h localhost -p 5432 -U widerspruch -d widerspruch -f backend/db/schema.sql

echo ""
echo "✓ Setup fertig."
echo ""
echo "Nächste Schritte:"
echo "  1. .env mit deinen Tokens befüllen"
echo "  2. source .venv/bin/activate"
echo "  3. python -m backend.bot.main"
