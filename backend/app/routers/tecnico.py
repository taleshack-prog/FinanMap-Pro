"""
Router: Análise Técnica + VaR — /api/v1/tecnico
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.services.technical_service import (
    analisar_ativo, calcular_risco_portfolio, stress_test_expandido
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class AnaliseAtivoInput(BaseModel):
    ticker:  str
    precos:  List[float]
    volumes: Optional[List[float]] = None

class RiscoPortfolioInput(BaseModel):
    retornos_ativos: Dict[str, List[float]]
    pesos:           Dict[str, float]
    patrimonio:      float

class StressTestInput(BaseModel):
    alocacao:   Dict[str, float]
    patrimonio: float

@router.post("/ativo", summary="RSI + MACD + Bollinger + sinal unificado")
async def analise_tecnica(payload: AnaliseAtivoInput):
    try:
        r = analisar_ativo(payload.ticker, payload.precos, payload.volumes)
        return {"ticker":r.ticker,"preco_atual":r.preco_atual,"rsi":r.rsi,
                "macd":r.macd,"macd_signal":r.macd_signal,"macd_hist":r.macd_hist,
                "bollinger":{"upper":r.bb_upper,"middle":r.bb_middle,"lower":r.bb_lower,"posicao":r.bb_posicao},
                "medias":{"sma_20":r.sma_20,"sma_50":r.sma_50,"ema_9":r.ema_9},
                "volume_ratio":r.volume_ratio,"tendencia":r.tendencia,
                "sinal":r.sinal,"forca_sinal":r.forca_sinal,"score":r.score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risco", summary="VaR 95%/99% + CVaR + Sharpe + Sortino + Calmar")
async def risco_portfolio(payload: RiscoPortfolioInput):
    try:
        r = await calcular_risco_portfolio(payload.retornos_ativos, payload.pesos, payload.patrimonio)
        return {"var_95_pct":r.var_95,"var_99_pct":r.var_99,"cvar_95_pct":r.cvar_95,
                "cvar_99_pct":r.cvar_99,"var_portfolio_95_brl":r.var_portfolio_95,
                "volatilidade_anual":r.volatilidade_anual,"beta":r.beta,
                "max_drawdown":r.max_drawdown,"sharpe":r.sharpe,
                "sortino":r.sortino,"calmar":r.calmar}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stress", summary="Stress test com 6 cenários históricos")
async def stress_test(payload: StressTestInput):
    try:
        return stress_test_expandido(payload.alocacao, payload.patrimonio)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
