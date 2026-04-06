#!/bin/bash
# ════════════════════════════════════════════════════════════
#  FinanMap Pro v4 — Launcher Linux
#  Um clique: abre backend + frontend no browser
# ════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND="$SCRIPT_DIR/finanmap-pro-v4.html"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$SCRIPT_DIR/.backend.pid"
PORT=8000

GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

clear
echo ""
echo -e "${CYAN}${BOLD}  FinanMap Pro v4 — Launcher${NC}"
echo -e "${CYAN}  ────────────────────────────────────${NC}"
echo ""

mkdir -p "$LOG_DIR"

# ── Verificar se já está rodando ────────────────────────
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo -e "  ${AMBER}⚠  Backend já está rodando (PID $OLD_PID)${NC}"
        echo -e "  ${GREEN}✓  Abrindo o frontend...${NC}"
        sleep 1
        xdg-open "$FRONTEND" 2>/dev/null &
        exit 0
    fi
fi

# ── Verificar Python ────────────────────────────────────
echo -e "  ${CYAN}[1/4]${NC} Verificando Python..."
if command -v python3 &>/dev/null; then
    PY="python3"
else
    echo -e "  ${RED}✗  Python3 não encontrado!${NC}"
    echo -e "       sudo apt install python3 python3-venv python3-pip"
    exit 1
fi
echo -e "       $($PY --version)"

# ── Verificar/criar venv ────────────────────────────────
echo -e "  ${CYAN}[2/4]${NC} Verificando ambiente virtual..."
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo -e "       Criando .venv pela primeira vez..."
    $PY -m venv "$BACKEND_DIR/.venv"
    source "$BACKEND_DIR/.venv/bin/activate"
    echo -e "       Instalando dependências (aguarde ~2 min na primeira vez)..."
    pip install -q --upgrade pip
    pip install -q -r "$BACKEND_DIR/requirements.txt"
    echo -e "       ${GREEN}✓  Dependências instaladas${NC}"
else
    source "$BACKEND_DIR/.venv/bin/activate"
    echo -e "       ${GREEN}✓  .venv encontrado${NC}"
fi

# ── Verificar porta livre ───────────────────────────────
echo -e "  ${CYAN}[3/4]${NC} Verificando porta $PORT..."
if ss -tlnp | grep -q ":$PORT "; then
    echo -e "       ${AMBER}Porta $PORT ocupada — liberando...${NC}"
    fuser -k ${PORT}/tcp 2>/dev/null || true
    sleep 1
fi
echo -e "       ${GREEN}✓  Porta $PORT livre${NC}"

# ── Iniciar backend ─────────────────────────────────────
echo -e "  ${CYAN}[4/4]${NC} Iniciando backend FastAPI..."
cd "$BACKEND_DIR"
nohup "$BACKEND_DIR/.venv/bin/uvicorn" app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --reload \
    --log-level info \
    > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_FILE"
echo -e "       ${GREEN}✓  Backend iniciado (PID $BACKEND_PID)${NC}"

# ── Aguardar backend ficar pronto ───────────────────────
echo ""
MAX_WAIT=30
WAITED=0
printf "  ${AMBER}  Aguardando backend...${NC}"
while ! curl -s "http://localhost:$PORT/" > /dev/null 2>&1; do
    sleep 1
    WAITED=$((WAITED+1))
    printf "\r  ${AMBER}  Aguardando backend... ${WAITED}s${NC}"
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo ""
        echo -e "  ${RED}✗  Backend não respondeu em ${MAX_WAIT}s${NC}"
        echo -e "  ${AMBER}   Veja: tail -f $LOG_DIR/backend.log${NC}"
        break
    fi
done
echo ""

# ── Abrir browser ────────────────────────────────────────
echo -e "  ${GREEN}✓  Tudo pronto! Abrindo FinanMap Pro...${NC}"
echo ""
echo -e "  ${BOLD}  Backend:  http://localhost:$PORT${NC}"
echo -e "  ${BOLD}  Docs API: http://localhost:$PORT/docs${NC}"
echo -e "  ${BOLD}  Logs:     $LOG_DIR/backend.log${NC}"
echo ""
echo -e "  ${CYAN}  Para parar: bash stop.sh${NC}"
echo ""

sleep 1
xdg-open "$FRONTEND" 2>/dev/null &

# ── Mostrar logs em tempo real ──────────────────────────
echo -e "  ${CYAN}════ Logs em tempo real (Ctrl+C fecha este terminal) ════${NC}"
echo ""
tail -f "$LOG_DIR/backend.log"
