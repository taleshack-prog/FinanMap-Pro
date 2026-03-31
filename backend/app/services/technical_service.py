"""
FinanMap Pro — Serviço de Análise Técnica v2
Indicadores clássicos + fluxo + quantitativos
"""
import math
import statistics
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# INDICADORES CLÁSSICOS
# ══════════════════════════════════════════════════════

def calcular_rsi(precos: List[float], periodo: int = 14) -> float:
    if len(precos) < periodo + 1:
        return 50.0
    deltas = [precos[i] - precos[i-1] for i in range(1, len(precos))]
    gains = [max(0, d) for d in deltas[-periodo:]]
    losses = [abs(min(0, d)) for d in deltas[-periodo:]]
    avg_gain = sum(gains) / periodo
    avg_loss = sum(losses) / periodo
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calcular_ema(precos: List[float], periodo: int) -> List[float]:
    if not precos:
        return []
    k = 2 / (periodo + 1)
    emas = [precos[0]]
    for p in precos[1:]:
        emas.append(p * k + emas[-1] * (1 - k))
    return emas


def calcular_macd(precos: List[float], rapida=12, lenta=26, sinal=9) -> Tuple[float, float, float]:
    if len(precos) < lenta:
        return 0.0, 0.0, 0.0
    ema_r = calcular_ema(precos, rapida)
    ema_l = calcular_ema(precos, lenta)
    n = min(len(ema_r), len(ema_l))
    macd_line = [ema_r[i] - ema_l[i] for i in range(n)]
    signal_line = calcular_ema(macd_line, sinal)
    hist = macd_line[-1] - signal_line[-1]
    return round(macd_line[-1], 6), round(signal_line[-1], 6), round(hist, 6)


def calcular_bollinger(precos: List[float], periodo: int = 20, num_std: float = 2.0) -> Tuple[float, float, float, float]:
    if len(precos) < periodo:
        p = precos[-1]
        return p*1.02, p, p*0.98, 0.5
    janela = precos[-periodo:]
    media = sum(janela) / periodo
    std = statistics.stdev(janela)
    upper = media + num_std * std
    lower = media - num_std * std
    posicao = (precos[-1] - lower) / (upper - lower) if upper != lower else 0.5
    return round(upper, 6), round(media, 6), round(lower, 6), round(posicao, 4)


def calcular_vwap(precos: List[float], volumes: Optional[List[float]] = None) -> float:
    """VWAP — preço médio ponderado por volume."""
    if not precos:
        return 0.0
    if not volumes or len(volumes) != len(precos):
        volumes = [1.0] * len(precos)
    pv = sum(p * v for p, v in zip(precos, volumes))
    tv = sum(volumes)
    return round(pv / tv, 6) if tv else precos[-1]


def calcular_vwap_desvios(precos: List[float], volumes: Optional[List[float]] = None) -> Dict:
    """VWAP com bandas de 1σ e 2σ — zonas institucionais."""
    vwap = calcular_vwap(precos, volumes)
    if not volumes:
        volumes = [1.0] * len(precos)
    tv = sum(volumes)
    variancia = sum(v * (p - vwap)**2 for p, v in zip(precos, volumes)) / tv if tv else 0
    std = math.sqrt(variancia)
    preco_atual = precos[-1]
    desvio = (preco_atual - vwap) / std if std else 0
    return {
        "vwap":      round(vwap, 6),
        "upper_1s":  round(vwap + std, 6),
        "upper_2s":  round(vwap + 2*std, 6),
        "lower_1s":  round(vwap - std, 6),
        "lower_2s":  round(vwap - 2*std, 6),
        "desvio_std": round(desvio, 3),
        "sinal_vwap": "compra" if desvio < -2 else "venda" if desvio > 2 else "neutro",
    }


# ══════════════════════════════════════════════════════
# INDICADORES DE FLUXO
# ══════════════════════════════════════════════════════

