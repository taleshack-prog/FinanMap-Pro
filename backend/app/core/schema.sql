-- FinanMap Pro — Schema Supabase Postgres
-- Execute no SQL Editor do Supabase dashboard
-- ou via: psql $DATABASE_URL < schema.sql

-- ── Extensões ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── 1. Usuários (estende auth.users do Supabase) ───────────────────────────
CREATE TABLE IF NOT EXISTS public.usuarios (
    id                UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nome              TEXT,
    perfil_risco      TEXT CHECK (perfil_risco IN ('conservador','moderado','moderado_agressivo','agressivo')),
    score_risco       INTEGER CHECK (score_risco BETWEEN 0 AND 100),
    patrimonio_atual  DECIMAL(15,2) DEFAULT 0,
    aporte_mensal     DECIMAL(12,2) DEFAULT 0,
    despesas_mensais  DECIMAL(12,2) DEFAULT 0,
    horizonte_anos    INTEGER DEFAULT 10,
    incluir_cripto    BOOLEAN DEFAULT TRUE,
    totp_secret       TEXT,                          -- segredo 2FA (criptografado)
    onboarding_done   BOOLEAN DEFAULT FALSE,
    plano             TEXT DEFAULT 'free' CHECK (plano IN ('free','pro','elite')),
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ DEFAULT NOW()
);

-- ── 2. Portfólios ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.portfolios (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id        UUID NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    nome              TEXT DEFAULT 'Principal',
    total_atual       DECIMAL(15,2) DEFAULT 0,
    total_investido   DECIMAL(15,2) DEFAULT 0,
    sharpe_ratio      DECIMAL(8,4),
    sortino_ratio     DECIMAL(8,4),
    volatilidade      DECIMAL(8,4),
    beta              DECIMAL(8,4),
    max_drawdown      DECIMAL(8,4),
    ativo             BOOLEAN DEFAULT TRUE,
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ DEFAULT NOW()
);

-- ── 3. Ativos do portfólio ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ativos (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id      UUID NOT NULL REFERENCES public.portfolios(id) ON DELETE CASCADE,
    ticker            TEXT NOT NULL,
    nome              TEXT,
    classe            TEXT NOT NULL CHECK (classe IN ('renda_fixa','renda_var','cripto','internacional','fii')),
    quantidade        DECIMAL(18,8) DEFAULT 0,
    preco_medio       DECIMAL(15,4) DEFAULT 0,
    preco_atual       DECIMAL(15,4),
    total_investido   DECIMAL(15,2) DEFAULT 0,
    total_atual       DECIMAL(15,2),
    retorno_pct       DECIMAL(8,4),
    dividendo_yield   DECIMAL(8,4),
    data_ultima_cot   TIMESTAMPTZ,
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (portfolio_id, ticker)
);

-- ── 4. Estratégias dos Robôs ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.estrategias (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id        UUID NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    nome              TEXT NOT NULL,
    geracao           INTEGER DEFAULT 0,
    strain            TEXT,

    -- Genes de alocação (%)
    gene_renda_fixa     DECIMAL(5,2) DEFAULT 35,
    gene_renda_var      DECIMAL(5,2) DEFAULT 30,
    gene_internacional  DECIMAL(5,2) DEFAULT 15,
    gene_cripto         DECIMAL(5,2) DEFAULT 20,

    -- Genes de estratégia
    gene_horizonte        DECIMAL(6,1) DEFAULT 30,    -- dias
    gene_tolerancia_risco DECIMAL(4,3) DEFAULT 0.5,   -- 0–1
    gene_stop_loss        DECIMAL(5,3) DEFAULT -0.10, -- negativo

    -- Métricas
    sortino_ratio     DECIMAL(8,4),
    sharpe_ratio      DECIMAL(8,4),
    cagr_projetado    DECIMAL(6,2),
    fitness_score     DECIMAL(8,4),
    estrategia_tipo   TEXT CHECK (estrategia_tipo IN (
        'swing_trade','arbitragem','rebalanceamento','dividend_capture','stop_dinamico'
    )),

    -- Status
    ativa             BOOLEAN DEFAULT FALSE,
    aprovada_pelo_ga  BOOLEAN DEFAULT FALSE,
    nova_strain       BOOLEAN DEFAULT FALSE,
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ DEFAULT NOW()
);

