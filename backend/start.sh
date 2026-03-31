#!/bin/bash
# FinanMap Pro — Iniciar API
# Uso: bash start.sh

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "⚠️  venv não encontrado. Rode primeiro: bash setup.sh"
    exit 1
fi

source .venv/bin/activate

echo ""
echo "🚀 Iniciando FinanMap Pro API..."
echo "   Swagger UI → http://localhost:8000/docs"
echo "   Parar      → Ctrl+C"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
