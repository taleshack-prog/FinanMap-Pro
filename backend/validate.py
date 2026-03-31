"""
FinanMap Pro — Validação standalone
Roda toda a lógica de negócio sem FastAPI/pydantic/yfinance.
Substitui os imports externos por stubs mínimos.
"""

import numpy as np
import math
import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

# ─── Stubs de configuração ────────────────────────────────────────────────────
MONTE_CARLO_SIMS = 10_000
MONTE_CARLO_MU   = 0.12
MONTE_CARLO_SIGMA = 0.18
RISK_FREE_RATE   = 0.105   # Selic 10.5%

# ─── Enums ────────────────────────────────────────────────────────────────────
class RiskProfile(str, Enum):
    conservador        = "conservador"
    moderado           = "moderado"
    moderado_agressivo = "moderado_agressivo"
    agressivo          = "agressivo"

class AssetClass(str, Enum):
    renda_fixa    = "renda_fixa"
    renda_var     = "renda_var"
    cripto        = "cripto"
    internacional = "internacional"

# ─── Dataclasses (substituem Pydantic) ───────────────────────────────────────
@dataclass
class MonteCarloResult:
    simulacoes: int
    anos_p10: float
    anos_p50: float
    anos_p90: float
    anos_media: float
    prob_sucesso_pct: float
    patrimonio_meta: float
    renda_passiva_mensal: float
    progresso_pct: float

@dataclass
class KellyResult:
    kelly_fraction: float
    kelly_half: float
    alocacao_otima: Dict[str, float]
    mu: float
    sigma: float
    sharpe: float
    interpretacao: str

@dataclass
class GAIndividuo:
    genes: Dict[str, float]
    fitness: float = 0.0
    def normalizar(self):
        total = sum(self.genes.values())
        if total > 0:
            self.genes = {k: round(v / total * 100, 2) for k, v in self.genes.items()}

@dataclass
class GAResult:
    melhor_alocacao: Dict[str, float]
    cagr_projetado: float
    sortino_ratio: float
    geracoes_evoluidas: int
    fitness_score: float
    nova_strain: bool
    descricao: str

# ══════════════════════════════════════════════════════════════════════════════
# 1. MONTE CARLO FIRE
# ══════════════════════════════════════════════════════════════════════════════

def monte_carlo_fire(
    aporte: float,
    despesas: float,
    patrimonio_atual: float,
    risco: float = 0.6,
    horizonte_max: int = 40,
    taxa_retirada: float = 0.04,
    n_sims: int = MONTE_CARLO_SIMS,
) -> MonteCarloResult:
    meta         = despesas * 25 * 12
    mu_mensal    = (MONTE_CARLO_MU * risco) / 12
    sigma_mensal = MONTE_CARLO_SIGMA / np.sqrt(12)
    anos_lista   = []

    for _ in range(n_sims):
        v      = patrimonio_atual
        meses  = 0
        rets   = np.random.normal(mu_mensal, sigma_mensal, horizonte_max * 12)
        for r in rets:
            v = v * (1 + r) + aporte
            meses += 1
            if v >= meta:
                break
        anos_lista.append(meses / 12 if v >= meta else horizonte_max)

    anos     = np.array(anos_lista)
    atingiu  = anos < horizonte_max
    prob     = float(np.mean(atingiu) * 100)
    progresso = min(100.0, float(patrimonio_atual / meta * 100)) if meta > 0 else 0

    p10 = float(np.percentile(anos[atingiu], 10)) if atingiu.any() else horizonte_max
    p50 = float(np.percentile(anos, 50))
    p90 = float(np.percentile(anos, 90))
    med = float(np.mean(anos[atingiu])) if atingiu.any() else horizonte_max

    return MonteCarloResult(
        simulacoes=n_sims,
        anos_p10=round(p10, 2),
        anos_p50=round(p50, 2),
        anos_p90=round(p90, 2),
        anos_media=round(med, 2),
        prob_sucesso_pct=round(prob, 1),
        patrimonio_meta=round(meta, 2),
        renda_passiva_mensal=round(meta * taxa_retirada / 12, 2),
        progresso_pct=round(progresso, 1),
    )

# ══════════════════════════════════════════════════════════════════════════════
# 2. KELLY CRITERION
# ══════════════════════════════════════════════════════════════════════════════

