"""
Schemas Pydantic — validação de entrada/saída de todos os endpoints
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Literal
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class RiskProfile(str, Enum):
    conservador       = "conservador"
    moderado          = "moderado"
    moderado_agressivo = "moderado_agressivo"
    agressivo         = "agressivo"

class AssetClass(str, Enum):
    renda_fixa   = "renda_fixa"
    renda_var    = "renda_var"
    cripto       = "cripto"
    internacional = "internacional"
    fii          = "fii"


# ── Onboarding ────────────────────────────────────────────────────────────────

class OnboardingInput(BaseModel):
    objetivo: Literal["fire", "crescimento", "renda", "reserva"]
    reacao_queda: Literal["vende", "espera", "compra", "all-in"]
    experiencia: Literal["iniciante", "intermediario", "avancado"]
    horizonte_anos: int = Field(..., ge=3, le=35)
    incluir_cripto: bool = True
    patrimonio_atual: float = Field(..., ge=0, description="R$")
    aporte_mensal: float = Field(..., ge=0, description="R$")
    despesas_mensais: float = Field(..., gt=0, description="R$")

class OnboardingResult(BaseModel):
    score_risco: int = Field(..., ge=0, le=100, description="Score VIX-adjusted 0-100")
    perfil: RiskProfile
    alocacao_kelly: Dict[str, float]     # ex: {"renda_fixa": 40, "renda_var": 30, ...}
    fire_anos_p50: float
    fire_anos_p90: float
    fire_meta_r: float
    fire_prob_sucesso: float
    sharpe_esperado: float
    sigma: float
    descricao_perfil: str


# ── FIRE Tracker ──────────────────────────────────────────────────────────────

class PortfolioAsset(BaseModel):
    ticker: str                          # "BOVA11.SA", "BTC-USD"
    quantidade: float
    preco_medio: float
    classe: AssetClass

class FireInput(BaseModel):
    aporte_mensal: float = Field(..., gt=0, description="R$")
    despesas_mensais: float = Field(..., gt=0, description="R$ — base IBGE inflacionado")
    patrimonio_atual: float = Field(0.0, ge=0)
    portfolio: Optional[Dict[str, PortfolioAsset]] = None
    risco: float = Field(0.6, ge=0.1, le=1.0, description="Fator de risco 0.1–1.0")
    horizonte_max_anos: int = Field(40, ge=1, le=60)
    taxa_retirada: float = Field(0.04, description="Regra dos 4% padrão")

class MonteCarloResult(BaseModel):
    simulacoes: int
    anos_p10: float
    anos_p50: float                      # mediana
    anos_p90: float
    anos_media: float
    prob_sucesso_pct: float
    patrimonio_meta: float
    renda_passiva_mensal: float          # meta × taxa_retirada / 12
    progresso_pct: float

class FireResult(BaseModel):
    monte_carlo: MonteCarloResult
    portfolio_atual: Optional[Dict[str, float]] = None   # preços yfinance ao vivo
    anos_para_fire: float
    meta_patrimonial: float
    sharpe_ratio: float
    sortino_ratio: float
    projecao_cenarios: Dict[str, List[float]]            # otimista/base/estressado


# ── Portfólio ─────────────────────────────────────────────────────────────────

class PortfolioInput(BaseModel):
    ativos: Dict[str, PortfolioAsset]

class AssetQuote(BaseModel):
    ticker: str
    preco_atual: float
    preco_abertura: float
    variacao_dia_pct: float
    variacao_12m_pct: float
    volume: Optional[int] = None
    dividendo_yield: Optional[float] = None
    fonte: str = "yfinance"
    latencia_ms: Optional[int] = None

class PortfolioResult(BaseModel):
    total_atual: float
    total_investido: float
    ganho_total: float
    ganho_pct: float
    sharpe_ratio: float
    volatilidade_anual: float
    beta: float
    dividendos_12m: float
    cotacoes: Dict[str, AssetQuote]
    alocacao_atual: Dict[str, float]     # classe → %
    drawdown_maximo: float


# ── Kelly Criterion ───────────────────────────────────────────────────────────

class KellyInput(BaseModel):
    retornos_historicos: List[float]     # retornos diários/mensais
    taxa_livre_risco: float = Field(0.105, description="Selic 10.5% a.a.")
    perfil: RiskProfile = RiskProfile.moderado_agressivo

class KellyResult(BaseModel):
    kelly_fraction: float                # f* = (mu - rf) / sigma²
    kelly_half: float                    # f*/2 (prática recomendada)
    alocacao_otima: Dict[str, float]
    mu: float
    sigma: float
    sharpe: float
    interpretacao: str


# ── Algoritmo Genético ────────────────────────────────────────────────────────

class GAInput(BaseModel):
    patrimonio: float
    aporte: float
    perfil: RiskProfile
    incluir_cripto: bool = True
    geracoes: int = Field(50, ge=10, le=200)
    populacao: int = Field(200, ge=50, le=500)

class GAResult(BaseModel):
    melhor_alocacao: Dict[str, float]
    cagr_projetado: float
    sortino_ratio: float
    geracoes_evoluidas: int
    fitness_score: float
    nova_strain: bool                    # true se melhorou >5% vs anterior
    descricao: str


# ── IA Advisor ────────────────────────────────────────────────────────────────

class IAAdvisorInput(BaseModel):
    perfil: RiskProfile
    aporte_mensal: float
    ativos: Dict[str, PortfolioAsset]
    patrimonio_total: float
    anos_para_fire: float
    score_risco: int

class IAAdvisorResult(BaseModel):
    analise: str                         # texto gerado pelo Claude
    alertas: List[str]
    oportunidades: List[str]
    recomendacoes_kelly: Dict[str, float]
    stress_test: Dict[str, float]        # cenário → impacto R$
    modelo_usado: str
    tokens_usados: int


# ── Market Data ───────────────────────────────────────────────────────────────

class MarketDataResult(BaseModel):
    ibov: float
    selic: float
    ipca_12m: float
    dolar: float
    btc_brl: float
    ultima_atualizacao: str
    fonte: str = "yfinance + B3"
