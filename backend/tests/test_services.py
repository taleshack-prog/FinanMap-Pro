"""
Testes — cobertura alvo: 95% (conforme documento)
Execução: pytest tests/ -v --cov=app --cov-report=term-missing
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, patch, MagicMock

# ── FIRE Service ───────────────────────────────────────────────────────────────

from app.services.fire_service import (
    monte_carlo_fire,
    kelly_criterion,
    calcular_sharpe,
    calcular_sortino,
    gerar_cenarios,
)
from app.models.schemas import RiskProfile, FireInput, PortfolioAsset, AssetClass


class TestMonteCarlo:

    def test_resultado_basico(self):
        result = monte_carlo_fire(
            aporte=5000, despesas=2000, patrimonio_atual=50000, risco=0.6
        )
        assert result.simulacoes == 10_000
        assert result.anos_p50 > 0
        assert result.anos_p90 >= result.anos_p50
        assert 0 <= result.prob_sucesso_pct <= 100
        assert result.patrimonio_meta == pytest.approx(2000 * 25 * 12, rel=0.01)

    def test_meta_25x_despesas(self):
        """Regra do documento: meta = despesas × 25 × 12"""
        desp = 3000
        result = monte_carlo_fire(5000, desp, 0, 0.6)
        assert result.patrimonio_meta == pytest.approx(desp * 25 * 12, rel=0.001)

    def test_patrimonio_alto_reduz_anos(self):
        """Quem já tem patrimônio próximo da meta deve levar menos tempo"""
        r_baixo = monte_carlo_fire(3000, 2000, 10_000, 0.5)
        r_alto  = monte_carlo_fire(3000, 2000, 400_000, 0.5)
        assert r_alto.anos_p50 < r_baixo.anos_p50

    def test_aporte_maior_reduz_anos(self):
        r1 = monte_carlo_fire(2000, 2000, 50000, 0.6)
        r2 = monte_carlo_fire(10000, 2000, 50000, 0.6)
        assert r2.anos_p50 < r1.anos_p50

    def test_progresso_percentual(self):
        meta = 2000 * 25 * 12
        result = monte_carlo_fire(5000, 2000, meta / 2, 0.6)
        assert result.progresso_pct == pytest.approx(50, abs=1)

    def test_renda_passiva_regra_4pct(self):
        result = monte_carlo_fire(5000, 2000, 50000, 0.6)
        esperado = result.patrimonio_meta * 0.04 / 12
        assert result.renda_passiva_mensal == pytest.approx(esperado, rel=0.01)


class TestKellyCriterion:

    def _retornos(self, mu=0.01, sigma=0.05, n=252):
        np.random.seed(42)
        return np.random.normal(mu, sigma, n).tolist()

    def test_kelly_fraction_range(self):
        k = kelly_criterion(self._retornos(), perfil=RiskProfile.moderado_agressivo)
        assert 0 <= k.kelly_fraction <= 1
        assert 0 <= k.kelly_half <= 0.5

    def test_half_kelly_metade(self):
        k = kelly_criterion(self._retornos())
        assert k.kelly_half == pytest.approx(k.kelly_fraction / 2, rel=0.01)

    def test_alocacao_soma_100(self):
        k = kelly_criterion(self._retornos(), perfil=RiskProfile.moderado)
        total = sum(k.alocacao_otima.values())
        assert total == pytest.approx(100, abs=1)

    def test_conservador_mais_rf(self):
        k_cons = kelly_criterion(self._retornos(), perfil=RiskProfile.conservador)
        k_agr  = kelly_criterion(self._retornos(), perfil=RiskProfile.agressivo)
        assert k_cons.alocacao_otima["renda_fixa"] > k_agr.alocacao_otima["renda_fixa"]

    def test_agressivo_mais_cripto(self):
        k_cons = kelly_criterion(self._retornos(), perfil=RiskProfile.conservador)
        k_agr  = kelly_criterion(self._retornos(), perfil=RiskProfile.agressivo)
        assert k_agr.alocacao_otima.get("cripto", 0) > k_cons.alocacao_otima.get("cripto", 0)

    def test_sharpe_calculado(self):
        k = kelly_criterion(self._retornos(mu=0.015))
        assert k.sharpe > 0


class TestRatios:

    def test_sharpe_positivo_mu_alto(self):
        retornos = [0.02] * 100  # 2% ao mês = muito acima do RF
        s = calcular_sharpe(retornos)
        assert s > 1

    def test_sortino_maior_que_sharpe_poucos_negativos(self):
        np.random.seed(0)
        retornos = np.random.normal(0.02, 0.03, 200).tolist()
        sharpe  = calcular_sharpe(retornos)
        sortino = calcular_sortino(retornos)
        assert sortino >= sharpe  # Sortino ≥ Sharpe quando há poucos negativos

    def test_sharpe_zero_sem_excesso(self):
        # Retorno = RF/12 exatamente → Sharpe ≈ 0
        rf_mensal = 0.105 / 12
        retornos = [rf_mensal] * 100
        s = calcular_sharpe(retornos)
        assert abs(s) < 0.5


class TestCenarios:

    def test_tres_cenarios_retornados(self):
        c = gerar_cenarios(100000, 3000, 0.12, 20)
        assert set(c.keys()) == {"otimista", "base", "estressado"}

    def test_otimista_maior_que_base(self):
        c = gerar_cenarios(50000, 2000, 0.12, 10)
        assert c["otimista"][-1] > c["base"][-1]

    def test_base_maior_que_estressado(self):
        c = gerar_cenarios(50000, 2000, 0.12, 10)
        assert c["base"][-1] > c["estressado"][-1]

    def test_tamanho_correto(self):
        c = gerar_cenarios(50000, 2000, 0.12, 15)
        assert len(c["base"]) == 16  # ano 0 + 15 anos


# ── GA Service ────────────────────────────────────────────────────────────────

from app.services.ga_service import (
    Individuo, calcular_fitness, crossover, mutacao, selecao_torneio
)


class TestGeneticAlgorithm:

    def _ind(self, genes=None):
        if genes is None:
            genes = {"renda_fixa": 40, "renda_var": 30, "internacional": 15, "cripto": 15}
        ind = Individuo(genes=genes)
        ind.normalizar()
        return ind

    def test_normalizacao_soma_100(self):
        ind = self._ind({"renda_fixa": 60, "renda_var": 60, "internacional": 30, "cripto": 10})
        assert sum(ind.genes.values()) == pytest.approx(100, rel=0.01)

    def test_fitness_nao_negativo(self):
        ind = self._ind()
        f = calcular_fitness(ind, 100000, 3000)
        assert f >= 0

    def test_fitness_crash_cripto_penaliza(self):
        all_cripto = self._ind({"renda_fixa": 0, "renda_var": 0, "internacional": 0, "cripto": 100})
        diversified = self._ind({"renda_fixa": 40, "renda_var": 30, "internacional": 20, "cripto": 10})
        f_cripto = calcular_fitness(all_cripto, 100000, 3000)
        f_div    = calcular_fitness(diversified, 100000, 3000)
        assert f_div > f_cripto  # diversificado deve ter fitness maior

    def test_crossover_filhos_somam_100(self):
        p1 = self._ind()
        p2 = self._ind({"renda_fixa": 20, "renda_var": 50, "internacional": 20, "cripto": 10})
        f1, f2 = crossover(p1, p2, True)
        assert sum(f1.genes.values()) == pytest.approx(100, rel=0.01)
        assert sum(f2.genes.values()) == pytest.approx(100, rel=0.01)

    def test_mutacao_sem_negativos(self):
        ind = self._ind()
        for _ in range(20):
            m = mutacao(ind, taxa=0.9)
            for v in m.genes.values():
                assert v >= 0

    def test_selecao_torneio_retorna_individuo(self):
        pop = [self._ind() for _ in range(10)]
        for ind in pop:
            ind.fitness = np.random.random()
        sel = selecao_torneio(pop)
        assert isinstance(sel, Individuo)


# ── Onboarding ────────────────────────────────────────────────────────────────

from app.models.schemas import OnboardingInput


class TestOnboarding:

    def _payload(self, reacao="espera", exp="intermediario", obj="fire", score_override=None):
        return OnboardingInput(
            objetivo=obj,
            reacao_queda=reacao,
            experiencia=exp,
            horizonte_anos=10,
            incluir_cripto=True,
            patrimonio_atual=50000,
            aporte_mensal=3000,
            despesas_mensais=5000,
        )

    @pytest.mark.asyncio
    async def test_perfil_conservador(self):
        from app.routers.onboarding import calcular_perfil
        p = self._payload(reacao="vende", exp="iniciante")
        result = await calcular_perfil(p)
        assert result.perfil == RiskProfile.conservador
        assert result.score_risco < 30

    @pytest.mark.asyncio
    async def test_perfil_agressivo(self):
        from app.routers.onboarding import calcular_perfil
        p = self._payload(reacao="all-in", exp="avancado", obj="crescimento")
        result = await calcular_perfil(p)
        assert result.perfil == RiskProfile.agressivo

    @pytest.mark.asyncio
    async def test_sem_cripto_zera_alocacao(self):
        from app.routers.onboarding import calcular_perfil
        p = self._payload()
        p.incluir_cripto = False
        result = await calcular_perfil(p)
        assert result.alocacao_kelly.get("cripto", 0) == 0

    @pytest.mark.asyncio
    async def test_fire_anos_positivo(self):
        from app.routers.onboarding import calcular_perfil
        result = await calcular_perfil(self._payload())
        assert result.fire_anos_p50 > 0
        assert result.fire_anos_p90 >= result.fire_anos_p50


# ── Stress Test ───────────────────────────────────────────────────────────────

from app.services.ia_service import calcular_stress_test


class TestStressTest:

    def _portfolio(self):
        return {
            "BTC": PortfolioAsset(ticker="BTC-USD", quantidade=0.5, preco_medio=500000, classe=AssetClass.cripto),
            "BOVA11": PortfolioAsset(ticker="BOVA11.SA", quantidade=200, preco_medio=128, classe=AssetClass.renda_var),
        }

    def test_crash_cripto_negativo(self):
        st = calcular_stress_test(self._portfolio(), 300000)
        assert st["crash_cripto_87pct"] < 0

    def test_cenario_base_positivo(self):
        st = calcular_stress_test(self._portfolio(), 300000)
        assert st["base_anual"] > 0

    def test_sem_cripto_sem_crash(self):
        portfolio_sem_cripto = {
            "BOVA11": PortfolioAsset(ticker="BOVA11.SA", quantidade=200, preco_medio=128, classe=AssetClass.renda_var),
        }
        st = calcular_stress_test(portfolio_sem_cripto, 25600)
        assert st["crash_cripto_87pct"] == 0
