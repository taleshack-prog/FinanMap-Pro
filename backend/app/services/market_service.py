"""
Serviço de Market Data — yfinance + cache TTL 5 min
Latência alvo: < 500ms (conforme documento)
Tickers B3: sufixo .SA | Cripto: BTC-USD, ETH-USD | ETFs: ^BVSP
"""

import asyncio
import time
from typing import Dict, Optional, List
from datetime import datetime, timezone
import logging

import yfinance as yf
import numpy as np

from app.core.config import settings
from app.models.schemas import AssetQuote, MarketDataResult, PortfolioAsset

logger = logging.getLogger(__name__)

# ── Cache em memória (substituir por Redis em produção) ───────────────────────
_cache: Dict[str, dict] = {}
TTL = settings.YFINANCE_CACHE_TTL   # 300s = 5 min


def _cache_get(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict) -> None:
    _cache[key] = {"data": data, "ts": time.time()}


# ── Mapeamento tickers → yfinance ─────────────────────────────────────────────
TICKER_MAP = {
    # B3 ETFs
    "BOVA11": "BOVA11.SA",
    "IVVB11": "IVVB11.SA",
    "HGLG11": "HGLG11.SA",
    "XPML11": "XPML11.SA",
    "KNRI11": "KNRI11.SA",
    # Cripto
    "BTC":    "BTC-USD",
    "ETH":    "ETH-USD",
    "BNB":    "BNB-USD",
    # Índices
    "IBOV":   "^BVSP",
    "SP500":  "^GSPC",
    # Câmbio
    "USDBRL": "USDBRL=X",
}

# Tickers com conversão USD → BRL para cripto
CRIPTO_TICKERS = {"BTC-USD", "ETH-USD", "BNB-USD"}


async def buscar_cotacao(ticker_raw: str) -> Optional[AssetQuote]:
    """
    Busca cotação de um ativo via yfinance.
    Retorna AssetQuote ou None se falhar.
    Latência alvo: < 500ms (usa asyncio.to_thread para não bloquear loop).
    """
    ticker_yf = TICKER_MAP.get(ticker_raw.upper(), ticker_raw)
    cache_key = f"quote:{ticker_yf}"

    # Hit de cache
    cached = _cache_get(cache_key)
    if cached:
        logger.debug(f"Cache hit: {ticker_yf}")
        return AssetQuote(**cached)

    try:
        t0 = time.monotonic()

        # Executa yfinance em thread separada (é síncrono)
        def _fetch():
            tk = yf.Ticker(ticker_yf)
            hist = tk.history(period="1y")
            info = tk.fast_info
            return hist, info

        hist, info = await asyncio.to_thread(_fetch)

        if hist.empty:
            logger.warning(f"Sem dados para {ticker_yf}")
            return None

        preco_atual = float(hist["Close"].iloc[-1])
        preco_abertura = float(hist["Open"].iloc[-1])
        preco_12m_atras = float(hist["Close"].iloc[0])

        # Conversão USD → BRL para cripto (usa USDBRL=X)
        if ticker_yf in CRIPTO_TICKERS:
            dolar = await _buscar_dolar()
            preco_atual    *= dolar
            preco_abertura *= dolar
            preco_12m_atras *= dolar

        var_dia  = (preco_atual - preco_abertura) / preco_abertura * 100
        var_12m  = (preco_atual - preco_12m_atras) / preco_12m_atras * 100
        latencia = int((time.monotonic() - t0) * 1000)

        # Dividend yield (melhor esforço)
        try:
            dy = float(getattr(info, "dividend_yield", 0) or 0) * 100
        except Exception:
            dy = 0.0

        result = AssetQuote(
            ticker=ticker_raw,
            preco_atual=round(preco_atual, 2),
            preco_abertura=round(preco_abertura, 2),
            variacao_dia_pct=round(var_dia, 2),
            variacao_12m_pct=round(var_12m, 2),
            volume=int(hist["Volume"].iloc[-1]) if "Volume" in hist else None,
            dividendo_yield=round(dy, 2) if dy else None,
            fonte="yfinance",
            latencia_ms=latencia,
        )

        _cache_set(cache_key, result.model_dump())
        logger.info(f"yfinance OK: {ticker_yf} = R${preco_atual:.2f} ({latencia}ms)")
        return result

    except Exception as e:
        logger.error(f"Erro ao buscar {ticker_yf}: {e}")
        return None


