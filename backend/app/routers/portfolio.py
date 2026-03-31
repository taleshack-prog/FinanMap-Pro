"""
Router: Portfólio — /api/v1/portfolio
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import PortfolioInput, PortfolioResult, AssetQuote
from app.services.market_service import (
    buscar_cotacao, buscar_precos_portfolio, calcular_metricas_portfolio
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=PortfolioResult, summary="Análise completa do portfólio")
async def analyze_portfolio(payload: PortfolioInput):
    """
    Analisa portfólio com preços reais yfinance:
    - Cotações ao vivo (cache 5min)
    - Sharpe, Sortino, Beta vs BOVA11
    - Drawdown máximo
    - Dividend yield
    """
    try:
        cotacoes_raw = await buscar_precos_portfolio(payload.ativos)
        metricas = await calcular_metricas_portfolio(payload.ativos)

        total_investido = sum(
            a.quantidade * a.preco_medio for a in payload.ativos.values()
        )
        total_atual = sum(
            a.quantidade * cotacoes_raw.get(t, {}).get("preco", a.preco_medio)
            for t, a in payload.ativos.items()
        )
        ganho = total_atual - total_investido
        ganho_pct = (ganho / total_investido * 100) if total_investido > 0 else 0

        # Alocação por classe
        alocacao: dict = {}
        for ticker, asset in payload.ativos.items():
            valor = asset.quantidade * cotacoes_raw.get(ticker, {}).get("preco", asset.preco_medio)
            classe = asset.classe.value
            alocacao[classe] = alocacao.get(classe, 0) + valor

        if total_atual > 0:
            alocacao = {k: round(v / total_atual * 100, 2) for k, v in alocacao.items()}

        # Cotações formatadas
        cotacoes_formatadas: dict = {}
        for ticker in payload.ativos:
            q = await buscar_cotacao(ticker)
            if q:
                cotacoes_formatadas[ticker] = q

        return PortfolioResult(
            total_atual=round(total_atual, 2),
            total_investido=round(total_investido, 2),
            ganho_total=round(ganho, 2),
            ganho_pct=round(ganho_pct, 2),
            sharpe_ratio=metricas["sharpe_ratio"],
            volatilidade_anual=metricas["volatilidade_anual"],
            beta=metricas["beta"],
            dividendos_12m=total_atual * 0.034,  # yield médio 3.4%
            cotacoes=cotacoes_formatadas,
            alocacao_atual=alocacao,
            drawdown_maximo=metricas["drawdown_maximo"],
        )
    except Exception as e:
        logger.error(f"Erro portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote/{ticker}", response_model=AssetQuote, summary="Cotação de um ativo")
async def get_quote(ticker: str):
    """Retorna cotação ao vivo de um ativo (cache 5min). Ex: BOVA11, BTC, IVVB11."""
    result = await buscar_cotacao(ticker)
    if not result:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} não encontrado")
    return result
