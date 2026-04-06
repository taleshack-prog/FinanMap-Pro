# FinanMap Pro v4 — Guia Linux

## Estrutura final da pasta

```
~/Downloads/finanmap-v3/
├── backend/                    ← FastAPI (já existe)
│   ├── app/
│   ├── .env                    ← suas API keys
│   ├── .venv/                  ← criado automaticamente
│   └── requirements.txt
├── finanmap-pro-v4.html        ← frontend (copie aqui)
├── logs/                       ← criada automaticamente
│   ├── backend.log
│   └── watchdog.log
├── start.sh                    ← INICIAR TUDO
├── stop.sh                     ← parar
├── status.sh                   ← ver status
├── watchdog.sh                 ← modo 24/7 simples
├── install-service.sh          ← serviço systemd permanente
└── FinanMap Pro.desktop        ← ícone de duplo clique
```

---

## Configuração inicial (só uma vez)

```bash
# 1. Copiar os arquivos
cp start.sh stop.sh status.sh watchdog.sh install-service.sh \
   "FinanMap Pro.desktop" finanmap-pro-v4.html \
   ~/Downloads/finanmap-v3/

# 2. Dar permissão
cd ~/Downloads/finanmap-v3
chmod +x start.sh stop.sh status.sh watchdog.sh install-service.sh

# 3. (Opcional) Instalar ícone na área de trabalho
cp "FinanMap Pro.desktop" ~/Desktop/
chmod +x ~/Desktop/"FinanMap Pro.desktop"
```

---

## Como abrir

### Opção A — Terminal (mais simples)
```bash
cd ~/Downloads/finanmap-v3
bash start.sh
```

### Opção B — Duplo clique no Desktop
Copie o `FinanMap Pro.desktop` para o Desktop.
No GNOME: clique direito → Permitir execução → duplo clique.
No KDE: já funciona com duplo clique.

---

## Parar e ver status

```bash
bash stop.sh        # parar o backend
bash status.sh      # ver status completo
```

---

## Modo 24/7

### Opção 1 — Watchdog simples
```bash
cd ~/Downloads/finanmap-v3
bash watchdog.sh &

# Ver log
tail -f logs/watchdog.log
```
Verifica a cada 30s e reinicia se o backend cair.

### Opção 2 — Serviço systemd (recomendado)
Inicia automaticamente com o Linux, reinicia se cair:

```bash
bash install-service.sh
```

Ver logs em tempo real:
```bash
journalctl --user -u finanmap -f
# ou
tail -f ~/Downloads/finanmap-v3/logs/backend.log
```

Desinstalar:
```bash
bash install-service.sh --uninstall
```

---

## Solução de problemas

### Backend não inicia
```bash
cat logs/backend.log          # ver o erro completo
ss -tlnp | grep 8000          # verificar se porta está ocupada
fuser -k 8000/tcp             # liberar a porta 8000
```

### Dependências faltando
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### Binance não conecta
```bash
# Verificar .env
cat backend/.env | grep BINANCE

# Testar conexão
curl http://localhost:8000/api/v1/hodl/binance/ping
```

### Permissão negada no .desktop
```bash
chmod +x ~/Desktop/"FinanMap Pro.desktop"
# No GNOME: clique direito no ícone → "Permitir execução"
```

---

## URLs importantes

| URL | O que é |
|-----|---------|
| http://localhost:8000 | Health check da API |
| http://localhost:8000/docs | Swagger UI — testar endpoints |
| http://localhost:8000/api/v1/hodl/binance/saldo | Saldo Binance |
| http://localhost:8000/api/v1/robos/monitor/status | Status dos robôs |
| http://localhost:8000/api/v1/tecnico/robos/status | Status GA |
