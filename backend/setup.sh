#!/bin/bash
# FinanMap Pro — Setup automático para Ubuntu 24.04
# Uso: bash setup.sh

set -e  # para se qualquer comando falhar

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   FinanMap Pro — Setup Ubuntu 24.04              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Verificar Python ───────────────────────────────────────────────────────
echo -e "${BLUE}[1/6] Verificando Python...${NC}"
python3 --version || { echo -e "${RED}Python3 não encontrado${NC}"; exit 1; }

# ── 2. Instalar python3-venv se necessário ────────────────────────────────────
echo -e "${BLUE}[2/6] Instalando python3-venv e python3-full...${NC}"
sudo apt install -y python3-venv python3-full 2>/dev/null | grep -E "instalado|already" || true

# ── 3. Criar e ativar ambiente virtual ───────────────────────────────────────
echo -e "${BLUE}[3/6] Criando ambiente virtual .venv...${NC}"
cd "$(dirname "$0")"   # garante que estamos na pasta do script

python3 -m venv .venv
source .venv/bin/activate
echo -e "${GREEN}    ✅ venv ativado: $(which python3)${NC}"

# ── 4. Instalar dependências ──────────────────────────────────────────────────
echo -e "${BLUE}[4/6] Instalando dependências (pode demorar ~2 min)...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}    ✅ Dependências instaladas${NC}"

# ── 5. Configurar .env ────────────────────────────────────────────────────────
echo -e "${BLUE}[5/6] Configurando .env...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}    ⚠️  Arquivo .env criado — edite com suas chaves:${NC}"
    echo -e "${YELLOW}        nano .env${NC}"
    echo -e "${YELLOW}        (mínimo: ANTHROPIC_API_KEY para o módulo IA)${NC}"
else
    echo -e "${GREEN}    ✅ .env já existe${NC}"
fi

# ── 6. Validar lógica de negócio ──────────────────────────────────────────────
echo -e "${BLUE}[6/6] Rodando validação (37 testes)...${NC}"
python3 validate.py
echo ""

# ── Instruções finais ─────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   Setup concluído!                               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo -e "  Para iniciar a API:"
echo ""
echo -e "  ${GREEN}source .venv/bin/activate${NC}"
echo -e "  ${GREEN}uvicorn app.main:app --reload --port 8000${NC}"
echo ""
echo -e "  Swagger UI:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  ReDoc:       ${BLUE}http://localhost:8000/redoc${NC}"
echo ""
echo -e "  Para parar:  ${YELLOW}Ctrl+C${NC}"
echo ""
