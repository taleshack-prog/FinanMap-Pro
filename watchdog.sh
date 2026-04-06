#!/bin/bash
# ════════════════════════════════════════════════════════════
#  FinanMap Pro v4 — Watchdog 24/7 (Linux)
#  Mantém o backend sempre vivo, reinicia se cair.
#
#  Rodar em background:  bash watchdog.sh &
#  Ver log:              tail -f logs/watchdog.log
#  Parar:                pkill -f watchdog.sh
# ════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$SCRIPT_DIR/.backend.pid"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"
PORT=8000
CHECK_INTERVAL=30
MAX_RESTARTS=10

mkdir -p "$LOG_DIR"
RESTARTS=0
RESTART_WINDOW_START=$(date +%s)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$WATCHDOG_LOG"
}

start_backend() {
    cd "$BACKEND_DIR"
    source "$BACKEND_DIR/.venv/bin/activate"
    fuser -k ${PORT}/tcp 2>/dev/null || true
    sleep 1
    nohup "$BACKEND_DIR/.venv/bin/uvicorn" app.main:app \
        --host 0.0.0.0 --port $PORT --log-level info \
        >> "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$PID_FILE"
    log "Backend iniciado (PID $(cat $PID_FILE))"
    sleep 3
}

is_healthy() {
    curl -s --max-time 5 "http://localhost:$PORT/" > /dev/null 2>&1
}

log "════════ Watchdog iniciado ════════"
log "Verificando a cada ${CHECK_INTERVAL}s · max $MAX_RESTARTS restarts/hora"

if ! is_healthy; then
    log "Backend offline — iniciando..."
    start_backend
fi

while true; do
    sleep $CHECK_INTERVAL

    # Reset contador por hora
    NOW=$(date +%s)
    if [ $((NOW - RESTART_WINDOW_START)) -gt 3600 ]; then
        RESTARTS=0
        RESTART_WINDOW_START=$NOW
    fi

    if ! is_healthy; then
        RESTARTS=$((RESTARTS+1))
        log "⚠  Backend não responde! Restart #$RESTARTS desta hora"

        if [ $RESTARTS -gt $MAX_RESTARTS ]; then
            log "✗  Muitos restarts ($RESTARTS/hora). Aguardando 5 min..."
            sleep 300
            RESTARTS=0
            RESTART_WINDOW_START=$(date +%s)
        fi

        start_backend
        sleep 5

        if is_healthy; then
            log "✓  Backend recuperado!"
        else
            log "✗  Backend ainda offline após restart"
        fi
    fi
done
