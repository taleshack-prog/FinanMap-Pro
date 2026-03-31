# FinanMap Pro — React Native (Expo)

App móvel iOS/Android com IA darwiniana, Monte Carlo e Robôs Investidores.

---

## Estrutura do Projeto

```
finanmap-rn/
├── app/                          # Expo Router (file-based routing)
│   ├── _layout.tsx               # Root: fonts, QueryClient, GestureHandler
│   ├── index.tsx                 # Redireciona: onboarding ↔ app
│   ├── onboarding.tsx            # Quiz 6 perguntas (perfil VIX-adjusted)
│   └── (tabs)/
│       ├── _layout.tsx           # Bottom tab navigator
│       ├── dashboard.tsx         # Início — patrimônio, FIRE, CTA Robôs
│       ├── portfolio.tsx         # Ativos em carteira
│       ├── robots.tsx            # ★ Robôs & GA (diferencial principal)
│       ├── fire.tsx              # FIRE Tracker interativo
│       └── ia.tsx                # IA Advisor — Claude API + stress test
│
├── src/
│   ├── theme/index.ts            # Cores, tipografia, espaçamentos, sombras
│   ├── components/index.tsx      # MetricCard, Card, Button, ProgressBar...
│   ├── services/api.ts           # Axios → FastAPI backend
│   ├── store/index.ts            # Zustand + AsyncStorage (persiste perfil)
│   └── screens/
│       ├── OnboardingScreen.tsx  # Animado com Reanimated
│       ├── DashboardScreen.tsx   # Pull-to-refresh, live market data
│       └── RobotsScreen.tsx      # GA engine local + animações
│
├── package.json
├── app.json
├── babel.config.js
└── tsconfig.json
```

---

## Setup em 3 passos

### 1. Instalar dependências

```bash
cd finanmap-rn
npm install
```

### 2. Configurar ambiente

```bash
cp .env.example .env
# .env já vem com API_BASE_URL=http://localhost:8000/api/v1
# Para produção: substituir pela URL do Render.com
```

### 3. Iniciar

```bash
# Backend precisa estar rodando:
cd ../finanmap-pro/backend && bash start.sh

# Em outro terminal — app mobile:
cd finanmap-rn
npx expo start
```

Abrirá o Expo Go QR code. Escaneie com o **Expo Go** (iOS/Android).

---

## Telas

### Onboarding (6 perguntas)
- Objetivo financeiro (FIRE / crescimento / renda / reserva)
- Patrimônio + aporte + despesas
- Reação a quedas (mapeado em score VIX-adjusted 0–100)
- Experiência (ajusta complexidade das recomendações)
- Horizonte + cripto sim/não
- **Resultado**: score, perfil, alocação Kelly, FIRE p50/p90

### Dashboard
- Header com patrimônio total e gradiente roxo
- Métricas: rentabilidade, aporte, Sharpe
- FIRE Tracker com barra de progresso
- Alocação Kelly + dados de mercado ao vivo
- CTA dark para a tela de Robôs

### ★ Robôs & Algoritmo Genético
**Diferencial principal do app.**
- Grade 2×4 de robôs com DNA colorido, animações Reanimated
- Robôs élite ficam com glow pulsante verde
- Arena do GA: botões iniciar/pausar/+1 geração/reset
- Sliders de mutação e penalidade black swan
- Gráfico de barras mostrando evolução fitness (melhor vs. média)
- Laboratório de cruzamento: seleciona 2 robôs → crossover real
- Alert nativo quando nasce uma "nova strain" (+4% fitness)
- Leaderboard top 5 com medalhas
- Painel de inspeção com genoma completo de cada robô

### FIRE Tracker
- Resultado em destaque (anos para FIRE, probabilidade)
- Parâmetros ajustáveis em pills (sem slider — melhor UX mobile)
- Botão "Recalcular Monte Carlo" chama o backend real

### IA Advisor
- Card dark com métricas do GA (CAGR, Sortino, gerações)
- Botão "Analisar com Claude AI" → POST /api/v1/ia/analyze
- Stress test com 4 cenários (crash cripto, recessão, base, otimista)
- 3 alertas Kelly Criterion com valores em R$

---

## Build para produção

```bash
# Instalar EAS CLI
npm install -g eas-cli
eas login

# Build Android (APK para distribuição direta)
eas build --platform android --profile preview

# Build iOS (necessita conta Apple Developer)
eas build --platform ios --profile preview

# Submit para lojas
eas submit --platform android
eas submit --platform ios
```

---

## Variáveis de ambiente

| Variável       | Descrição                          | Default                          |
|----------------|------------------------------------|----------------------------------|
| `API_BASE_URL` | URL do backend FastAPI             | `http://localhost:8000/api/v1`   |
| `EXPO_PROJECT_ID` | ID do projeto no Expo.dev       | —                                |

---

## Tecnologias

| Lib                      | Uso                                      |
|--------------------------|------------------------------------------|
| Expo 51 + Expo Router    | Navegação file-based, build nativo       |
| React Native Reanimated 3| Animações fluidas (robôs, onboarding)   |
| Zustand + AsyncStorage   | Estado global persistido offline        |
| Axios + TanStack Query   | Chamadas ao backend FastAPI             |
| Expo LinearGradient      | Header dashboard, card dark GA          |
| Expo Haptics             | Feedback tátil (seleção, cruzamento)    |
| Expo SecureStore         | Armazenamento seguro de chaves          |

---

## Arquitetura — Fluxo de dados

```
Onboarding Quiz
     ↓ POST /onboarding/profile
FastAPI Backend ← yfinance (B3 + Cripto)
     ↓ OnboardingResult (score, Kelly, FIRE)
Zustand Store (persistido AsyncStorage)
     ↓
Dashboard / FIRE / Robôs / IA
     ↓ (Robôs: GA engine roda LOCAL no device)
GA Engine (TypeScript) → crossover → mutação → Sortino fitness
     ↓ quando usuário pede análise
POST /ia/analyze → Claude API → análise personalizada
```

O GA roda **100% no device** para privacidade total — sem enviar dados do portfólio para otimização genética. Apenas a análise textual usa a Claude API.
