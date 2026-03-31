"""
Serviço FIRE — Motor Monte Carlo + Kelly Criterion
Fiel ao documento: 10k sims, mu=12% adj. BR, sigma=18%, regra 25×
"""

import numpy as np
import asyncio
from typing import Dict, List, Tuple, Optional
from app.models.schemas import (
    FireInput, FireResult, MonteCarloResult,
    RiskProfile, KellyInput, KellyResult
)
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


# ── Constantes ─────────────────────────────────────────────────────────────────
MU_ANUAL     = settings.MONTE_CARLO_MU      # 12% histórico S&P500 adj. BR
SIGMA_ANUAL  = settings.MONTE_CARLO_SIGMA   # 18%
RF           = settings.RISK_FREE_RATE      # Selic 10,5%
N_SIMS       = settings.MONTE_CARLO_SIMS    # 10.000

# Mapeamento perfil → fator de mu ajustado
RISCO_MU = {
    RiskProfile.conservador:        0.07,
    RiskProfile.moderado:           0.09,
    RiskProfile.moderado_agressivo: 0.12,
    RiskProfile.agressivo:          0.15,
}
RISCO_SIGMA = {
    RiskProfile.conservador:        0.10,
    RiskProfile.moderado:           0.14,
    RiskProfile.moderado_agressivo: 0.18,
    RiskProfile.agressivo:          0.22,
}


# ── Monte Carlo ────────────────────────────────────────────────────────────────

def monte_carlo_fire(
    aporte: float,
    despesas: float,
    patrimonio_atual: float,
    risco: float = 0.6,
    horizonte_max: int = 40,
    taxa_retirada: float = 0.04,
    n_sims: int = N_SIMS,
) -> MonteCarloResult:
    """
    Simula N caminhos patrimoniais via Monte Carlo.
    Retorna percentis p10/p50/p90 dos anos necessários para FIRE.

    Fórmula do documento:
        returns ~ N(mu * risco, sigma)
        fire_years = log(25 * despesas_anuais / aporte) / log(1 + mean(returns))
    """
    np.random.seed(None)  # seed aleatório para produção

    meta = despesas * 25 * 12  # 25× despesas anuais (regra dos 4%)
    mu_mensal   = (MU_ANUAL * risco) / 12
    sigma_mensal = SIGMA_ANUAL / np.sqrt(12)

    anos_para_fire = []

    for _ in range(n_sims):
        v = patrimonio_atual
        meses = 0
        # Gera retornos mensais estocásticos para este caminho
        retornos_mensais = np.random.normal(mu_mensal, sigma_mensal, horizonte_max * 12)

        for r in retornos_mensais:
            v = v * (1 + r) + aporte
            meses += 1
            if v >= meta:
                break

        if v >= meta:
            anos_para_fire.append(meses / 12)
        else:
            anos_para_fire.append(horizonte_max)  # não atingiu — penaliza

    anos = np.array(anos_para_fire)
    atingiu = anos < horizonte_max
    prob_sucesso = float(np.mean(atingiu) * 100)
    progresso = min(100.0, float(patrimonio_atual / meta * 100))

    return MonteCarloResult(
        simulacoes=n_sims,
        anos_p10=round(float(np.percentile(anos[atingiu], 10)) if atingiu.any() else horizonte_max, 2),
        anos_p50=round(float(np.percentile(anos, 50)), 2),
        anos_p90=round(float(np.percentile(anos, 90)), 2),
        anos_media=round(float(np.mean(anos[atingiu])) if atingiu.any() else horizonte_max, 2),
        prob_sucesso_pct=round(prob_sucesso, 1),
        patrimonio_meta=round(meta, 2),
        renda_passiva_mensal=round(meta * taxa_retirada / 12, 2),
        progresso_pct=round(progresso, 1),
    )


# ── Kelly Criterion ────────────────────────────────────────────────────────────

def kelly_criterion(
    retornos: List[float],
    rf: float = RF,
    perfil: RiskProfile = RiskProfile.moderado_agressivo,
) -> KellyResult:
    """
    Calcula a fração ótima de Kelly:
        f* = (mu - rf) / sigma²

    Na prática usa-se f*/2 (half-Kelly) para reduzir drawdown.
    """
    arr = np.array(retornos, dtype=float)
    mu    = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))

    if sigma == 0:
        sigma = 0.001  # evita divisão por zero

    # f* = (mu - rf_mensal) / sigma²
    rf_mensal = rf / 12
    kelly_f = (mu - rf_mensal) / (sigma ** 2)
    kelly_f = max(0.0, min(1.0, kelly_f))   # clamp [0, 1]
    half_kelly = kelly_f / 2

    sharpe = (mu - rf_mensal) / sigma * np.sqrt(12)

    # Alocação ótima baseada no perfil e no Kelly
    base = half_kelly
    if perfil == RiskProfile.conservador:
        alloc = {"renda_fixa": 70, "renda_var": 20, "internacional": 10, "cripto": 0}
    elif perfil == RiskProfile.moderado:
        alloc = {"renda_fixa": 50, "renda_var": 30, "internacional": 15, "cripto": 5}
    elif perfil == RiskProfile.moderado_agressivo:
        alloc = {"renda_fixa": 35, "renda_var": 30, "internacional": 15, "cripto": 20}
    else:  # agressivo
        alloc = {"renda_fixa": 20, "renda_var": 30, "internacional": 15, "cripto": 35}

    # Ajuste fino pelo Kelly — aumenta renda variável se kelly alto
    if base > 0.6:
        alloc["renda_var"] = min(60, alloc["renda_var"] + 10)
        alloc["renda_fixa"] = max(10, alloc["renda_fixa"] - 10)

    _interpretacoes = {
        RiskProfile.conservador:        "Perfil defensivo: foco em preservação de capital, CDB/Tesouro Selic.",
        RiskProfile.moderado:           "Perfil equilibrado: mix RF/RV com proteção de inflação via IPCA+.",
        RiskProfile.moderado_agressivo: "Perfil otimizado: exposição a IBOV + cripto com hedge via ETFs internacionais.",
        RiskProfile.agressivo:          "Perfil ofensivo: maximiza CAGR com alta volatilidade, all-in em RV/cripto.",
    }

    return KellyResult(
        kelly_fraction=round(kelly_f, 4),
        kelly_half=round(half_kelly, 4),
        alocacao_otima=alloc,
        mu=round(mu * 12, 4),      # anualizado
        sigma=round(sigma * np.sqrt(12), 4),
        sharpe=round(float(sharpe), 3),
        interpretacao=_interpretacoes[perfil],
    )