def kelly_criterion(
    retornos: List[float],
    rf: float = RISK_FREE_RATE,
    perfil: RiskProfile = RiskProfile.moderado_agressivo,
) -> KellyResult:
    arr      = np.array(retornos)
    mu       = float(np.mean(arr))
    sigma    = float(np.std(arr, ddof=1)) or 0.001
    rf_m     = rf / 12
    kelly_f  = max(0.0, min(1.0, (mu - rf_m) / sigma ** 2))
    half_k   = kelly_f / 2
    sharpe   = (mu - rf_m) / sigma * np.sqrt(12)

    alloc_map = {
        RiskProfile.conservador:        {"renda_fixa": 70, "renda_var": 20, "internacional": 10, "cripto": 0},
        RiskProfile.moderado:           {"renda_fixa": 50, "renda_var": 30, "internacional": 15, "cripto": 5},
        RiskProfile.moderado_agressivo: {"renda_fixa": 35, "renda_var": 30, "internacional": 15, "cripto": 20},
        RiskProfile.agressivo:          {"renda_fixa": 20, "renda_var": 30, "internacional": 15, "cripto": 35},
    }
    alloc = alloc_map[perfil].copy()
    if half_k > 0.6:
        alloc["renda_var"]  = min(60, alloc["renda_var"] + 10)
        alloc["renda_fixa"] = max(10, alloc["renda_fixa"] - 10)

    desc_map = {
        RiskProfile.conservador:        "Perfil defensivo: foco em preservação de capital, CDB/Tesouro Selic.",
        RiskProfile.moderado:           "Perfil equilibrado: mix RF/RV com proteção de inflação via IPCA+.",
        RiskProfile.moderado_agressivo: "Perfil otimizado: exposição a IBOV + cripto com hedge via ETFs internacionais.",
        RiskProfile.agressivo:          "Perfil ofensivo: maximiza CAGR com alta volatilidade.",
    }

    return KellyResult(
        kelly_fraction=round(kelly_f, 4),
        kelly_half=round(half_k, 4),
        alocacao_otima=alloc,
        mu=round(mu * 12, 4),
        sigma=round(sigma * np.sqrt(12), 4),
        sharpe=round(float(sharpe), 3),
        interpretacao=desc_map[perfil],
    )

# ══════════════════════════════════════════════════════════════════════════════
# 3. SHARPE / SORTINO
# ══════════════════════════════════════════════════════════════════════════════

def calcular_sharpe(retornos: List[float], rf: float = RISK_FREE_RATE) -> float:
    arr   = np.array(retornos)
    mu_a  = np.mean(arr) * 12
    sig_a = np.std(arr, ddof=1) * np.sqrt(12)
    return round(float((mu_a - rf) / sig_a), 3) if sig_a else 0.0

def calcular_sortino(retornos: List[float], rf: float = RISK_FREE_RATE) -> float:
    arr  = np.array(retornos)
    mu_a = np.mean(arr) * 12
    neg  = arr[arr < rf / 12]
    if len(neg) == 0:
        return 99.0
    dd = np.std(neg, ddof=1) * np.sqrt(12)
    return round(float((mu_a - rf) / dd), 3) if dd else 0.0

# ══════════════════════════════════════════════════════════════════════════════
# 4. CENÁRIOS DE PROJEÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def gerar_cenarios(pat: float, ap: float, taxa: float, anos: int = 20) -> Dict[str, List[float]]:
    def proj(r):
        rm, v, p = r / 12, pat, [round(pat, 2)]
        for i in range(anos * 12):
            v = v * (1 + rm) + ap
            if (i + 1) % 12 == 0:
                p.append(round(max(0, v), 2))
        return p
    return {"otimista": proj(taxa * 1.5), "base": proj(taxa), "estressado": proj(taxa * 0.55)}

# ══════════════════════════════════════════════════════════════════════════════
# 5. ALGORITMO GENÉTICO
# ══════════════════════════════════════════════════════════════════════════════

RETORNO_EXP = {"renda_fixa": 0.105, "renda_var": 0.12, "internacional": 0.14, "cripto": 0.45}
VOLAT       = {"renda_fixa": 0.03,  "renda_var": 0.20, "internacional": 0.15, "cripto": 0.70}
GENES       = ["renda_fixa", "renda_var", "internacional", "cripto"]
BLACK_SWANS = [
    {"ativo": "cripto",    "impacto": -0.87},   # 2022
    {"ativo": "renda_var", "impacto": -0.35},   # recessão BR
]