-- ── 5. Execuções dos Robôs ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.robo_execucoes (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estrategia_id     UUID NOT NULL REFERENCES public.estrategias(id),
    usuario_id        UUID NOT NULL REFERENCES public.usuarios(id),
    portfolio_id      UUID NOT NULL REFERENCES public.portfolios(id),

    -- Operação
    tipo_operacao     TEXT NOT NULL CHECK (tipo_operacao IN (
        'rebalanceamento','compra','venda','stop_loss','dividend_capture','arbitragem'
    )),
    ticker            TEXT NOT NULL,
    quantidade        DECIMAL(18,8),
    preco_execucao    DECIMAL(15,4),
    valor_total       DECIMAL(15,2),
    taxa              DECIMAL(10,4) DEFAULT 0,

    -- Status
    status            TEXT DEFAULT 'pendente' CHECK (status IN (
        'pendente','aprovado_2fa','executando','concluido','cancelado','erro'
    )),
    corretora         TEXT DEFAULT 'simulado',  -- 'binance','xp','clear','simulado'

    -- 2FA
    requer_2fa        BOOLEAN DEFAULT TRUE,
    aprovado_2fa_em   TIMESTAMPTZ,
    aprovado_por      UUID REFERENCES public.usuarios(id),

    -- Resultado
    retorno_realizado DECIMAL(8,4),
    mensagem_erro     TEXT,
    dados_corretora   JSONB,

    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    executado_em      TIMESTAMPTZ,
    atualizado_em     TIMESTAMPTZ DEFAULT NOW()
);

-- ── 6. Projeções FIRE ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.projecoes_fire (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id        UUID NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    despesas_mensais  DECIMAL(12,2),
    aporte_mensal     DECIMAL(12,2),
    patrimonio_atual  DECIMAL(15,2),
    taxa_retorno      DECIMAL(6,4),
    meta_patrimonial  DECIMAL(15,2),
    anos_p50          DECIMAL(6,2),
    anos_p90          DECIMAL(6,2),
    prob_sucesso      DECIMAL(6,2),
    renda_passiva_mes DECIMAL(12,2),
    progresso_pct     DECIMAL(6,2),
    simulacoes        INTEGER DEFAULT 10000,
    cenarios          JSONB,          -- {otimista, base, estressado} arrays
    criado_em         TIMESTAMPTZ DEFAULT NOW()
);

-- ── 7. Alertas ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.alertas (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id        UUID NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    tipo              TEXT NOT NULL CHECK (tipo IN (
        'kelly_concentracao','nova_strain','stop_loss_atingido',
        'rebalanceamento_necessario','dividendo_ex_date','rsi_oversold',
        'rsi_overbought','meta_fire_atingida','mercado_queda'
    )),
    titulo            TEXT NOT NULL,
    mensagem          TEXT NOT NULL,
    ticker            TEXT,
    valor_referencia  DECIMAL(15,4),
    lido              BOOLEAN DEFAULT FALSE,
    acao_url          TEXT,
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    lido_em           TIMESTAMPTZ
);

-- ── 8. Histórico de Preços (time-series) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS public.historico_precos (
    id                BIGSERIAL PRIMARY KEY,
    ticker            TEXT NOT NULL,
    data              DATE NOT NULL,
    abertura          DECIMAL(15,4),
    maxima            DECIMAL(15,4),
    minima            DECIMAL(15,4),
    fechamento        DECIMAL(15,4) NOT NULL,
    volume            BIGINT,
    fonte             TEXT DEFAULT 'yfinance',
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, data)
);

