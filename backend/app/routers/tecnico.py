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
        return r
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risco", summary="VaR 95%/99% + CVaR + Sharpe + Sortino + Calmar")
async def risco_portfolio(payload: RiscoPortfolioInput):
    try:
        r = calcular_risco_portfolio(payload.retornos_ativos, payload.pesos, payload.patrimonio)
        return r
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stress", summary="Stress test com 6 cenários históricos")
async def stress_test(payload: StressTestInput):
    try:
        return stress_test_expandido(payload.alocacao, payload.patrimonio)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