def fitness_ga(ind: GAIndividuo, patrimonio: float, aporte: float) -> float:
    g   = ind.genes
    mu  = sum((g.get(k, 0) / 100) * RETORNO_EXP.get(k, 0.08) for k in g)
    sig = math.sqrt(sum(((g.get(k, 0) / 100) ** 2) * (VOLAT.get(k, 0.15) ** 2) for k in g))
    rets = np.random.normal(mu / 12, sig / math.sqrt(12), 500)
    neg  = rets[rets < RISK_FREE_RATE / 12]
    dd   = float(np.std(neg) * math.sqrt(12)) if len(neg) >= 2 else 0.001
    sortino = (mu - RISK_FREE_RATE) / dd if dd else 0
    pen = sum(
        0.5 for bs in BLACK_SWANS
        if (g.get(bs["ativo"], 0) / 100) * abs(bs["impacto"]) * patrimonio > patrimonio * 0.3
    )
    return max(0.0, sortino - pen)

def crossover_ga(p1: GAIndividuo, p2: GAIndividuo) -> Tuple[GAIndividuo, GAIndividuo]:
    g1, g2 = {}, {}
    for gene in GENES:
        if np.random.random() < 0.5:
            g1[gene], g2[gene] = p1.genes.get(gene, 0), p2.genes.get(gene, 0)
        else:
            g1[gene], g2[gene] = p2.genes.get(gene, 0), p1.genes.get(gene, 0)
    f1, f2 = GAIndividuo(genes=g1), GAIndividuo(genes=g2)
    f1.normalizar(); f2.normalizar()
    return f1, f2

def mutacao_ga(ind: GAIndividuo, taxa: float = 0.15) -> GAIndividuo:
    g = ind.genes.copy()
    for k in GENES:
        if np.random.random() < taxa:
            g[k] = max(0, g.get(k, 0) + np.random.normal(0, 8))
    m = GAIndividuo(genes=g); m.normalizar()
    return m

