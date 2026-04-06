#!/bin/bash
# FinanMap Pro v4 — Stop (Linux)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.backend.pid"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

echo ""
echo -e "${CYAN}  FinanMap Pro — Parando backend...${NC}"
echo ""

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" && rm -f "$PID_FILE"
        echo -e "  ${GREEN}✓  Backend parado (PID $PID)${NC}"
    else
        echo -e "  ${RED}  Processo $PID não encontrado${NC}"
        rm -f "$PID_FILE"
    fi
else
    pkill -f "uvicorn app.main" 2>/dev/null && \
        echo -e "  ${GREEN}✓  uvicorn encerrado${NC}" || \
        echo -e "  ${RED}  Nenhum processo encontrado${NC}"
fi
echo ""
