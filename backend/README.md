# FinanMap Pro — Backend API

Motor de investimentos antifragil: **Monte Carlo · Kelly Criterion · Algoritmo Genético · Claude IA**

---

## Stack Técnica

| Camada | Tecnologia | Detalhe |
|---|---|---|
| API | FastAPI + uvicorn ASGI | ~1k req/s, AWS Lambda ready |
| Dados | yfinance 0.2.43 | B3 + Cripto + ETFs, 5k calls/dia free |
| IA | Claude (Anthropic) | Few-shot, análise de portfólio |
| DB | Supabase (Postgres) | Queries <50ms, Realtime |
| Cache | Redis / in-memory | TTL 5min, evita rate limit yfinance |
| Deploy | Render.com | US$7/mês inicial, escala automática |
| CI/CD | GitHub Actions | pytest 80%+ cobertura, deploy automático |

---

## Estrutura do Projeto

```
backend/
├── app/
│   ├── main.py                  # Entry point FastAPI
│   ├── core/
│   │   └── config.py            # Configurações via .env
│   ├── models/
│   │   └── schemas.py           # Pydantic schemas (request/response)
│   ├── routers/
│   │   ├── fire.py              # /api/v1/fire
│   │   ├── portfolio.py         # /api/v1/portfolio
│   │   ├── ai_advisor.py        # /api/v1/ia
│   │   ├── market.py            # /api/v1/market
│   │   └── onboarding.py        # /api/v1/onboarding
│   └── services/
│       ├── fire_service.py      # Monte Carlo + Kelly Criterion
│       ├── market_service.py    # yfinance + cache
│       ├── ga_service.py        # Algoritmo Genético (DEAP-inspired)
│       └── ia_service.py        # Claude API + stress test
└── tests/
    └── test_services.py         # pytest — 35 testes
```

---

## Endpoints

### 🔥 FIRE Tracker
```
POST /api/v1/fire/calculate
```
Motor principal — 10.000 simulações Monte Carlo com preços reais yfinance.

**Body:**
```json
{
  "aporte_mensal": 5000,
  "despesas_mensais": 2000,
  "patrimonio_atual": 50000,
  "portfolio": {
    "bova": { "ticker": "BOVA11.SA", "quantidade": 220, "preco_medio": 115, "classe": "renda_var" },
    "btc":  { "ticker": "BTC-USD",   "quantidade": 0.31, "preco_medio": 280000, "classe": "cripto" }
  },
  "risco": 0.6,
  "taxa_retirada": 0.04
}
```

**Response:**
```json
{
  "monte_carlo": {
    "simulacoes": 10000,
    "anos_p50": 8.3,
    "anos_p90": 12.1,
    "prob_sucesso_pct": 87.2,
    "patrimonio_meta": 600000,
    "renda_passiva_mensal": 2000,
    "progresso_pct": 41.0
  },
  "anos_para_fire": 8.3,
  "sharpe_ratio": 1.82,
  "sortino_ratio": 2.14,
  "projecao_cenarios": {
    "otimista":   [50000, 75000, ...],
    "base":       [50000, 64000, ...],
    "estressado": [50000, 54000, ...]
  }
}
```

---

### 📊 Portfólio
```
POST /api/v1/portfolio/analyze    # Análise completa com cotações ao vivo
GET  /api/v1/portfolio/quote/{ticker}   # Cotação de um ativo (ex: BOVA11, BTC)
```

---

### 🧬 IA Advisor
```
POST /api/v1/ia/analyze     # Análise Claude API + Kelly + stress test
POST /api/v1/ia/optimize    # Algoritmo Genético — alocação ótima
```

**Exemplo GA:**
```json
{
  "patrimonio": 247000,
  "aporte": 5000,
  "perfil": "moderado_agressivo",
  "incluir_cripto": true,
  "geracoes": 50,
  "populacao": 200
}
```

---

### 📈 Market Data
```
GET /api/v1/market/snapshot    # IBOV, Selic, IPCA, USD/BRL, BTC — cache 5min
```

---

### 🎯 Onboarding
```
POST /api/v1/onboarding/profile   # Score VIX-adjusted + Kelly + FIRE
```

---

## Setup Local

### 1. Pré-requisitos
```bash
python 3.11+
git clone https://github.com/seu-usuario/finanmap-pro
cd finanmap-pro/backend
```

### 2. Ambiente virtual
```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente
```bash
cp .env.example .env
# Editar .env com suas chaves:
# - ANTHROPIC_API_KEY (https://console.anthropic.com)
# - SUPABASE_URL + SUPABASE_ANON_KEY (https://supabase.com)
# - ALPHA_VANTAGE_KEY (opcional — dividendos BR)
```

### 4. Rodar a API
```bash
uvicorn app.main:app --reload --port 8000
```
Acesse: http://localhost:8000/docs (Swagger UI automático)

### 5. Docker Compose (recomendado)
```bash
cd ..  # raiz do projeto
docker compose up --build
```
Sobe: API (8000) + Postgres (5432) + Redis (6379)

---

## Testes

```bash
# Todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ -v --cov=app --cov-report=term-missing

# Teste específico
pytest tests/test_services.py::TestMonteCarlo -v
```

**Cobertura esperada:** 80%+ (alvo do documento: 95% com dados reais)

---

## Deploy — Render.com (US$7/mês)

1. Conectar repositório GitHub no [Render.com](https://render.com)
2. Criar **Web Service** → apontar para `/backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Adicionar variáveis de ambiente no painel
6. Adicionar `RENDER_DEPLOY_HOOK` nos secrets do GitHub → CI/CD automático

---

## Próximo Passo: React Native

O frontend React Native consumirá estes endpoints via:
```
BASE_URL=https://api.finanmap.pro
```

Todos os endpoints suportam CORS configurado para `http://localhost:8081` (Expo).

---

## Notas de Segurança

- Zero custody: apenas APIs read-only (yfinance, Alpha Vantage)
- Nenhuma credencial de corretora armazenada
- JWT via Supabase Auth para autenticação de usuários
- Rate limiting recomendado via Nginx/Cloudflare em produção
