"""
Router: IA Advisor — /api/v1/ia
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import IAAdvisorInput, IAAdvisorResult, GAInput, GAResult
from app.services.ia_service import analisar_portfolio
from app.services.ga_service import otimizar_portfolio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=IAAdvisorResult, summary="Análise IA do portfólio (Claude)")
async def ia_analyze(payload: IAAdvisorInput):
    """
    Gera análise personalizada via Claude API:
    - Few-shot prompting com contexto do usuário
    - Kelly Criterion aplicado ao portfólio real
    - Stress test (crash cripto, recessão BR, base)
    - Fallback rule-based se API indisponível
    """
    try:
        return await analisar_portfolio(payload)
    except Exception as e:
        logger.error(f"IA analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize", response_model=GAResult, summary="Otimização via Algoritmo Genético")
async def ga_optimize(payload: GAInput):
    """
    Algoritmo Genético (DEAP-inspired):
    - Population: 200 indivíduos
    - Fitness: Sortino Ratio pós-Monte Carlo
    - Black swans incluídos (crash -87% cripto 2022)
    - Retorna nova 'strain' se melhora >5% vs anterior
    """
    try:
        return await otimizar_portfolio(payload)
    except Exception as e:
        logger.error(f"GA optimize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
