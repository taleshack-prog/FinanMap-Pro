"""
FinanMap Pro — GA Service v2
Genoma: 7 genes (4 alocação + 3 estratégia)
Estratégias emergentes: swing_trade, arbitragem, rebalanceamento, dividend_capture, stop_dinamico
"""
import numpy as np
import asyncio
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from app.models.schemas import GAInput, GAResult, RiskProfile
from app.core.config import settings

logger = logging.getLogger(__name__)

GENES_ALLOC = ["renda_fixa", "renda_var", "internacional", "cripto"]
RETORNO_ESPERADO = {"renda_fixa": 0.105, "renda_var": 0.12, "internacional": 0.14, "cripto": 0.45}
VOLATILIDADE     = {"renda_fixa": 0.03,  "renda_var": 0.20, "internacional": 0.15, "cripto": 0.70}
RF = settings.RISK_FREE_RATE
HORIZONTE_MIN, HORIZONTE_MAX = 1, 180
RISCO_MIN,     RISCO_MAX     = 0.0, 1.0
STOP_MIN,      STOP_MAX      = -0.25, -0.02

class Estrategia(str, Enum):
    swing_trade      = "swing_trade"
    arbitragem       = "arbitragem"
    rebalanceamento  = "rebalanceamento"
    dividend_capture = "dividend_capture"
    stop_dinamico    = "stop_dinamico"

def classificar_estrategia(genes: Dict) -> Estrategia:
    h = genes.get("horizonte", 30)
    r = genes.get("tolerancia_risco", 0.5)
    s = abs(genes.get("stop_loss", -0.10))
    rv = genes.get("renda_var", 30)
    if h <= 7 and r >= 0.65 and s <= 0.06:   return Estrategia.arbitragem
    if h <= 30 and 0.4 <= r <= 0.85 and rv >= 35: return Estrategia.swing_trade
    if h >= 25 and r <= 0.55:                return Estrategia.rebalanceamento
    if 3 <= h <= 12 and s <= 0.12:           return Estrategia.dividend_capture
    return Estrategia.stop_dinamico

@dataclass
class Individuo:
    genes_alloc: Dict[str, float]
    horizonte: float = 30.0
    tolerancia_risco: float = 0.5
    stop_loss: float = -0.10
    fitness: float = 0.0
    estrategia: Optional[Estrategia] = None
    sortino: float = 0.0
    sharpe: float = 0.0
    cagr: float = 0.0

    def all_genes(self) -> Dict:
        return {**self.genes_alloc, "horizonte": self.horizonte,
                "tolerancia_risco": self.tolerancia_risco, "stop_loss": self.stop_loss}

    def normalizar_alloc(self) -> None:
        total = sum(max(0, v) for v in self.genes_alloc.values())
        if total > 0:
            self.genes_alloc = {k: round(max(0, v)/total*100, 2) for k, v in self.genes_alloc.items()}

    def clampar(self) -> None:
        self.horizonte        = float(np.clip(self.horizonte, HORIZONTE_MIN, HORIZONTE_MAX))
        self.tolerancia_risco = float(np.clip(self.tolerancia_risco, RISCO_MIN, RISCO_MAX))
        self.stop_loss        = float(np.clip(self.stop_loss, STOP_MIN, STOP_MAX))

def calcular_fitness_v2(ind: Individuo, bs_penalty: float = 0.5, n_sims: int = 800) -> float:
    g  = ind.genes_alloc
    h  = ind.horizonte
    s  = abs(ind.stop_loss)
    mu = sum((g.get(k,0)/100)*RETORNO_ESPERADO.get(k,0.08) for k in GENES_ALLOC)
    sig = math.sqrt(sum(((g.get(k,0)/100)**2)*(VOLATILIDADE.get(k,0.15)**2) for k in GENES_ALLOC)) or 0.001
    rets = np.random.normal(mu/12, sig/math.sqrt(12), n_sims)
    rf_m = RF/12
    neg  = rets[rets < rf_m]
    dd   = float(np.std(neg)*math.sqrt(12)) if len(neg)>=2 else 0.001
    sortino = (mu - RF)/dd if dd > 0 else 0
    # Penalidades
    pen_bs   = (bs_penalty if g.get("cripto",0)>40 else 0) + (bs_penalty*1.5 if g.get("cripto",0)>60 else 0)
    pen_conc = 0.30 if max(g.values(), default=0)>60 else 0
    # Bônus coerência
    bonus = 0.0
    if 8<=h<=30 and 0.06<=s<=0.14:    bonus += 0.15
    elif h<=7 and s<=0.06:            bonus += 0.20
    elif h>=30 and s>=0.10:           bonus += 0.10
    elif s<=0.04 and h>=30:           bonus -= 0.25
    # Bônus consistência
    bonus += 0.20 if float(np.mean(rets>rf_m))>=0.60 else 0
    total = max(0.0, sortino - pen_bs + bonus - pen_conc)
    ind.sortino    = round(sortino, 4)
    ind.sharpe     = round((mu-RF)/(sig*math.sqrt(12)), 4)
    ind.cagr       = round(mu*100, 2)
    ind.estrategia = classificar_estrategia(ind.all_genes())
    return round(total, 4)