-- ── Índices ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_portfolios_usuario     ON public.portfolios(usuario_id);
CREATE INDEX IF NOT EXISTS idx_ativos_portfolio       ON public.ativos(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_ativos_ticker          ON public.ativos(ticker);
CREATE INDEX IF NOT EXISTS idx_estrategias_usuario    ON public.estrategias(usuario_id);
CREATE INDEX IF NOT EXISTS idx_estrategias_ativa      ON public.estrategias(usuario_id, ativa);
CREATE INDEX IF NOT EXISTS idx_execucoes_usuario      ON public.robo_execucoes(usuario_id);
CREATE INDEX IF NOT EXISTS idx_execucoes_status       ON public.robo_execucoes(status);
CREATE INDEX IF NOT EXISTS idx_alertas_usuario_nao_lido ON public.alertas(usuario_id, lido);
CREATE INDEX IF NOT EXISTS idx_historico_ticker_data  ON public.historico_precos(ticker, data DESC);
CREATE INDEX IF NOT EXISTS idx_projecoes_usuario      ON public.projecoes_fire(usuario_id);

-- ── Row Level Security ────────────────────────────────────────────────────
ALTER TABLE public.usuarios         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolios       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ativos           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.estrategias      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.robo_execucoes   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projecoes_fire   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alertas          ENABLE ROW LEVEL SECURITY;

-- Políticas: cada usuário só acessa seus próprios dados
CREATE POLICY "usuarios_proprios"       ON public.usuarios         FOR ALL USING (auth.uid() = id);
CREATE POLICY "portfolios_proprios"     ON public.portfolios       FOR ALL USING (auth.uid() = usuario_id);
CREATE POLICY "ativos_proprios"         ON public.ativos           FOR ALL USING (auth.uid() = (SELECT usuario_id FROM public.portfolios WHERE id = portfolio_id));
CREATE POLICY "estrategias_proprias"    ON public.estrategias      FOR ALL USING (auth.uid() = usuario_id);
CREATE POLICY "execucoes_proprias"      ON public.robo_execucoes   FOR ALL USING (auth.uid() = usuario_id);
CREATE POLICY "projecoes_proprias"      ON public.projecoes_fire   FOR ALL USING (auth.uid() = usuario_id);
CREATE POLICY "alertas_proprios"        ON public.alertas          FOR ALL USING (auth.uid() = usuario_id);

-- historico_precos: leitura pública (dados de mercado não são privados)
CREATE POLICY "historico_leitura_publica" ON public.historico_precos FOR SELECT USING (true);
CREATE POLICY "historico_insercao_service" ON public.historico_precos FOR INSERT WITH CHECK (true);

-- ── Triggers: atualizado_em automático ───────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.atualizado_em = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_usuarios_upd         BEFORE UPDATE ON public.usuarios         FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_portfolios_upd       BEFORE UPDATE ON public.portfolios       FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_ativos_upd           BEFORE UPDATE ON public.ativos           FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_estrategias_upd      BEFORE UPDATE ON public.estrategias      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_execucoes_upd        BEFORE UPDATE ON public.robo_execucoes   FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── Funções utilitárias ───────────────────────────────────────────────────

-- Calcula progresso FIRE do usuário
CREATE OR REPLACE FUNCTION public.progresso_fire(p_usuario_id UUID)
RETURNS TABLE(meta DECIMAL, atual DECIMAL, progresso_pct DECIMAL, anos_restantes DECIMAL)
AS $$
DECLARE
    v_desp   DECIMAL; v_pat DECIMAL; v_anos DECIMAL;
BEGIN
    SELECT despesas_mensais, patrimonio_atual INTO v_desp, v_pat
    FROM public.usuarios WHERE id = p_usuario_id;
    SELECT anos_p50 INTO v_anos FROM public.projecoes_fire
    WHERE usuario_id = p_usuario_id ORDER BY criado_em DESC LIMIT 1;
    RETURN QUERY SELECT
        v_desp * 25 * 12 AS meta,
        v_pat             AS atual,
        LEAST(100, v_pat / NULLIF(v_desp * 25 * 12, 0) * 100) AS progresso_pct,
        COALESCE(v_anos, 0) AS anos_restantes;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Conta alertas não lidos por usuário
CREATE OR REPLACE FUNCTION public.alertas_nao_lidos(p_usuario_id UUID)
RETURNS INTEGER AS $$
    SELECT COUNT(*)::INTEGER FROM public.alertas
    WHERE usuario_id = p_usuario_id AND lido = FALSE;
$$ LANGUAGE sql SECURITY DEFINER;
