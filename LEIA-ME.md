# FinanMap Pro v3 — O que foi implementado

## Novidades v3 (implementado nesta sessão)

### ✅ GA Service v2 — Genoma de 7 genes
- 4 genes de alocação (renda_fixa, renda_var, internacional, cripto)
- 3 genes de estratégia: horizonte (1–180d), tolerância risco (0–1), stop loss (-25% a -2%)
- 5 estratégias emergentes: swing_trade, arbitragem, rebalanceamento, dividend_capture, stop_dinamico
- Fitness expandido: Sortino + bônus coerência + bônus consistência + penalidades
- Hipermutação automática quando estagnado por 10 gerações
- Seeds Kelly por perfil com todos os 7 genes

### ✅ Análise Técnica — RSI, MACD, Bollinger
- RSI (Wilder): oversold <30, overbought >70
- MACD: EMA(12)-EMA(26), signal EMA(9), histograma
- Bandas de Bollinger: SMA±2σ, posição relativa 0–1
- Sinal unificado: compra/venda/neutro com força 0–1
- Score técnico 0–100 (síntese dos 3 indicadores)

### ✅ VaR / CVaR — Risco quantitativo
- VaR paramétrico 95% e 99% (1 dia)
- CVaR (Expected Shortfall) histórico 95% e 99%
- VaR do portfólio em R$ com correlações reais
- Sharpe, Sortino, Calmar, Beta, Max Drawdown anualizados
- Stress test expandido com 6 cenários (crash cripto, covid, crise BR, inflação, base, bull crypto)

### ✅ Auth JWT + 2FA
- Supabase Auth: registro, login, refresh token
- 2FA TOTP (compatível Google Authenticator)
- Desafios 2FA para operações de robôs (TTL 5 min)
- FastAPI dependency: get_current_user, require_2fa
- Segurança HMAC-SHA256 nos tokens

### ✅ Schema Supabase — 8 tabelas
- usuarios, portfolios, ativos, estrategias
- robo_execucoes, projecoes_fire, alertas, historico_precos
- Row Level Security (RLS) em todas as tabelas
- Triggers updated_at automáticos
- Funções: progresso_fire(), alertas_nao_lidos()
- Arquivo: backend/app/core/schema.sql

### ✅ Robôs com Execução Real
- 5 robôs: RoboRebalanceamento, RoboSwingTrade, RoboStopLoss, RoboDividendCapture
- Fluxo: análise → proposta → aprovação 2FA → execução → log
- Binance API (testnet): spot orders, saldos, preços
- ExecutorSimulado: B3/XP/Clear (até integração real)
- RoboOrchestrator: todos os robôs em paralelo

### ✅ Novos endpoints v3
- POST /api/v1/auth/register, /login, /refresh
- POST /api/v1/auth/2fa/challenge, /2fa/verify
- POST /api/v1/robos/analisar, /executar
- POST /api/v1/tecnico/ativo (RSI/MACD/BB)
- POST /api/v1/tecnico/risco (VaR/CVaR)
- POST /api/v1/tecnico/stress (6 cenários)

## O que ainda falta (próximas sessões)

### Fase 3 — Pendente
- [ ] Integração real XP/Clear via webhooks (substituir ExecutorSimulado)
- [ ] LSTM para previsão de preços (ARIMA primeiro)
- [ ] Notificações push (Firebase FCM) para alertas dos robôs
- [ ] Dashboard admin com métricas de uso
- [ ] React Native: tela de robôs com 7 genes visuais

## Para rodar

cd backend
bash setup.sh    # primeira vez (instala deps + venv)
bash start.sh    # toda vez
→ http://localhost:8000/docs

## Schema do banco

Rodar no Supabase SQL Editor:
backend/app/core/schema.sql
