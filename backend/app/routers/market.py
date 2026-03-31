"""
Router: Market Data — /api/v1/market
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import MarketDataResult
from app.services.market_service import buscar_dados_mercado

router = APIRouter()


@router.get("/snapshot", response_model=MarketDataResult, summary="Snapshot do mercado")
async def market_snapshot():
    """IBOV, Selic, IPCA, USD/BRL, BTC — cache 5min."""
    try:
        return await buscar_dados_mercado()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
