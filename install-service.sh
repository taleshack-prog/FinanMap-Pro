#!/bin/bash
# ════════════════════════════════════════════════════════════
#  FinanMap Pro v4 — Instalar como serviço systemd (Linux)
#  Roda 24/7, inicia automaticamente com o PC
#
#  Uso:          bash install-service.sh
#  Desinstalar:  bash install-service.sh --uninstall
#  Ver logs:     journalctl -u finanmap -f
# ════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
LOG_DIR="$SCRIPT_DIR/logs"
SERVICE_NAME="finanmap"
SERVICE_FILE="$HOME/.config/systemd/user/${SERVICE_NAME}.service"
UVICORN="$BACKEND_DIR/.venv/bin/uvicorn"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'
AMBER='\033[0;33m'; BOLD='\033[1m'; NC='\033[0m'

mkdir -p "$LOG_DIR" "$HOME/.config/systemd/user"

# ── Desinstalar ─────────────────────────────────────────
if [ "$1" == "--uninstall" ]; then
    echo -e "${CYAN}  Removendo serviço FinanMap...${NC}"
    systemctl --user stop $SERVICE_NAME 2>/dev/null
    systemctl --user disable $SERVICE_NAME 2>/dev/null
    rm -f "$SERVICE_FILE"
    systemctl --user daemon-reload
    pkill -f "uvicorn app.main" 2>/dev/null
    echo -e "${GREEN}  ✓  Serviço removido${NC}"
    exit 0
fi

echo ""
echo -e "${CYAN}${BOLD}  FinanMap Pro — Instalar serviço systemd 24/7${NC}"
echo -e "${CYAN}  ──────────────────────────────────────────────${NC}"
echo ""

# ── Verificar venv ──────────────────────────────────────
if [ ! -f "$UVICORN" ]; then
    echo -e "  ${RED}✗  .venv não encontrado!${NC}"
    echo -e "  ${CYAN}   Rode primeiro: bash start.sh${NC}"
    exit 1
fi

# ── Criar arquivo .service ──────────────────────────────
cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=FinanMap Pro v4 Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=${BACKEND_DIR}
ExecStart=${UVICORN} app.main:app --host 0.0.0.0 --port 8000 --log-level info
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/backend.log
StandardError=append:${LOG_DIR}/backend.log
Environment="PATH=${BACKEND_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=default.target
SERVICE

echo -e "  ${GREEN}✓  Service file criado:${NC} $SERVICE_FILE"

# ── Ativar serviço ──────────────────────────────────────
systemctl --user daemon-reload
systemctl --user enable $SERVICE_NAME
systemctl --user restart $SERVICE_NAME

sleep 3

# ── Verificar ───────────────────────────────────────────
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo -e "  ${GREEN}✓  Serviço ativo!${NC}"
else
    echo -e "  ${RED}✗  Falha ao iniciar. Veja:${NC}"
    journalctl --user -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi

if curl -s "http://localhost:8000/" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓  API respondendo em http://localhost:8000${NC}"
fi

# ── Habilitar linger (roda sem login) ───────────────────
loginctl enable-linger "$USER" 2>/dev/null && \
    echo -e "  ${GREEN}✓  Linger ativo — roda mesmo sem login${NC}" || \
    echo -e "  ${AMBER}  Linger não disponível (requer sudo). Roda apenas com sessão ativa.${NC}"

echo ""
echo -e "  ${CYAN}${BOLD}FinanMap Pro agora inicia automaticamente com o Linux!${NC}"
echo ""
echo -e "  ${CYAN}Comandos úteis:${NC}"
echo -e "  systemctl --user status $SERVICE_NAME    # ver status"
echo -e "  systemctl --user stop $SERVICE_NAME      # parar"
echo -e "  systemctl --user restart $SERVICE_NAME   # reiniciar"
echo -e "  journalctl --user -u $SERVICE_NAME -f    # logs ao vivo"
echo -e "  tail -f $LOG_DIR/backend.log             # logs arquivo"
echo -e "  bash install-service.sh --uninstall      # remover"
echo ""
