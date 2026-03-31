"""
Router: FIRE Tracker — /api/v1/fire
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import FireInput, FireResult
from app.services.fire_service import calcular_fire
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/calculate", response_model=FireResult, summary="Calcular FIRE via Monte Carlo")
async def calculate_fire(payload: FireInput):
    """
    Motor principal FIRE:
    - Monte Carlo 10.000 simulações
    - Preços reais via yfinance (B3 + Cripto)
    - Kelly Criterion para Sharpe/Sortino
    - Projeção 3 cenários (otimista/base/estressado)

    Latência típica: 200–800ms dependendo do portfólio.
    """
    try:
        return await calcular_fire(payload)
    except Exception as e:
        logger.error(f"Erro FIRE: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios", summary="Cenários de projeção patrimonial")
async def get_scenarios(
    patrimonio: float = 50000,
    aporte: float = 2000,
    taxa: float = 0.12,
    anos: int = 20,
):
    from app.services.fire_service import gerar_cenarios
    return gerar_cenarios(patrimonio, aporte, taxa, anos)