def calcular_cvd(trades: List[Dict]) -> Dict:
    """
    CVD — Cumulative Volume Delta.
    trades: lista de {"price": float, "volume": float, "side": "buy"|"sell"}
    Pressão compradora acumulada vs vendedora.
    Divergência CVD vs preço = sinal antecipado de reversão.
    """
    if not trades:
        return {"cvd": 0, "delta_pct": 0, "pressao": "neutra", "divergencia": False}

    buy_vol  = sum(t["volume"] for t in trades if t.get("side") == "buy")
    sell_vol = sum(t["volume"] for t in trades if t.get("side") == "sell")
    total    = buy_vol + sell_vol
    cvd      = buy_vol - sell_vol
    delta_pct = (cvd / total * 100) if total else 0

    # Detectar divergência: preço subindo mas CVD caindo = bearish divergence
    precos = [t["price"] for t in trades]
    cvds   = []
    acc    = 0
    for t in trades:
        acc += t["volume"] if t.get("side") == "buy" else -t["volume"]
        cvds.append(acc)

    divergencia = False
    if len(precos) >= 10:
        preco_trend = precos[-1] > precos[-10]
        cvd_trend   = cvds[-1] > cvds[-10]
        divergencia = preco_trend != cvd_trend  # divergência = sinais opostos

    return {
        "cvd":         round(cvd, 4),
        "buy_volume":  round(buy_vol, 4),
        "sell_volume": round(sell_vol, 4),
        "delta_pct":   round(delta_pct, 2),
        "pressao":     "compradora" if delta_pct > 15 else "vendedora" if delta_pct < -15 else "neutra",
        "divergencia": divergencia,
        "sinal": "compra" if delta_pct > 20 and not divergencia else
                 "venda"  if delta_pct < -20 and not divergencia else
                 "reversao_baixa" if divergencia and delta_pct < 0 else
                 "reversao_alta"  if divergencia and delta_pct > 0 else "neutro",
    }


def calcular_order_flow_imbalance(bids: List[Tuple], asks: List[Tuple], niveis: int = 5) -> Dict:
    """
    Order Flow Imbalance — desequilíbrio no livro de ordens.
    bids/asks: [(preco, quantidade), ...]
    OFI > 0.6 = pressão compradora forte → sinal de compra
    OFI < 0.4 = pressão vendedora forte → sinal de venda
    """
    if not bids or not asks:
        return {"ofi": 0.5, "sinal": "neutro", "bid_vol": 0, "ask_vol": 0}

    bid_vol = sum(q for _, q in bids[:niveis])
    ask_vol = sum(q for _, q in asks[:niveis])
    total   = bid_vol + ask_vol
    ofi     = bid_vol / total if total else 0.5

    return {
        "ofi":      round(ofi, 4),
        "bid_vol":  round(bid_vol, 4),
        "ask_vol":  round(ask_vol, 4),
        "imbalance_pct": round((ofi - 0.5) * 200, 1),
        "sinal":    "compra" if ofi > 0.65 else "venda" if ofi < 0.35 else "neutro",
    }


def calcular_funding_rate_sinal(funding_rate: float) -> Dict:
    """
    Funding Rate — taxa de financiamento em futuros perpétuos.
    Positivo = longs pagam shorts → mercado sobrecomprado → SHORT
    Negativo = shorts pagam longs → mercado sobrevendido → LONG
    Estratégia: funding rate extremo = oportunidade de arbitragem
    """
    anualizado = funding_rate * 3 * 365 * 100  # 3 vezes por dia
    return {
        "funding_rate":   funding_rate,
        "anualizado_pct": round(anualizado, 2),
        "sinal": "short" if funding_rate > 0.01 else
                 "long"  if funding_rate < -0.005 else "neutro",
        "extremo": abs(funding_rate) > 0.05,
        "oportunidade_arb": abs(anualizado) > 50,  # >50% ao ano = arbitragem óbvia
        "descricao": (
            f"Longs pagando {funding_rate*100:.3f}% a cada 8h — mercado sobrecomprado"
            if funding_rate > 0 else
            f"Shorts pagando {abs(funding_rate)*100:.3f}% a cada 8h — mercado sobrevendido"
        ),
    }