def crossover_v2(p1: Individuo, p2: Individuo, cripto: bool=True) -> Tuple[Individuo, Individuo]:
    def mx(a, b): return a if np.random.random()<0.5 else b
    def alloc(pa, pb): return {k: (pa.genes_alloc.get(k,0) if np.random.random()<0.5 else pb.genes_alloc.get(k,0)) for k in GENES_ALLOC}
    g1, g2 = alloc(p1,p2), alloc(p1,p2)
    if not cripto: g1["cripto"]=g2["cripto"]=0
    f1=Individuo(genes_alloc=g1,horizonte=mx(p1.horizonte,p2.horizonte),tolerancia_risco=mx(p1.tolerancia_risco,p2.tolerancia_risco),stop_loss=mx(p1.stop_loss,p2.stop_loss))
    f2=Individuo(genes_alloc=g2,horizonte=mx(p1.horizonte,p2.horizonte),tolerancia_risco=mx(p1.tolerancia_risco,p2.tolerancia_risco),stop_loss=mx(p1.stop_loss,p2.stop_loss))
    f1.normalizar_alloc(); f1.clampar()
    f2.normalizar_alloc(); f2.clampar()
    return f1, f2

def mutacao_v2(ind: Individuo, taxa: float=0.15, cripto: bool=True) -> Individuo:
    new_a = {k: max(0, v+np.random.normal(0,8)) if np.random.random()<taxa else v for k,v in ind.genes_alloc.items()}
    if not cripto: new_a["cripto"]=0
    nh = ind.horizonte + (np.random.normal(0,15) if np.random.random()<taxa else 0)
    nr = ind.tolerancia_risco + (np.random.normal(0,0.12) if np.random.random()<taxa else 0)
    ns = ind.stop_loss + (np.random.normal(0,0.03) if np.random.random()<taxa else 0)
    m  = Individuo(genes_alloc=new_a, horizonte=nh, tolerancia_risco=nr, stop_loss=ns)
    m.normalizar_alloc(); m.clampar()
    return m

def selecao_torneio(pop: List[Individuo], k: int=3) -> Individuo:
    idx = np.random.choice(len(pop), min(k,len(pop)), replace=False)
    return max((pop[i] for i in idx), key=lambda x: x.fitness)

KELLY_SEEDS = {
    RiskProfile.conservador:        dict(genes_alloc={"renda_fixa":70,"renda_var":20,"internacional":10,"cripto":0}, horizonte=90, tolerancia_risco=0.25, stop_loss=-0.18),
    RiskProfile.moderado:           dict(genes_alloc={"renda_fixa":50,"renda_var":30,"internacional":15,"cripto":5}, horizonte=45, tolerancia_risco=0.45, stop_loss=-0.12),
    RiskProfile.moderado_agressivo: dict(genes_alloc={"renda_fixa":35,"renda_var":30,"internacional":15,"cripto":20}, horizonte=30, tolerancia_risco=0.60, stop_loss=-0.10),
    RiskProfile.agressivo:          dict(genes_alloc={"renda_fixa":20,"renda_var":30,"internacional":15,"cripto":35}, horizonte=12, tolerancia_risco=0.80, stop_loss=-0.07),
}

async def otimizar_portfolio(payload: GAInput) -> GAResult:
    def _run():
        np.random.seed(None)
        bs_pen = getattr(payload, 'black_swan_penalty', 0.5)
        seed   = KELLY_SEEDS[payload.perfil]
        pop: List[Individuo] = [Individuo(genes_alloc=dict(seed["genes_alloc"]),horizonte=seed["horizonte"],tolerancia_risco=seed["tolerancia_risco"],stop_loss=seed["stop_loss"])]
        for _ in range(payload.populacao-1):
            w = np.random.dirichlet(np.ones(len(GENES_ALLOC)))*100
            ga = {k: round(float(v),2) for k,v in zip(GENES_ALLOC,w)}
            if not payload.incluir_cripto: ga["cripto"]=0
            ind=Individuo(genes_alloc=ga,horizonte=float(np.random.uniform(1,180)),tolerancia_risco=float(np.random.uniform(0,1)),stop_loss=float(np.random.uniform(-0.25,-0.02)))
            ind.normalizar_alloc(); pop.append(ind)
        melhor_hist=0.0; sem_melhora=0
        for _ in range(payload.geracoes):
            for ind in pop: ind.fitness=calcular_fitness_v2(ind, bs_pen)
            pop.sort(key=lambda x: x.fitness, reverse=True)
            if pop[0].fitness > melhor_hist*1.005: melhor_hist=pop[0].fitness; sem_melhora=0
            else: sem_melhora+=1
            taxa=0.35 if sem_melhora>=10 else 0.15
            elite=pop[:max(2,payload.populacao//10)]
            nova=list(elite)
            while len(nova)<payload.populacao:
                p1=selecao_torneio(pop[:max(10,payload.populacao//4)])
                p2=selecao_torneio(pop[:max(10,payload.populacao//4)])
                f1,f2=crossover_v2(p1,p2,payload.incluir_cripto)
                nova+=[mutacao_v2(f1,taxa,payload.incluir_cripto),mutacao_v2(f2,taxa,payload.incluir_cripto)]
            pop=nova[:payload.populacao]
        best=max(pop,key=lambda x: x.fitness)
        best.fitness=calcular_fitness_v2(best,bs_pen)
        alloc_out={**best.genes_alloc,"horizonte_dias":round(best.horizonte,1),"tolerancia_risco":round(best.tolerancia_risco,3),"stop_loss_pct":round(best.stop_loss*100,2)}
        return GAResult(melhor_alocacao=alloc_out,cagr_projetado=best.cagr,sortino_ratio=round(best.fitness,3),geracoes_evoluidas=payload.geracoes,fitness_score=round(best.fitness,4),nova_strain=best.fitness>melhor_hist*1.05,descricao=f"Estratégia: {best.estrategia.value} · H={round(best.horizonte)}d · Stop={round(best.stop_loss*100,1)}% · CAGR={best.cagr}% · Sortino={round(best.fitness,3)}")
    return await asyncio.to_thread(_run)