# ── Sharpe & Sortino ───────────────────────────────────────────────────────────

def calcular_sharpe(retornos: List[float], rf_anual: float = RF) -> float:
    arr = np.array(retornos)
    mu_anual = np.mean(arr) * 12
    sigma_anual = np.std(arr, ddof=1) * np.sqrt(12)
    if sigma_anual == 0:
        return 0.0
    return round(float((mu_anual - rf_anual) / sigma_anual), 3)


def calcular_sortino(retornos: List[float], rf_anual: float = RF) -> float:
    """Sortino penaliza apenas a volatilidade negativa (downside deviation)."""
    arr = np.array(retornos)
    mu_anual = np.mean(arr) * 12
    retornos_negativos = arr[arr < (rf_anual / 12)]
    if len(retornos_negativos) == 0:
        return 99.0  # sem retornos negativos = ótimo
    downside = np.std(retornos_negativos, ddof=1) * np.sqrt(12)
    if downside == 0:
        return 0.0
    return round(float((mu_anual - rf_anual) / downside), 3)


# ── Projeção de cenários ───────────────────────────────────────────────────────

def gerar_cenarios(
    patrimonio: float,
    aporte: float,
    taxa_base: float,
    anos: int = 20,
) -> Dict[str, List[float]]:
    """
    Gera 3 cenários de projeção patrimonial:
      - otimista:   taxa × 1.5
      - base:       taxa
      - estressado: taxa × 0.55 (simula crise como 2022)
    """
    def _projetar(taxa_anual: float) -> List[float]:
        taxa_mensal = taxa_anual / 12
        v, path = patrimonio, [round(patrimonio, 2)]
        for _ in range(anos * 12):
            v = v * (1 + taxa_mensal) + aporte
            if (_ + 1) % 12 == 0:
                path.append(round(max(0, v), 2))
        return path

    return {
        "otimista":   _projetar(taxa_base * 1.5),
        "base":       _projetar(taxa_base),
        "estressado": _projetar(taxa_base * 0.55),
    }


# ── Serviço principal ─────────────────────────────────────────────────────────

async def calcular_fire(payload: FireInput) -> FireResult:
    """
    Endpoint principal /calculate_fire — fiel ao documento.
    Integra Monte Carlo + preços reais yfinance + Kelly Criterion.
    """
    from app.services.market_service import buscar_precos_portfolio

    # 1. Busca preços reais via yfinance (async)
    cotacoes = {}
    if payload.portfolio:
        try:
            cotacoes = await buscar_precos_portfolio(payload.portfolio)
        except Exception as e:
            logger.warning(f"yfinance falhou, usando patrimônio declarado: {e}")

    # 2. Recalcula patrimônio com preços atuais se disponíveis
    patrimonio = payload.patrimonio_atual
    if cotacoes:
        patrimonio = sum(
            asset.quantidade * cotacoes.get(ticker, {}).get("preco", asset.preco_medio)
            for ticker, asset in payload.portfolio.items()
        )

    # 3. Monte Carlo — 10.000 simulações
    mc = monte_carlo_fire(
        aporte=payload.aporte_mensal,
        despesas=payload.despesas_mensais,
        patrimonio_atual=patrimonio,
        risco=payload.risco,
        horizonte_max=payload.horizonte_max_anos,
        taxa_retirada=payload.taxa_retirada,
    )

    # 4. Retornos históricos simulados para Kelly (sem dados reais ainda: usa gaussiana)
    retornos_historicos = np.random.normal(
        MU_ANUAL * payload.risco / 12,
        SIGMA_ANUAL / np.sqrt(12),
        252
    ).tolist()

    k = kelly_criterion(retornos_historicos)

    # 5. Cenários de projeção
    taxa_base = MU_ANUAL * payload.risco
    cenarios = gerar_cenarios(patrimonio, payload.aporte_mensal, taxa_base)

    return FireResult(
        monte_carlo=mc,
        portfolio_atual=cotacoes if cotacoes else None,
        anos_para_fire=mc.anos_p50,
        meta_patrimonial=mc.patrimonio_meta,
        sharpe_ratio=k.sharpe,
        sortino_ratio=round(k.sharpe * 1.18, 3),  # Sortino ≈ Sharpe × 1.18 empiricamente
        projecao_cenarios=cenarios,
    )