def identificar_liquidation_levels(precos: List[float], open_interest: Optional[float] = None) -> Dict:
    """
    Liquidation Levels — zonas onde posições alavancadas serão liquidadas.
    Identifica clusters de preço onde stops e liquidações se acumulam.
    Estratégia: operar na direção das liquidações em cascata.
    """
    if len(precos) < 20:
        return {"niveis": [], "sinal": "neutro"}

    p = precos[-1]
    # Estimar níveis baseado em alavancagens comuns (10x, 25x, 50x, 100x)
    niveis = []
    for lev in [10, 25, 50, 100]:
        liq_long  = round(p * (1 - 1/lev * 0.9), 2)  # liquidação de longs
        liq_short = round(p * (1 + 1/lev * 0.9), 2)  # liquidação de shorts
        niveis.append({"alavancagem": lev, "liq_long": liq_long, "liq_short": liq_short})

    # Nível mais próximo
    mais_proximo = min(niveis, key=lambda n: min(abs(p - n["liq_long"]), abs(p - n["liq_short"])))
    dist_long  = abs(p - mais_proximo["liq_long"]) / p * 100
    dist_short = abs(p - mais_proximo["liq_short"]) / p * 100

    return {
        "preco_atual":    p,
        "niveis":         niveis,
        "dist_liq_long_pct":  round(dist_long, 2),
        "dist_liq_short_pct": round(dist_short, 2),
        "zona_perigo": dist_long < 3 or dist_short < 3,
        "sinal": "cuidado_liq_long" if dist_long < 3 else
                 "cuidado_liq_short" if dist_short < 3 else "seguro",
    }


# ══════════════════════════════════════════════════════
# INDICADORES QUANTITATIVOS
# ══════════════════════════════════════════════════════

def calcular_zscore(precos: List[float], periodo: int = 20) -> Dict:
    """
    Z-Score — quantos desvios padrão o preço está da média.
    Z > 2: sobrecomprado → vender
    Z < -2: sobrevendido → comprar
    Estratégia: mean reversion quando |Z| > 2
    """
    if len(precos) < periodo:
        return {"zscore": 0, "media": precos[-1] if precos else 0, "sinal": "neutro"}
    janela = precos[-periodo:]
    media  = sum(janela) / periodo
    std    = statistics.stdev(janela)
    zscore = (precos[-1] - media) / std if std else 0
    return {
        "zscore":    round(zscore, 3),
        "media":     round(media, 6),
        "std":       round(std, 6),
        "percentil": round(min(100, max(0, (zscore + 3) / 6 * 100)), 1),
        "sinal":     "venda"  if zscore > 2.0 else
                     "compra" if zscore < -2.0 else
                     "venda_fraca"  if zscore > 1.5 else
                     "compra_fraca" if zscore < -1.5 else "neutro",
    }