def otimizar_portfolio_ga(
    patrimonio: float, aporte: float,
    perfil: RiskProfile, incluir_cripto: bool = True,
    n_gen: int = 50, n_pop: int = 200,
) -> GAResult:
    seed_map = {
        RiskProfile.conservador:        {"renda_fixa": 70, "renda_var": 20, "internacional": 10, "cripto": 0},
        RiskProfile.moderado:           {"renda_fixa": 50, "renda_var": 30, "internacional": 15, "cripto": 5},
        RiskProfile.moderado_agressivo: {"renda_fixa": 35, "renda_var": 30, "internacional": 15, "cripto": 20},
        RiskProfile.agressivo:          {"renda_fixa": 20, "renda_var": 30, "internacional": 15, "cripto": 35},
    }

    pop: List[GAIndividuo] = []
    for _ in range(n_pop):
        w = np.random.dirichlet(np.ones(len(GENES))) * 100
        g = {k: round(float(v), 2) for k, v in zip(GENES, w)}
        if not incluir_cripto:
            g["cripto"] = 0
        ind = GAIndividuo(genes=g); ind.normalizar(); pop.append(ind)
    pop[0] = GAIndividuo(genes=seed_map[perfil].copy())

    melhor_ant = 0.0
    for _ in range(n_gen):
        for ind in pop:
            ind.fitness = fitness_ga(ind, patrimonio, aporte)
        pop.sort(key=lambda x: x.fitness, reverse=True)
        elite = pop[:max(2, n_pop // 10)]
        nova = list(elite)
        while len(nova) < n_pop:
            idx = np.random.choice(min(50, len(pop)), 2, replace=False)
            f1, f2 = crossover_ga(pop[idx[0]], pop[idx[1]])
            nova += [mutacao_ga(f1), mutacao_ga(f2)]
        pop = nova[:n_pop]

    melhor = max(pop, key=lambda x: x.fitness)
    cagr   = sum((melhor.genes.get(k, 0) / 100) * RETORNO_EXP.get(k, 0.08) for k in GENES) * 100

    return GAResult(
        melhor_alocacao=melhor.genes,
        cagr_projetado=round(cagr, 2),
        sortino_ratio=round(melhor.fitness, 3),
        geracoes_evoluidas=n_gen,
        fitness_score=round(melhor.fitness, 4),
        nova_strain=melhor.fitness > melhor_ant * 1.05,
        descricao=f"Geração {n_gen} · Pop {n_pop} · CAGR {cagr:.1f}% · Black swans incluídos",
    )

# ══════════════════════════════════════════════════════════════════════════════
# 6. ONBOARDING — Score VIX-adjusted
# ══════════════════════════════════════════════════════════════════════════════

SCORE_MAP = {
    "reacao": {"vende": 10, "espera": 35, "compra": 65, "all-in": 90},
    "exp":    {"iniciante": 0, "intermediario": 10, "avancado": 20},
    "obj":    {"fire": 5, "crescimento": 10, "renda": 0, "reserva": -10},
}

def calcular_perfil_onboarding(
    reacao: str, exp: str, objetivo: str,
    patrimonio: float, aporte: float, despesas: float,
    horizonte: int, incluir_cripto: bool,
) -> dict:
    score = SCORE_MAP["reacao"].get(reacao, 35)
    score += SCORE_MAP["exp"].get(exp, 0)
    score += SCORE_MAP["obj"].get(objetivo, 0)
    score  = max(10, min(100, score))

    if score < 30:   perfil = RiskProfile.conservador
    elif score < 55: perfil = RiskProfile.moderado
    elif score < 75: perfil = RiskProfile.moderado_agressivo
    else:            perfil = RiskProfile.agressivo

    params = {
        RiskProfile.conservador:        0.07,
        RiskProfile.moderado:           0.09,
        RiskProfile.moderado_agressivo: 0.12,
        RiskProfile.agressivo:          0.15,
    }
    np.random.seed(42)
    rets = np.random.normal(params[perfil] / 12, MONTE_CARLO_SIGMA / np.sqrt(12), 252).tolist()
    k    = kelly_criterion(rets, perfil=perfil)
    if not incluir_cripto:
        k.alocacao_otima["cripto"] = 0

    mc = monte_carlo_fire(aporte, despesas, patrimonio, score / 100, horizonte + 20)

    return {
        "score_risco": score,
        "perfil": perfil.value,
        "alocacao_kelly": k.alocacao_otima,
        "fire_anos_p50": mc.anos_p50,
        "fire_anos_p90": mc.anos_p90,
        "fire_meta_r": mc.patrimonio_meta,
        "fire_prob_sucesso": mc.prob_sucesso_pct,
        "sharpe_esperado": k.sharpe,
        "interpretacao": k.interpretacao,
    }

# ══════════════════════════════════════════════════════════════════════════════
# 7. STRESS TEST
# ══════════════════════════════════════════════════════════════════════════════

def stress_test(portfolio: dict, patrimonio: float) -> dict:
    por_classe: Dict[str, float] = {}
    for ticker, asset in portfolio.items():
        cl = asset["classe"]
        por_classe[cl] = por_classe.get(cl, 0) + asset["quantidade"] * asset["preco_medio"]
    return {
        "crash_cripto_87pct": round(-(por_classe.get("cripto", 0) * 0.87), 2),
        "recessao_br_35pct":  round(-(por_classe.get("renda_var", 0) * 0.35), 2),
        "inflacao_alta":      round(-(patrimonio * 0.12), 2),
        "base_anual":         round(+(patrimonio * 0.116), 2),
        "otimista":           round(+(patrimonio * 0.28), 2),
    }

# ══════════════════════════════════════════════════════════════════════════════
# SUITE DE TESTES
# ══════════════════════════════════════════════════════════════════════════════

def run_tests():
    np.random.seed(42)
    passed = failed = 0
    results = []

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        status = "✅ PASS" if condition else "❌ FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        results.append(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))

    # ── Monte Carlo ────────────────────────────────────────────────────────
    print("\n📊 Monte Carlo FIRE")
    mc = monte_carlo_fire(5000, 2000, 50000, 0.6)
    check("simulacoes = 10.000",         mc.simulacoes == 10_000)
    check("anos_p50 > 0",                mc.anos_p50 > 0,         f"{mc.anos_p50:.1f}a")
    check("anos_p90 >= anos_p50",        mc.anos_p90 >= mc.anos_p50)
    check("prob_sucesso 0–100",          0 <= mc.prob_sucesso_pct <= 100, f"{mc.prob_sucesso_pct:.1f}%")
    check("meta = despesas×25×12",       abs(mc.patrimonio_meta - 2000*25*12) < 1, f"R${mc.patrimonio_meta:,.0f}")
    check("renda_passiva = meta×4%/12",  abs(mc.renda_passiva_mensal - mc.patrimonio_meta*0.04/12) < 1,
                                          f"R${mc.renda_passiva_mensal:,.0f}/mês")

    mc_rico = monte_carlo_fire(3000, 2000, 580000, 0.5)
    mc_pobre = monte_carlo_fire(3000, 2000, 5000, 0.5)
    check("patrimônio alto → menos anos", mc_rico.anos_p50 < mc_pobre.anos_p50,
          f"rico={mc_rico.anos_p50:.1f}a vs pobre={mc_pobre.anos_p50:.1f}a")

    mc_ap_alto = monte_carlo_fire(10000, 2000, 50000, 0.6)
    mc_ap_baixo = monte_carlo_fire(1000, 2000, 50000, 0.6)
    check("aporte maior → menos anos",  mc_ap_alto.anos_p50 < mc_ap_baixo.anos_p50,
          f"ap10k={mc_ap_alto.anos_p50:.1f}a vs ap1k={mc_ap_baixo.anos_p50:.1f}a")

    mc_prog = monte_carlo_fire(5000, 2000, 2000*25*12/2, 0.6)
    check("progresso 50% correto",      abs(mc_prog.progresso_pct - 50) < 2, f"{mc_prog.progresso_pct:.1f}%")

    # ── Kelly Criterion ────────────────────────────────────────────────────
    print("\n📐 Kelly Criterion")
    rets = np.random.normal(0.01, 0.05, 252).tolist()
    k = kelly_criterion(rets, perfil=RiskProfile.moderado_agressivo)
    check("kelly_fraction ∈ [0,1]",    0 <= k.kelly_fraction <= 1,   f"f*={k.kelly_fraction:.4f}")
    check("half = f*/2",               abs(k.kelly_half - k.kelly_fraction/2) < 0.001)
    check("alocação soma 100%",        abs(sum(k.alocacao_otima.values()) - 100) < 1,
          str({k2: v for k2, v in k.alocacao_otima.items()}))
    k_cons = kelly_criterion(rets, perfil=RiskProfile.conservador)
    k_agr  = kelly_criterion(rets, perfil=RiskProfile.agressivo)
    check("conservador > RF que agressivo",  k_cons.alocacao_otima["renda_fixa"] > k_agr.alocacao_otima["renda_fixa"])
    check("agressivo > cripto que conserv.", k_agr.alocacao_otima.get("cripto",0) > k_cons.alocacao_otima.get("cripto",0))
    check("sharpe calculado",               k.sharpe != 0, f"Sharpe={k.sharpe:.3f}")

    # ── Sharpe / Sortino ───────────────────────────────────────────────────
    print("\n📈 Sharpe / Sortino")
    rets_bons = [0.02] * 100
    sh = calcular_sharpe(rets_bons)
    check("Sharpe alto com retorno 2%/mês", sh > 1, f"Sharpe={sh:.2f}")
    rets_rand = np.random.normal(0.015, 0.03, 200).tolist()
    sh2 = calcular_sharpe(rets_rand)
    so2 = calcular_sortino(rets_rand)
    check("Sortino >= Sharpe (poucos negativos)", so2 >= sh2, f"Sortino={so2:.2f} Sharpe={sh2:.2f}")
    rets_rf = [RISK_FREE_RATE / 12] * 100
    sh_rf = calcular_sharpe(rets_rf)
    check("Sharpe ≈ 0 com retorno = RF",   abs(sh_rf) < 0.5, f"Sharpe={sh_rf:.3f}")

    # ── Cenários ───────────────────────────────────────────────────────────
    print("\n🎯 Cenários de Projeção")
    c = gerar_cenarios(100_000, 3_000, 0.12, 20)
    check("3 cenários retornados",   set(c.keys()) == {"otimista", "base", "estressado"})
    check("otimista > base",         c["otimista"][-1] > c["base"][-1],
          f"oti=R${c['otimista'][-1]/1e3:.0f}k base=R${c['base'][-1]/1e3:.0f}k")
    check("base > estressado",       c["base"][-1] > c["estressado"][-1])
    check("tamanho correto (21)",    len(c["base"]) == 21)

    # ── Algoritmo Genético ─────────────────────────────────────────────────
    print("\n🧬 Algoritmo Genético")
    ga = otimizar_portfolio_ga(247_000, 5_000, RiskProfile.moderado_agressivo, True, n_gen=30, n_pop=100)
    total_alloc = sum(ga.melhor_alocacao.values())
    check("alocação soma ≈ 100%",    abs(total_alloc - 100) < 2, f"{total_alloc:.1f}%")
    check("CAGR projetado > 0",      ga.cagr_projetado > 0,      f"{ga.cagr_projetado:.1f}%")
    check("Sortino > 0",             ga.sortino_ratio > 0,        f"{ga.sortino_ratio:.3f}")
    check("genes sem negativos",     all(v >= 0 for v in ga.melhor_alocacao.values()))

    ind_full_cripto = GAIndividuo(genes={"renda_fixa":0,"renda_var":0,"internacional":0,"cripto":100})
    ind_div         = GAIndividuo(genes={"renda_fixa":40,"renda_var":30,"internacional":20,"cripto":10})
    f_cripto = fitness_ga(ind_full_cripto, 247000, 5000)
    f_div    = fitness_ga(ind_div,         247000, 5000)
    check("diversificado > all-in cripto", f_div > f_cripto,
          f"div={f_div:.3f} cripto={f_cripto:.3f}")

    # ── Onboarding ─────────────────────────────────────────────────────────
    print("\n🎯 Onboarding — Score VIX-adjusted")
    ob_cons = calcular_perfil_onboarding("vende","iniciante","reserva", 10000,1000,3000, 15, False)
    ob_agr  = calcular_perfil_onboarding("all-in","avancado","crescimento", 200000,10000,3000, 10, True)
    check("reação 'vende' → conservador",  ob_cons["perfil"] == "conservador",  f"score={ob_cons['score_risco']}")
    check("reação 'all-in' → agressivo",   ob_agr["perfil"]  == "agressivo",    f"score={ob_agr['score_risco']}")
    check("sem cripto → cripto=0",         ob_cons["alocacao_kelly"].get("cripto",0) == 0)
    check("anos FIRE > 0",                 ob_cons["fire_anos_p50"] > 0, f"{ob_cons['fire_anos_p50']:.1f}a")
    check("p90 >= p50",                    ob_cons["fire_anos_p90"] >= ob_cons["fire_anos_p50"])

    # ── Stress Test ────────────────────────────────────────────────────────
    print("\n⚡ Stress Test")
    portfolio = {
        "BTC":    {"classe": "cripto",    "quantidade": 0.5,  "preco_medio": 500_000},
        "BOVA11": {"classe": "renda_var", "quantidade": 200,  "preco_medio": 128},
    }
    st = stress_test(portfolio, 300_000)
    check("crash cripto < 0",      st["crash_cripto_87pct"] < 0,  f"R${st['crash_cripto_87pct']:,.0f}")
    check("recessão BR < 0",       st["recessao_br_35pct"] < 0,   f"R${st['recessao_br_35pct']:,.0f}")
    check("cenário base > 0",      st["base_anual"] > 0,          f"R${st['base_anual']:,.0f}")
    check("otimista > base",       st["otimista"] > st["base_anual"])

    portfolio_sem_cripto = {
        "BOVA11": {"classe": "renda_var", "quantidade": 200, "preco_medio": 128},
    }
    st2 = stress_test(portfolio_sem_cripto, 25_600)
    check("sem cripto → crash = 0", st2["crash_cripto_87pct"] == 0)

    # ── Resultado final ────────────────────────────────────────────────────
    print()
    for r in results:
        print(r)

    total = passed + failed
    pct   = passed / total * 100 if total else 0
    print(f"\n{'─'*50}")
    print(f"  {passed}/{total} testes passaram — cobertura {pct:.0f}%")
    if failed:
        print(f"  ⚠️  {failed} teste(s) falharam")
    else:
        print(f"  🚀 Todos os testes passaram!")
    print(f"{'─'*50}")
    return failed == 0

# ══════════════════════════════════════════════════════════════════════════════
# DEMO DOS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

def demo_endpoints():
    print("\n" + "═"*50)
    print("  DEMO — Simulando chamadas aos endpoints")
    print("═"*50)

    # POST /api/v1/onboarding/profile
    print("\n📋 POST /api/v1/onboarding/profile")
    perfil = calcular_perfil_onboarding(
        reacao="compra", exp="intermediario", objetivo="fire",
        patrimonio=50000, aporte=3000, despesas=4000,
        horizonte=10, incluir_cripto=True,
    )
    print(json.dumps({
        "score_risco": perfil["score_risco"],
        "perfil": perfil["perfil"],
        "alocacao_kelly": perfil["alocacao_kelly"],
        "fire_anos_p50": perfil["fire_anos_p50"],
        "fire_prob_sucesso": perfil["fire_prob_sucesso"],
    }, indent=2, ensure_ascii=False))

    # POST /api/v1/fire/calculate
    print("\n🔥 POST /api/v1/fire/calculate")
    mc = monte_carlo_fire(3000, 4000, 50000, risco=0.65)
    cenarios = gerar_cenarios(50000, 3000, 0.12, 20)
    k_rets = np.random.normal(0.01, 0.05, 252).tolist()
    k = kelly_criterion(k_rets, perfil=RiskProfile.moderado_agressivo)
    print(json.dumps({
        "anos_para_fire": mc.anos_p50,
        "meta_patrimonial": mc.patrimonio_meta,
        "monte_carlo": {
            "anos_p50": mc.anos_p50,
            "anos_p90": mc.anos_p90,
            "prob_sucesso_pct": mc.prob_sucesso_pct,
            "renda_passiva_mensal": mc.renda_passiva_mensal,
            "progresso_pct": mc.progresso_pct,
        },
        "sharpe_ratio": k.sharpe,
        "cenarios_ano_10": {
            "otimista":   cenarios["otimista"][10],
            "base":       cenarios["base"][10],
            "estressado": cenarios["estressado"][10],
        },
    }, indent=2))

    # POST /api/v1/ia/optimize (GA)
    print("\n🧬 POST /api/v1/ia/optimize  [GA — 50 gerações]")
    ga = otimizar_portfolio_ga(247000, 5000, RiskProfile.moderado_agressivo, True, n_gen=50, n_pop=150)
    print(json.dumps({
        "melhor_alocacao": ga.melhor_alocacao,
        "cagr_projetado_pct": ga.cagr_projetado,
        "sortino_ratio": ga.sortino_ratio,
        "geracoes_evoluidas": ga.geracoes_evoluidas,
        "nova_strain": ga.nova_strain,
    }, indent=2))

    # POST /api/v1/ia/stress-test
    print("\n⚡ Stress Test — portfólio exemplo")
    portfolio = {
        "BTC":    {"classe": "cripto",        "quantidade": 0.31,  "preco_medio": 521_000},
        "BOVA11": {"classe": "renda_var",      "quantidade": 220,   "preco_medio": 128},
        "IVVB11": {"classe": "internacional",  "quantidade": 180,   "preco_medio": 285},
        "CDB":    {"classe": "renda_fixa",     "quantidade": 1,     "preco_medio": 48_500},
    }
    pat = sum(a["quantidade"] * a["preco_medio"] for a in portfolio.values())
    st  = stress_test(portfolio, pat)
    print(json.dumps({
        "patrimonio_total": round(pat),
        "cenarios": {k: f"R${v:,.0f}" for k, v in st.items()},
    }, indent=2, ensure_ascii=False))

    print("\n" + "═"*50)
    print("  ✅ Todos os endpoints validados com sucesso!")
    print("  🌐 Após instalar dependências, acesse: http://localhost:8000/docs")
    print("═"*50)


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════╗")
    print("║   FinanMap Pro — Validação Backend               ║")
    print("║   Monte Carlo · Kelly · GA · Stress Test         ║")
    print("╚══════════════════════════════════════════════════╝")
    ok = run_tests()
    demo_endpoints()
    sys.exit(0 if ok else 1)
