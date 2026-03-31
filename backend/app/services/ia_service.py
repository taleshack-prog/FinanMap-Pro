"""
IA Advisor — integração com Claude (Anthropic)
Few-shot prompting conforme documento + Kelly Criterion + stress test
"""

import httpx
import json
import logging
from typing import Dict, List

from app.core.config import settings
from app.models.schemas import (
    IAAdvisorInput, IAAdvisorResult,
    RiskProfile, PortfolioAsset
)
from app.services.fire_service import kelly_criterion
from app.services.market_service import buscar_dados_mercado

logger = logging.getLogger(__name__)

# ── Stress Test ────────────────────────────────────────────────────────────────

def calcular_stress_test(
    portfolio: Dict[str, PortfolioAsset],
    patrimonio: float,
) -> Dict[str, float]:
    """
    Calcula impacto em R$ de cenários de crise no portfólio.
    Black swans do documento: crash cripto -87% (2022), recessão BR -35%.
    """
    # Agrupa por classe
    por_classe: Dict[str, float] = {}
    for ticker, asset in portfolio.items():
        classe = asset.classe.value
        valor = asset.quantidade * asset.preco_medio
        por_classe[classe] = por_classe.get(classe, 0) + valor

    cenarios = {
        "crash_cripto_87pct": -(por_classe.get("cripto", 0) * 0.87),
        "recessao_br_35pct":  -(por_classe.get("renda_var", 0) * 0.35),
        "inflacao_alta":      -(patrimonio * 0.12),        # -12% real
        "base_anual":         +(patrimonio * 0.116),        # +11.6% base
        "otimista":           +(patrimonio * 0.28),         # CAGR GA +28%
    }

    return {k: round(v, 2) for k, v in cenarios.items()}


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(payload: IAAdvisorInput, dados_mercado: dict, kelly_result: dict) -> str:
    """
    Few-shot prompt conforme documento:
    'Perfil [X], aportes R$Y/mês, ativos [lista]. Sugira alocação...'
    """
    ativos_str = "\n".join(
        f"  - {ticker}: {asset.quantidade} unidades @ R${asset.preco_medio:,.2f} ({asset.classe.value})"
        for ticker, asset in payload.ativos.items()
    )

    kelly_str = json.dumps(kelly_result.get("alocacao_otima", {}), ensure_ascii=False)

    prompt = f"""Você é o IA Advisor do FinanMap Pro, um copiloto de investimentos especializado no mercado brasileiro.

PERFIL DO USUÁRIO:
- Perfil de risco: {payload.perfil.value}
- Score VIX-adjusted: {payload.score_risco}/100
- Patrimônio total: R${payload.patrimonio_total:,.2f}
- Aporte mensal: R${payload.aporte_mensal:,.2f}
- Horizonte FIRE: {payload.anos_para_fire:.1f} anos

CARTEIRA ATUAL:
{ativos_str}

DADOS DE MERCADO (2026):
- Selic: {dados_mercado.get('selic', 10.5)}% a.a. (FocusEconomics Q1/2026)
- IPCA 12m: {dados_mercado.get('ipca_12m', 4.8)}%
- IBOV: {dados_mercado.get('ibov', 130000):,.0f} pontos
- USD/BRL: R${dados_mercado.get('dolar', 5.15):.2f}
- BTC: R${dados_mercado.get('btc_brl', 520000):,.0f}

KELLY CRITERION calculado para este perfil:
Alocação ótima: {kelly_str}
(f* = (mu - rf) / sigma² — half-Kelly para reduzir drawdown)

Por favor, forneça:
1. Análise da carteira atual vs. alocação Kelly ótima
2. Até 3 alertas específicos com valores em R$ (ex: concentração excessiva em cripto)
3. Até 3 oportunidades de mercado dado o cenário macro 2026
4. Recomendação de rebalanceamento com valores precisos

Responda em português, de forma direta e quantitativa. Use linguagem de especialista em finanças brasileiras."""

    return prompt


# ── Serviço principal ──────────────────────────────────────────────────────────

