#!/bin/bash
# FinanMap Pro v4 — Status (Linux)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.backend.pid"
LOG_DIR="$SCRIPT_DIR/logs"
PORT=8000

GREEN='\033[0;32m'; RED='\033[0;31m'; AMBER='\033[0;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

echo ""
echo -e "${CYAN}${BOLD}  FinanMap Pro v4 — Status${NC}"
echo -e "${CYAN}  ──────────────────────────────────${NC}"
echo ""

# Backend process
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        # Tempo rodando
        START=$(stat -c %Y "$PID_FILE" 2>/dev/null || echo 0)
        NOW=$(date +%s)
        UPTIME_SEC=$((NOW - START))
        UPTIME_H=$((UPTIME_SEC/3600))
        UPTIME_M=$(((UPTIME_SEC%3600)/60))
        echo -e "  ${GREEN}●  Backend rodando${NC}  PID $PID  (uptime: ${UPTIME_H}h${UPTIME_M}m)"
    else
        echo -e "  ${RED}●  Backend parado${NC}"
        rm -f "$PID_FILE"
    fi
else
    echo -e "  ${RED}●  Backend parado${NC}"
fi

# API health
if curl -s --max-time 3 "http://localhost:$PORT/" > /dev/null 2>&1; then
    VER=$(curl -s "http://localhost:$PORT/" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('version','ok'))" 2>/dev/null || echo "ok")
    echo -e "  ${GREEN}●  API respondendo${NC}  http://localhost:$PORT  (v$VER)"
else
    echo -e "  ${RED}●  API não responde${NC}  http://localhost:$PORT"
fi

# Binance
BINANCE=$(curl -s --max-time 3 "http://localhost:$PORT/api/v1/hodl/binance/ping" 2>/dev/null)
if echo "$BINANCE" | grep -q '"conectado":true\|"online":true'; then
    echo -e "  ${GREEN}●  Binance conectada${NC}"
elif echo "$BINANCE" | grep -q '"api_configurada":false'; then
    echo -e "  ${AMBER}●  Binance: configure API keys no .env${NC}"
else
    echo -e "  ${RED}●  Binance offline / backend parado${NC}"
fi

# Monitor robôs
ROBOS=$(curl -s --max-time 3 "http://localhost:$PORT/api/v1/robos/monitor/status" 2>/dev/null)
if echo "$ROBOS" | grep -q '"ativo":true\|"running":true'; then
    echo -e "  ${GREEN}●  Monitor de robôs ativo${NC}"
else
    echo -e "  ${AMBER}●  Monitor de robôs parado${NC}  (abra o app e clique Iniciar Monitor)"
fi

# Watchdog
if pgrep -f "watchdog.sh" > /dev/null 2>&1; then
    echo -e "  ${GREEN}●  Watchdog 24/7 ativo${NC}"
else
    echo -e "  ${AMBER}●  Watchdog parado${NC}  (rode: bash watchdog.sh &)"
fi

echo ""
echo -e "  ${CYAN}Logs:${NC}  tail -f $LOG_DIR/backend.log"
echo -e "  ${CYAN}Docs:${NC}  http://localhost:$PORT/docs"
echo ""