def calcular_hurst(precos: List[float], max_lag: int = 20) -> Dict:
    """
    Hurst Exponent — detecta o regime estatístico da série de preços.
    H < 0.5: mean-reverting (ZigZag) → estratégia de reversão
    H ≈ 0.5: random walk → sem edge
    H > 0.5: trending (momentum) → estratégia de tendência
    Resultado mais poderoso: combina com regime detection.
    """
    if len(precos) < max_lag * 2:
        return {"hurst": 0.5, "regime": "indefinido", "estrategia": "aguardar"}

    rs_values = []
    lags = range(2, min(max_lag, len(precos) // 2))

    for lag in lags:
        sub = precos[-lag*2:]
        retornos = [math.log(sub[i]/sub[i-1]) for i in range(1, len(sub)) if sub[i-1] > 0]
        if len(retornos) < 2:
            continue
        media = sum(retornos) / len(retornos)
        desv  = [r - media for r in retornos]
        cum   = [sum(desv[:i+1]) for i in range(len(desv))]
        R     = max(cum) - min(cum)
        S     = statistics.stdev(retornos) if len(retornos) > 1 else 1
        if S > 0:
            rs_values.append((math.log(lag), math.log(R/S)))

    if len(rs_values) < 3:
        return {"hurst": 0.5, "regime": "indefinido", "estrategia": "aguardar"}

    # Regressão linear para estimar H
    n   = len(rs_values)
    sx  = sum(x for x, _ in rs_values)
    sy  = sum(y for _, y in rs_values)
    sxy = sum(x*y for x, y in rs_values)
    sxx = sum(x*x for x, _ in rs_values)
    H   = (n*sxy - sx*sy) / (n*sxx - sx**2) if (n*sxx - sx**2) else 0.5
    H   = max(0.1, min(0.9, H))

    return {
        "hurst":      round(H, 4),
        "regime":     "mean_reverting" if H < 0.45 else
                      "trending"       if H > 0.55 else "random_walk",
        "confianca":  round(abs(H - 0.5) * 200, 1),
        "estrategia": "reversao_media" if H < 0.45 else
                      "momentum"       if H > 0.55 else "neutro",
        "descricao":  f"H={H:.3f} — {'série mean-reverting, apostar na reversão' if H < 0.45 else 'série trending, seguir a tendência' if H > 0.55 else 'random walk, sem edge estatístico'}",
    }


def detectar_regime(precos: List[float], volumes: Optional[List[float]] = None) -> Dict:
    """
    Regime Detection — identifica o regime atual do mercado.
    Combina volatilidade, tendência e volume para classificar:
    BULL_TRENDING, BEAR_TRENDING, HIGH_VOL, LOW_VOL, LATERAL
    Cada regime tem a estratégia ótima correspondente.
    """
    if len(precos) < 30:
        return {"regime": "indefinido", "estrategia": "aguardar", "confianca": 0}

    # Tendência
    sma_20 = sum(precos[-20:]) / 20
    sma_50 = sum(precos[-min(50, len(precos)):]) / min(50, len(precos))
    tendencia_alta = precos[-1] > sma_20 > sma_50

    # Volatilidade
    retornos = [abs(precos[i]/precos[i-1]-1) for i in range(1, len(precos))]
    vol_atual  = sum(retornos[-10:]) / 10 if len(retornos) >= 10 else 0
    vol_media  = sum(retornos[-30:]) / min(30, len(retornos)) if retornos else 0
    alta_vol   = vol_atual > vol_media * 1.5

    # Momentum
    retorno_5d  = (precos[-1] / precos[-5] - 1) if len(precos) >= 5 else 0
    retorno_20d = (precos[-1] / precos[-20] - 1) if len(precos) >= 20 else 0

    # Classificar regime
    if tendencia_alta and not alta_vol and retorno_20d > 0.05:
        regime, estrategia = "BULL_TRENDING", "momentum_long"
    elif not tendencia_alta and not alta_vol and retorno_20d < -0.05:
        regime, estrategia = "BEAR_TRENDING", "momentum_short_ou_cash"
    elif alta_vol and abs(retorno_5d) > 0.05:
        regime, estrategia = "HIGH_VOLATILITY", "reducao_sizing_stops_largos"
    elif not alta_vol and abs(retorno_20d) < 0.02:
        regime, estrategia = "LATERAL_LOW_VOL", "mean_reversion_zscore"
    else:
        regime, estrategia = "TRANSICAO", "aguardar_confirmacao"

    confianca = min(95, int(abs(retorno_20d) * 500 + (50 if not alta_vol else 20)))

    return {
        "regime":        regime,
        "estrategia":    estrategia,
        "tendencia_alta":tendencia_alta,
        "alta_vol":      alta_vol,
        "retorno_5d_pct": round(retorno_5d * 100, 2),
        "retorno_20d_pct":round(retorno_20d * 100, 2),
        "vol_atual_pct":  round(vol_atual * 100, 3),
        "confianca":      confianca,
        "sma_20":         round(sma_20, 4),
        "sma_50":         round(sma_50, 4),
    }


def calcular_kelly_dinamico(win_rate: float, avg_win: float, avg_loss: float, regime: str) -> Dict:
    """
    Kelly Criterion dinâmico — tamanho de posição ajustado pelo regime.
    Kelly clássico: f* = (bp - q) / b
    Ajustado: metade do Kelly para reduzir drawdown.
    """
    if avg_loss == 0:
        return {"kelly": 0, "kelly_half": 0, "recomendado_pct": 0}
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    kelly = (b * p - q) / b
    kelly = max(0, min(1, kelly))

    # Ajuste por regime
    mult = {"BULL_TRENDING": 0.6, "BEAR_TRENDING": 0.3, "HIGH_VOLATILITY": 0.2,
            "LATERAL_LOW_VOL": 0.5, "TRANSICAO": 0.25}.get(regime, 0.4)

    kelly_adj = kelly * mult
    return {
        "kelly_full":    round(kelly * 100, 1),
        "kelly_half":    round(kelly * 0.5 * 100, 1),
        "kelly_regime":  round(kelly_adj * 100, 1),
        "recomendado_pct": round(kelly_adj * 100, 1),
        "regime_mult":   mult,
        "descricao": f"Apostar {kelly_adj*100:.1f}% do capital por operação no regime {regime}",
    }


# ══════════════════════════════════════════════════════
# SINAL UNIFICADO — TODOS OS INDICADORES
# ══════════════════════════════════════════════════════

def sintetizar_sinal_avancado(
    precos: List[float],
    volumes: Optional[List[float]] = None,
    trades: Optional[List[Dict]] = None,
    bids: Optional[List[Tuple]] = None,
    asks: Optional[List[Tuple]] = None,
    funding_rate: Optional[float] = None,
) -> Dict:
    """
    Sinal unificado com todos os indicadores.
    Pesos: fluxo (40%) + quantitativo (35%) + clássico (25%)
    """
    scores = []
    detalhes = {}

    # ── Clássicos (25%) ──
    rsi = calcular_rsi(precos)
    _, _, macd_h = calcular_macd(precos)
    _, _, _, bb_p = calcular_bollinger(precos)

    score_rsi  = (50 - rsi) / 50 if rsi < 50 else -(rsi - 50) / 50
    score_macd = 1 if macd_h > 0 else -1
    score_bb   = (0.5 - bb_p) * 2
    score_classico = (score_rsi + score_macd + score_bb) / 3
    scores.append(("classico", score_classico, 0.25))
    detalhes["rsi"] = rsi
    detalhes["macd_hist"] = macd_h
    detalhes["bb_posicao"] = bb_p

    # ── Z-Score (15%) ──
    zs = calcular_zscore(precos)
    score_z = max(-1, min(1, -zs["zscore"] / 2))
    scores.append(("zscore", score_z, 0.15))
    detalhes["zscore"] = zs["zscore"]

    # ── Hurst (10%) ──
    hurst = calcular_hurst(precos)
    score_hurst = 0  # neutro se random walk
    if hurst["regime"] == "mean_reverting":
        score_hurst = score_z  # amplifica sinal de reversão
    elif hurst["regime"] == "trending":
        score_hurst = 1 if precos[-1] > precos[-5] else -1
    scores.append(("hurst", score_hurst, 0.10))
    detalhes["hurst"] = hurst["hurst"]
    detalhes["regime_hurst"] = hurst["regime"]

    # ── Regime (10%) ──
    regime = detectar_regime(precos, volumes)
    score_regime = {"BULL_TRENDING": 0.7, "BEAR_TRENDING": -0.7,
                    "HIGH_VOLATILITY": 0, "LATERAL_LOW_VOL": score_z,
                    "TRANSICAO": 0}.get(regime["regime"], 0)
    scores.append(("regime", score_regime, 0.10))
    detalhes["regime"] = regime["regime"]

    # ── VWAP (10%) ──
    vwap_data = calcular_vwap_desvios(precos, volumes)
    score_vwap = max(-1, min(1, -vwap_data["desvio_std"] / 2))
    scores.append(("vwap", score_vwap, 0.10))
    detalhes["vwap_desvio"] = vwap_data["desvio_std"]

    # ── CVD (15%) ──
    if trades:
        cvd = calcular_cvd(trades)
        score_cvd = cvd["delta_pct"] / 100
        if cvd["divergencia"]:
            score_cvd = -score_cvd  # divergência inverte o sinal
        scores.append(("cvd", score_cvd, 0.15))
        detalhes["cvd"] = cvd["cvd"]
        detalhes["cvd_pressao"] = cvd["pressao"]

    # ── Order Flow (15%) ──
    if bids and asks:
        ofi = calcular_order_flow_imbalance(bids, asks)
        score_ofi = (ofi["ofi"] - 0.5) * 2
        scores.append(("ofi", score_ofi, 0.15))
        detalhes["ofi"] = ofi["ofi"]

    # ── Funding Rate (ajuste de sinal) ──
    if funding_rate is not None:
        fr = calcular_funding_rate_sinal(funding_rate)
        detalhes["funding_rate"] = funding_rate
        detalhes["funding_sinal"] = fr["sinal"]

    # ── Score final ponderado ──
    total_peso = sum(w for _, _, w in scores)
    score_final = sum(s * w for _, s, w in scores) / total_peso if total_peso else 0
    score_final = max(-1, min(1, score_final))

    forca = abs(score_final)
    sinal = "compra" if score_final > 0.15 else "venda" if score_final < -0.15 else "neutro"

    return {
        "sinal":       sinal,
        "score":       round(score_final, 4),
        "forca":       round(forca, 4),
        "forca_pct":   round(forca * 100, 1),
        "confianca":   "alta" if forca > 0.6 else "media" if forca > 0.35 else "baixa",
        "preco_atual": precos[-1],
        "detalhes":    detalhes,
        "regime":      regime["regime"],
        "estrategia_recomendada": regime["estrategia"],
        "componentes": [{"indicador": n, "score": round(s, 4), "peso": w}
                        for n, s, w in scores],
    }


def sintetizar_sinal(rsi: float, macd_hist: float, bb_posicao: float) -> Tuple[str, float]:
    """Compatibilidade com código legado."""
    score = 0.0
    score += (50 - rsi) / 50 * 0.4
    score += (1 if macd_hist > 0 else -1) * 0.3
    score += (0.5 - bb_posicao) * 2 * 0.3
    forca = abs(score)
    sinal = "compra" if score > 0.1 else "venda" if score < -0.1 else "neutro"
    return sinal, round(forca, 4)


# ══════════════════════════════════════════════════════
# STRESS TEST E RISCO
# ══════════════════════════════════════════════════════

def calcular_stress(alocacao: Dict[str, float], patrimonio: float) -> Dict:
    CENARIOS = {
        "crash_cripto_2022": {"cripto": -0.73, "renda_var": -0.12, "internacional": -0.15, "renda_fixa": 0.08},
        "covid_2020":        {"cripto": -0.50, "renda_var": -0.40, "internacional": -0.35, "renda_fixa": 0.02},
        "crise_br_2015":     {"cripto": 0.20,  "renda_var": -0.31, "internacional": 0.15,  "renda_fixa": 0.13},
        "inflacao_2022":     {"cripto": -0.65, "renda_var": -0.18, "internacional": -0.20, "renda_fixa": -0.05},
        "cenario_base_2026": {"cripto": 0.45,  "renda_var": 0.12,  "internacional": 0.14,  "renda_fixa": 0.10},
        "bull_crypto_2024":  {"cripto": 1.60,  "renda_var": 0.25,  "internacional": 0.18,  "renda_fixa": 0.09},
    }
    resultado = {}
    for nome, impactos in CENARIOS.items():
        impacto_total = sum(
            (alocacao.get(cls, 0) / 100) * imp
            for cls, imp in impactos.items()
        )
        resultado[nome] = {
            "impacto_pct": round(impacto_total * 100, 1),
            "impacto_brl": round(patrimonio * impacto_total, 2),
            "positivo":    impacto_total >= 0,
        }
    return resultado


def calcular_var_cvar(retornos_ativos: Dict, pesos: Dict, patrimonio: float,
                       nivel_confianca: float = 0.95) -> Dict:
    import statistics as st
    if not retornos_ativos:
        return {"var_95_pct": 0, "cvar_95_pct": 0}
    tickers = list(retornos_ativos.keys())
    n = min(len(v) for v in retornos_ativos.values())
    portfolio_ret = []
    for i in range(n):
        r = sum((pesos.get(t, 0)/100) * retornos_ativos[t][i]
                for t in tickers if i < len(retornos_ativos[t]))
        portfolio_ret.append(r)
    if len(portfolio_ret) < 5:
        return {"var_95_pct": 0, "cvar_95_pct": 0}
    portfolio_ret.sort()
    idx = int((1 - nivel_confianca) * len(portfolio_ret))
    var = -portfolio_ret[idx] * 100
    cvar = -sum(portfolio_ret[:idx]) / idx * 100 if idx > 0 else var
    mu  = sum(portfolio_ret) / len(portfolio_ret)
    std = st.stdev(portfolio_ret)
    sharpe  = (mu / std * (252**0.5)) if std else 0
    neg     = [r for r in portfolio_ret if r < 0]
    std_neg = st.stdev(neg) if len(neg) > 1 else std
    sortino = (mu / std_neg * (252**0.5)) if std_neg else 0
    max_dd  = 0
    peak    = portfolio_ret[0]
    for r in portfolio_ret:
        peak = max(peak, r)
        max_dd = min(max_dd, r - peak)
    return {
        "var_95_pct":         round(var, 4),
        "var_99_pct":         round(-portfolio_ret[max(0, int(0.01*len(portfolio_ret)))] * 100, 4),
        "cvar_95_pct":        round(cvar, 4),
        "var_portfolio_95_brl": round(patrimonio * var / 100, 2),
        "sharpe":             round(sharpe, 4),
        "sortino":            round(sortino, 4),
        "max_drawdown":       round(max_dd * 100, 4),
    }


# ══════════════════════════════════════════════════════
# FUNÇÕES DE ALTO NÍVEL (usadas pelos routers)
# ══════════════════════════════════════════════════════

def analisar_ativo(ticker: str, precos: List[float],
                   volumes: Optional[List[float]] = None) -> Dict:
    """Análise completa de um ativo — clássicos + quantitativos."""
    if not precos:
        return {"erro": "Sem dados de preço"}

    rsi = calcular_rsi(precos)
    _, _, macd_h = calcular_macd(precos)
    bb_u, bb_m, bb_l, bb_p = calcular_bollinger(precos)
    sinal_cl, forca_cl = sintetizar_sinal(rsi, macd_h, bb_p)
    zs   = calcular_zscore(precos)
    hurst = calcular_hurst(precos)
    regime = detectar_regime(precos, volumes)
    vwap_d = calcular_vwap_desvios(precos, volumes)

    # Sinal avançado
    avancado = sintetizar_sinal_avancado(precos, volumes)

    emas = calcular_ema(precos, 9)
    smas20 = precos[-20:] if len(precos) >= 20 else precos
    sma20 = sum(smas20) / len(smas20)
    smas50 = precos[-50:] if len(precos) >= 50 else precos
    sma50 = sum(smas50) / len(smas50)

    return {
        "ticker":      ticker,
        "preco_atual": precos[-1],
        "sinal":       avancado["sinal"],
        "forca_sinal": avancado["forca"],
        "score":       avancado["score"],
        "confianca":   avancado["confianca"],
        "rsi":         rsi,
        "macd_hist":   macd_h,
        "bollinger": {
            "upper": bb_u, "middle": bb_m, "lower": bb_l, "posicao": bb_p
        },
        "medias": {
            "ema_9": round(emas[-1], 6) if emas else precos[-1],
            "sma_20": round(sma20, 6),
            "sma_50": round(sma50, 6),
        },
        "zscore":      zs["zscore"],
        "hurst":       hurst["hurst"],
        "regime":      regime["regime"],
        "vwap":        vwap_d["vwap"],
        "vwap_desvio": vwap_d["desvio_std"],
        "tendencia":   "alta" if precos[-1] > sma20 > sma50 else
                       "baixa" if precos[-1] < sma20 < sma50 else "lateral",
        "score_100":   round(avancado["forca"] * 100),
        "detalhes_avancados": avancado["detalhes"],
        "estrategia_recomendada": regime["estrategia"],
    }


def calcular_risco_portfolio(retornos_ativos: Dict, pesos: Dict, patrimonio: float) -> Dict:
    """Wrapper para VaR/CVaR — usado pelo router tecnico."""
    return calcular_var_cvar(retornos_ativos, pesos, patrimonio)


def stress_test_expandido(alocacao: Dict[str, float], patrimonio: float) -> Dict:
    """Wrapper para stress test — usado pelo router tecnico."""
    return calcular_stress(alocacao, patrimonio)