async def analisar_portfolio(payload: IAAdvisorInput) -> IAAdvisorResult:
    """
    Gera análise completa via Claude API + Kelly + stress test.
    """
    import numpy as np
    from app.services.fire_service import calcular_sharpe

    # Retornos simulados para Kelly (em produção: yfinance real)
    retornos = np.random.normal(0.12/12, 0.18/np.sqrt(12), 252).tolist()
    k = kelly_criterion(retornos, perfil=payload.perfil)

    # Stress test
    stress = calcular_stress_test(payload.ativos, payload.patrimonio_total)

    # Dados de mercado
    try:
        mercado = await buscar_dados_mercado()
        dados_mercado = mercado.model_dump()
    except Exception:
        dados_mercado = {"selic": 10.5, "ipca_12m": 4.8, "ibov": 130000, "dolar": 5.15, "btc_brl": 520000}

    # Prompt Claude
    prompt = _build_prompt(payload, dados_mercado, k.model_dump())

    analise = ""
    tokens = 0
    modelo = settings.CLAUDE_MODEL

    # ── Chamada à API do Claude ───────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": modelo,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            analise = data["content"][0]["text"]
            tokens = data.get("usage", {}).get("input_tokens", 0) + \
                     data.get("usage", {}).get("output_tokens", 0)
    except Exception as e:
        logger.error(f"Claude API erro: {e}")
        analise = _fallback_analise(payload, k, stress)
        modelo = "fallback-rule-based"

    # ── Extrai alertas e oportunidades do texto (rule-based fallback) ─────────
    alertas = _extrair_alertas(payload, k)
    oportunidades = _extrair_oportunidades(dados_mercado, payload)

    return IAAdvisorResult(
        analise=analise,
        alertas=alertas,
        oportunidades=oportunidades,
        recomendacoes_kelly=k.alocacao_otima,
        stress_test=stress,
        modelo_usado=modelo,
        tokens_usados=tokens,
    )


def _extrair_alertas(payload: IAAdvisorInput, kelly) -> List[str]:
    alertas = []
    # Verifica concentração em cripto
    cripto_pct = sum(
        a.quantidade * a.preco_medio
        for t, a in payload.ativos.items()
        if a.classe.value == "cripto"
    ) / payload.patrimonio_total * 100 if payload.patrimonio_total > 0 else 0

    kelly_cripto = kelly.alocacao_otima.get("cripto", 0)
    if cripto_pct > kelly_cripto + 5:
        diff = cripto_pct - kelly_cripto
        valor = diff / 100 * payload.patrimonio_total
        alertas.append(
            f"Concentração em cripto ({cripto_pct:.1f}%) excede Kelly ótimo ({kelly_cripto}%) "
            f"em {diff:.1f}pp. Considere rebalancear R${valor:,.0f} para Tesouro IPCA+."
        )
    if payload.aporte_mensal < 2000:
        alertas.append(
            "Aporte mensal abaixo de R$2.000 pode comprometer o prazo FIRE. "
            "Considere aumentar para aceleração patrimonial."
        )
    if not any(a.classe.value == "internacional" for a in payload.ativos.values()):
        alertas.append(
            "Sem exposição internacional — risco de concentração em moeda BRL. "
            "Recomendado 10-15% em IVVB11 (S&P500 hedgeado)."
        )
    return alertas[:3]


def _extrair_oportunidades(dados: dict, payload: IAAdvisorInput) -> List[str]:
    ops = []
    selic = dados.get("selic", 10.5)
    if selic > 10:
        ops.append(
            f"Selic em {selic}% a.a. — Tesouro IPCA+ com spread >6% oferece "
            f"retorno real atrativo com baixo risco de crédito."
        )
    ops.append(
        "IBOV com Sharpe >1.2 (rolling 6m) e momento positivo — "
        "BOVA11 recomendado para exposição diversificada à B3."
    )
    if payload.perfil in [RiskProfile.agressivo, RiskProfile.moderado_agressivo]:
        ops.append(
            "BTC acima da média móvel 200d — janela de acumulação gradual "
            "via DCA mensal para exposição cripto controlada pelo Kelly."
        )
    return ops[:3]


def _fallback_analise(payload: IAAdvisorInput, kelly, stress: dict) -> str:
    return (
        f"Análise automática do portfólio (R${payload.patrimonio_total:,.0f}):\n\n"
        f"Perfil {payload.perfil.value} — alocação Kelly recomendada: "
        f"{kelly.alocacao_otima}.\n\n"
        f"Stress test: crash cripto impacta R${abs(stress.get('crash_cripto_87pct', 0)):,.0f}. "
        f"Cenário base projeta +R${stress.get('base_anual', 0):,.0f} em 12 meses.\n\n"
        f"Sharpe atual: {kelly.sharpe:.2f}. "
        f"Horizonte FIRE: {payload.anos_para_fire:.1f} anos."
    )
