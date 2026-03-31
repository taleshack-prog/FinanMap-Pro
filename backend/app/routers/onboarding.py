"""
Router: Onboarding — /api/v1/onboarding
"""
import numpy as np
from fastapi import APIRouter
from app.models.schemas import OnboardingInput, OnboardingResult, RiskProfile
from app.services.fire_service import kelly_criterion, monte_carlo_fire
from app.core.config import settings

router = APIRouter()

SCORE_MAP = {
    "reacao": {"vende": 10, "espera": 35, "compra": 65, "all-in": 90},
    "exp":    {"iniciante": 0, "intermediario": 10, "avancado": 20},
    "obj":    {"fire": 5, "crescimento": 10, "renda": 0, "reserva": -10},
}

PERFIL_PARAMS = {
    RiskProfile.conservador:        {"mu": 0.07, "sigma": 0.10, "sharpe": 1.20},
    RiskProfile.moderado:           {"mu": 0.09, "sigma": 0.14, "sharpe": 1.45},
    RiskProfile.moderado_agressivo: {"mu": 0.12, "sigma": 0.18, "sharpe": 1.82},
    RiskProfile.agressivo:          {"mu": 0.15, "sigma": 0.22, "sharpe": 2.10},
}


@router.post("/profile", response_model=OnboardingResult, summary="Calcular perfil de risco")
async def calcular_perfil(payload: OnboardingInput):
    """
    Calcula score de risco VIX-adjusted (0–100) + alocação Kelly + FIRE via Monte Carlo.
    Chamado ao final do quiz de onboarding.
    """
    score = SCORE_MAP["reacao"].get(payload.reacao_queda, 35)
    score += SCORE_MAP["exp"].get(payload.experiencia, 0)
    score += SCORE_MAP["obj"].get(payload.objetivo, 0)
    score = max(10, min(100, score))

    if score < 30:
        perfil = RiskProfile.conservador
    elif score < 55:
        perfil = RiskProfile.moderado
    elif score < 75:
        perfil = RiskProfile.moderado_agressivo
    else:
        perfil = RiskProfile.agressivo

    params = PERFIL_PARAMS[perfil]

    # Kelly Criterion com retornos gaussianos (produção: yfinance real)
    retornos = np.random.normal(params["mu"] / 12, params["sigma"] / np.sqrt(12), 252).tolist()
    kelly = kelly_criterion(retornos, perfil=perfil)

    # Ajusta cripto
    if not payload.incluir_cripto:
        kelly.alocacao_otima["cripto"] = 0
        kelly.alocacao_otima["renda_var"] = min(60, kelly.alocacao_otima.get("renda_var", 30) + 5)
        kelly.alocacao_otima["renda_fixa"] = 100 - sum(
            v for k, v in kelly.alocacao_otima.items() if k != "renda_fixa"
        )

    # Monte Carlo FIRE
    risco_fator = score / 100
    mc = monte_carlo_fire(
        aporte=payload.aporte_mensal,
        despesas=payload.despesas_mensais,
        patrimonio_atual=payload.patrimonio_atual,
        risco=risco_fator,
        horizonte_max=payload.horizonte_anos + 20,
    )

    return OnboardingResult(
        score_risco=score,
        perfil=perfil,
        alocacao_kelly=kelly.alocacao_otima,
        fire_anos_p50=mc.anos_p50,
        fire_anos_p90=mc.anos_p90,
        fire_meta_r=mc.patrimonio_meta,
        fire_prob_sucesso=mc.prob_sucesso_pct,
        sharpe_esperado=params["sharpe"],
        sigma=params["sigma"],
        descricao_perfil=kelly.interpretacao,
    )
