/**
 * FinanMap Pro — API Service
 * Consome o backend FastAPI em http://localhost:8000
 * Em produção: substituir BASE_URL pela URL do Render.com
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';

// ── Config ────────────────────────────────────────────────────────────────────
const BASE_URL = __DEV__
  ? 'http://localhost:8000/api/v1'       // dev: backend local
  : 'https://api.finanmap.pro/api/v1';   // prod: Render.com

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Interceptors ──────────────────────────────────────────────────────────────
api.interceptors.request.use(config => {
  console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  return config;
});

api.interceptors.response.use(
  (r: AxiosResponse) => r,
  error => {
    const msg = error.response?.data?.detail || error.message || 'Erro de rede';
    console.error(`[API Error] ${msg}`);
    return Promise.reject(new Error(msg));
  },
);

// ── Types ─────────────────────────────────────────────────────────────────────

export type RiskProfile = 'conservador' | 'moderado' | 'moderado_agressivo' | 'agressivo';
export type AssetClass  = 'renda_fixa' | 'renda_var' | 'cripto' | 'internacional' | 'fii';

export interface PortfolioAsset {
  ticker:      string;
  quantidade:  number;
  preco_medio: number;
  classe:      AssetClass;
}

export interface OnboardingInput {
  objetivo:          'fire' | 'crescimento' | 'renda' | 'reserva';
  reacao_queda:      'vende' | 'espera' | 'compra' | 'all-in';
  experiencia:       'iniciante' | 'intermediario' | 'avancado';
  horizonte_anos:    number;
  incluir_cripto:    boolean;
  patrimonio_atual:  number;
  aporte_mensal:     number;
  despesas_mensais:  number;
}

export interface OnboardingResult {
  score_risco:        number;
  perfil:             RiskProfile;
  alocacao_kelly:     Record<string, number>;
  fire_anos_p50:      number;
  fire_anos_p90:      number;
  fire_meta_r:        number;
  fire_prob_sucesso:  number;
  sharpe_esperado:    number;
  sigma:              number;
  descricao_perfil:   string;
}

export interface FireInput {
  aporte_mensal:      number;
  despesas_mensais:   number;
  patrimonio_atual:   number;
  portfolio?:         Record<string, PortfolioAsset>;
  risco?:             number;
  horizonte_max_anos?:number;
  taxa_retirada?:     number;
}

export interface FireResult {
  monte_carlo: {
    simulacoes:           number;
    anos_p10:             number;
    anos_p50:             number;
    anos_p90:             number;
    prob_sucesso_pct:     number;
    patrimonio_meta:      number;
    renda_passiva_mensal: number;
    progresso_pct:        number;
  };
  anos_para_fire:     number;
  meta_patrimonial:   number;
  sharpe_ratio:       number;
  sortino_ratio:      number;
  projecao_cenarios:  Record<string, number[]>;
}

export interface GAInput {
  patrimonio:      number;
  aporte:          number;
  perfil:          RiskProfile;
  incluir_cripto:  boolean;
  geracoes?:       number;
  populacao?:      number;
}

export interface GAResult {
  melhor_alocacao:    Record<string, number>;
  cagr_projetado:     number;
  sortino_ratio:      number;
  geracoes_evoluidas: number;
  fitness_score:      number;
  nova_strain:        boolean;
  descricao:          string;
}

export interface MarketData {
  ibov:               number;
  selic:              number;
  ipca_12m:           number;
  dolar:              number;
  btc_brl:            number;
  ultima_atualizacao: string;
}

// ── Endpoints ──────────────────────────────────────────────────────────────────

export const ApiService = {

  // Onboarding
  calcularPerfil: async (data: OnboardingInput): Promise<OnboardingResult> => {
    const r = await api.post<OnboardingResult>('/onboarding/profile', data);
    return r.data;
  },

  // FIRE
  calcularFire: async (data: FireInput): Promise<FireResult> => {
    const r = await api.post<FireResult>('/fire/calculate', data);
    return r.data;
  },

  getCenarios: async (pat: number, ap: number, taxa: number, anos: number) => {
    const r = await api.get('/fire/scenarios', { params: { patrimonio: pat, aporte: ap, taxa, anos } });
    return r.data;
  },

  // Portfólio
  analisarPortfolio: async (ativos: Record<string, PortfolioAsset>) => {
    const r = await api.post('/portfolio/analyze', { ativos });
    return r.data;
  },

  getCotacao: async (ticker: string) => {
    const r = await api.get(`/portfolio/quote/${ticker}`);
    return r.data;
  },

  // IA & GA
  otimizarGA: async (data: GAInput): Promise<GAResult> => {
    const r = await api.post<GAResult>('/ia/optimize', data);
    return r.data;
  },

  analisarIA: async (data: any) => {
    const r = await api.post('/ia/analyze', data);
    return r.data;
  },

  // Market
  getDadosMercado: async (): Promise<MarketData> => {
    const r = await api.get<MarketData>('/market/snapshot');
    return r.data;
  },
};

export default ApiService;