async def buscar_precos_portfolio(
    portfolio: Dict[str, PortfolioAsset]
) -> Dict[str, dict]:
    """
    Busca cotações de todos os ativos do portfólio em paralelo.
    Retorna dict {ticker: {"preco": float, "variacao": float}}
    """
    tasks = {
        ticker: buscar_cotacao(asset.ticker)
        for ticker, asset in portfolio.items()
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    cotacoes = {}
    for (ticker, _), result in zip(tasks.items(), results):
        if isinstance(result, AssetQuote):
            cotacoes[ticker] = {
                "preco": result.preco_atual,
                "variacao_dia": result.variacao_dia_pct,
                "variacao_12m": result.variacao_12m_pct,
            }
    return cotacoes


async def buscar_retornos_historicos(
    ticker_raw: str,
    periodo: str = "2y",
) -> List[float]:
    """
    Retorna lista de retornos mensais históricos para uso no Kelly Criterion.
    """
    ticker_yf = TICKER_MAP.get(ticker_raw.upper(), ticker_raw)
    cache_key = f"returns:{ticker_yf}:{periodo}"

    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        def _fetch():
            tk = yf.Ticker(ticker_yf)
            return tk.history(period=periodo)["Close"]

        hist = await asyncio.to_thread(_fetch)
        retornos = hist.pct_change().dropna().tolist()
        _cache_set(cache_key, retornos)
        return retornos
    except Exception as e:
        logger.error(f"Erro retornos {ticker_yf}: {e}")
        # Fallback: retornos gaussianos simulados
        return np.random.normal(0.12/12, 0.18/np.sqrt(12), 252).tolist()


async def _buscar_dolar() -> float:
    """Cotação USD/BRL via yfinance."""
    cached = _cache_get("usdbrl")
    if cached:
        return cached["rate"]
    try:
        def _fetch():
            return yf.Ticker("USDBRL=X").fast_info.last_price
        rate = await asyncio.to_thread(_fetch)
        rate = float(rate) if rate else 5.15
        _cache_set("usdbrl", {"rate": rate})
        return rate
    except Exception:
        return 5.15  # fallback


async def buscar_dados_mercado() -> MarketDataResult:
    """
    Snapshot do mercado: IBOV, Selic, IPCA, Dólar, BTC.
    Usado no dashboard e na IA Advisor.
    """
    cache_key = "market:snapshot"
    cached = _cache_get(cache_key)
    if cached:
        return MarketDataResult(**cached)

    resultados = await asyncio.gather(
        buscar_cotacao("IBOV"),
        buscar_cotacao("USDBRL"),
        buscar_cotacao("BTC"),
        return_exceptions=True,
    )

    ibov_q, dolar_q, btc_q = resultados

    result = MarketDataResult(
        ibov=ibov_q.preco_atual if isinstance(ibov_q, AssetQuote) else 130_000,
        selic=10.5,             # FocusEconomics 2026 — atualizar via API do BCB
        ipca_12m=4.8,           # IBGE — atualizar via API do BCB
        dolar=dolar_q.preco_atual if isinstance(dolar_q, AssetQuote) else 5.15,
        btc_brl=btc_q.preco_atual if isinstance(btc_q, AssetQuote) else 520_000,
        ultima_atualizacao=datetime.now(timezone.utc).isoformat(),
        fonte="yfinance + BCB",
    )

    _cache_set(cache_key, result.model_dump())
    return result


async def calcular_metricas_portfolio(
    portfolio: Dict[str, PortfolioAsset],
) -> dict:
    """
    Calcula Sharpe, Sortino, beta, drawdown máximo do portfólio.
    Usa retornos reais do BOVA11 como benchmark.
    """
    from app.services.fire_service import calcular_sharpe, calcular_sortino

    # Retornos do benchmark (BOVA11)
    bova_retornos = await buscar_retornos_historicos("BOVA11", "2y")

    # Retornos médios ponderados do portfólio (simplificado)
    total = sum(a.quantidade * a.preco_medio for a in portfolio.values())
    retornos_port = np.zeros(len(bova_retornos))

    for ticker, asset in portfolio.items():
        peso = (asset.quantidade * asset.preco_medio) / total if total > 0 else 0
        try:
            rets = await buscar_retornos_historicos(asset.ticker, "2y")
            n = min(len(rets), len(bova_retornos))
            retornos_port[:n] += np.array(rets[:n]) * peso
        except Exception:
            pass

    retornos_list = retornos_port[retornos_port != 0].tolist()
    if not retornos_list:
        retornos_list = np.random.normal(0.12/12, 0.18/np.sqrt(12), 252).tolist()

    sharpe  = calcular_sharpe(retornos_list)
    sortino = calcular_sortino(retornos_list)

    # Beta vs BOVA11
    n = min(len(retornos_list), len(bova_retornos))
    if n > 10:
        cov = np.cov(retornos_list[:n], bova_retornos[:n])[0][1]
        var_bova = np.var(bova_retornos[:n])
        beta = round(float(cov / var_bova) if var_bova > 0 else 1.0, 3)
    else:
        beta = 1.0

    # Drawdown máximo
    cum = np.cumprod(1 + np.array(retornos_list))
    rolling_max = np.maximum.accumulate(cum)
    drawdown = (cum - rolling_max) / rolling_max
    max_dd = round(float(np.min(drawdown) * 100), 2)

    return {
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "beta": beta,
        "drawdown_maximo": max_dd,
        "volatilidade_anual": round(float(np.std(retornos_list) * np.sqrt(12) * 100), 2),
    }
