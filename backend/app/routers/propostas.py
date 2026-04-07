# backend/app/routers/propostas.py
# Sistema de propostas dos robôs — análise automática + retroalimentação

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging
import os
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
router = APIRouter(prefix="/api/v1/propostas", tags=["propostas"])
logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "propostas.json")

# ── Watchlist padrão (ativos a monitorar além do portfólio) ──────────────────
WATCHLIST_DEFAULT = [
    {"ticker": "BTC",   "tipo": "cripto",    "nome": "Bitcoin"},
    {"ticker": "ETH",   "tipo": "cripto",    "nome": "Ethereum"},
    {"ticker": "SOL",   "tipo": "cripto",    "nome": "Solana"},
    {"ticker": "BNB",   "tipo": "cripto",    "nome": "BNB"},
    {"ticker": "PETR4", "tipo": "acao_br",   "nome": "Petrobras"},
    {"ticker": "VALE3", "tipo": "acao_br",   "nome": "Vale"},
    {"ticker": "NVDA",  "tipo": "acao_eua",  "nome": "NVIDIA"},
    {"ticker": "BOVA11","tipo": "etf_br",    "nome": "ETF Ibovespa"},
]

# ── Persistência ──────────────────────────────────────────────────────────────

def carregar_dados() -> dict:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "propostas": [],
        "historico": [],
        "watchlist": WATCHLIST_DEFAULT,
        "scores_robos": {},
        "ultima_analise": None
    }

def salvar_dados(data: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

# ── Análise técnica de um ativo ───────────────────────────────────────────────

async def analisar_ativo_completo(ticker: str, tipo: str) -> Optional[dict]:
    """Busca preços reais e faz análise técnica completa."""
    try:
        import aiohttp
        precos = []
        nome_completo = ticker

        # Buscar preços
        if tipo == "cripto":
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                url = f"https://api.binance.com/api/v3/klines?symbol={ticker}USDT&interval=1d&limit=60"
                async with session.get(url) as r:
                    if r.status == 200:
                        klines = await r.json()
                        precos = [float(k[4]) for k in klines]
                        nome_completo = f"{ticker}/USDT"
        else:
            import yfinance as yf
            sufixo = ".SA" if tipo in ("acao_br", "etf_br", "fii", "bdr") else ""
            stock = yf.Ticker(ticker + sufixo)
            hist = stock.history(period="3mo")
            if not hist.empty:
                precos = hist["Close"].tolist()
                try:
                    info = stock.info or {}
                    nome_completo = info.get("longName") or info.get("shortName") or ticker
                except Exception:
                    pass

        if len(precos) < 14:
            return None

        # Análise técnica
        from app.services.technical_service import analisar_ativo
        tecnica = analisar_ativo(ticker, precos)

        preco_atual = precos[-1]
        var24h = ((precos[-1] - precos[-2]) / precos[-2] * 100) if len(precos) >= 2 else 0

        return {
            "ticker": ticker,
            "tipo": tipo,
            "nome_completo": nome_completo,
            "preco_atual": preco_atual,
            "variacao_24h": round(var24h, 2),
            "tecnica": tecnica,
            "precos": precos[-30:],  # últimos 30 para contexto
        }
    except Exception as e:
        logger.error(f"Erro ao analisar {ticker}: {e}")
        return None


def gerar_proposta(analise: dict, robo_id: str, robo_nome: str, patrimonio: float) -> Optional[dict]:
    """Gera proposta de investimento baseada na análise técnica."""
    t = analise.get("tecnica", {})
    sinal = t.get("sinal", "neutro")
    forca = t.get("forca_sinal", 0)
    score = t.get("score_100", 0)
    rsi = t.get("rsi", 50)
    bb = t.get("bollinger", {})
    preco = analise["preco_atual"]

    # Só gerar proposta com sinal forte o suficiente
    if forca < 0.3:
        return None
    if sinal == "neutro":
        return None

    # Calcular entrada e stop
    bb_lower = bb.get("lower", preco * 0.95)
    bb_upper = bb.get("upper", preco * 1.05)
    bb_mid = bb.get("middle", preco)

    if sinal == "compra":
        acao = "COMPRAR"
        entrada_sugerida = round(min(preco, bb_lower * 1.01), 6)
        stop_loss = round(bb_lower * 0.97, 6)
        alvo = round(bb_upper * 0.98, 6)
        risco_pct = round((entrada_sugerida - stop_loss) / entrada_sugerida * 100, 2)
        retorno_potencial = round((alvo - entrada_sugerida) / entrada_sugerida * 100, 2)
        cor = "green"
    else:
        acao = "VENDER / EVITAR"
        entrada_sugerida = round(max(preco, bb_upper * 0.99), 6)
        stop_loss = round(bb_upper * 1.03, 6)
        alvo = round(bb_lower * 1.02, 6)
        risco_pct = round((stop_loss - entrada_sugerida) / entrada_sugerida * 100, 2)
        retorno_potencial = round((entrada_sugerida - alvo) / entrada_sugerida * 100, 2)
        cor = "red"

    # Tamanho sugerido (Kelly simplificado)
    kelly = max(0.01, min(0.15, forca * 0.2))
    valor_sugerido = round(patrimonio * kelly, 2)

    # Justificativa
    justificativas = []
    if rsi < 30: justificativas.append(f"RSI {rsi:.0f} — oversold")
    if rsi > 70: justificativas.append(f"RSI {rsi:.0f} — overbought")
    if bb.get("posicao", 0.5) < 0.2: justificativas.append("Preço próximo ao suporte Bollinger")
    if bb.get("posicao", 0.5) > 0.8: justificativas.append("Preço próximo à resistência Bollinger")
    if t.get("tendencia") == "alta": justificativas.append("Tendência de alta confirmada")
    if t.get("tendencia") == "baixa": justificativas.append("Tendência de baixa confirmada")
    if t.get("zscore", 0) < -1.5: justificativas.append(f"Z-Score {t.get('zscore', 0):.2f} — desvio negativo extremo")
    if not justificativas:
        justificativas.append(f"Sinal técnico unificado: {sinal} ({forca*100:.0f}% força)")

    return {
        "id": f"prop_{robo_id}_{analise['ticker']}_{int(datetime.now().timestamp())}",
        "robo_id": robo_id,
        "robo_nome": robo_nome,
        "ticker": analise["ticker"],
        "tipo": analise["tipo"],
        "nome_completo": analise["nome_completo"],
        "acao": acao,
        "sinal": sinal,
        "forca": round(forca, 3),
        "score": score,
        "preco_atual": preco,
        "entrada_sugerida": entrada_sugerida,
        "stop_loss": stop_loss,
        "alvo": alvo,
        "risco_pct": risco_pct,
        "retorno_potencial": retorno_potencial,
        "valor_sugerido": valor_sugerido,
        "kelly_pct": round(kelly * 100, 1),
        "justificativa": " · ".join(justificativas),
        "rsi": rsi,
        "variacao_24h": analise["variacao_24h"],
        "cor": cor,
        "status": "pendente",  # pendente → executei / rejeitei
        "criada_em": datetime.now().isoformat(),
        "executada_em": None,
        "preco_execucao": None,
        "resultado": None,  # acertou / errou (calculado depois)
        "notas": "",
    }


# ── Análise automática ────────────────────────────────────────────────────────

async def rodar_analise_automatica(patrimonio: float = 2597.0) -> dict:
    """Roda análise completa em todos os ativos e gera propostas."""
    dados = carregar_dados()
    watchlist = dados.get("watchlist", WATCHLIST_DEFAULT)

    # Robôs simulados com estratégias diferentes
    ROBOS = [
        {"id": "alpha", "nome": "Alpha-RSI",    "estrategia": "momentum"},
        {"id": "beta",  "nome": "Beta-Bollinger","estrategia": "mean_reversion"},
        {"id": "gamma", "nome": "Gamma-Trend",  "estrategia": "trend_following"},
    ]

    novas_propostas = []
    analisados = 0
    erros = 0

    for ativo in watchlist:
        try:
            analise = await analisar_ativo_completo(ativo["ticker"], ativo["tipo"])
            if not analise:
                erros += 1
                continue

            analisados += 1

            # Cada robô pode gerar uma proposta diferente baseada na mesma análise
            for robo in ROBOS:
                # Verificar se já existe proposta pendente deste robô para este ativo
                ja_existe = any(
                    p["ticker"] == ativo["ticker"] and
                    p["robo_id"] == robo["id"] and
                    p["status"] == "pendente"
                    for p in dados["propostas"]
                )
                if ja_existe:
                    continue

                proposta = gerar_proposta(analise, robo["id"], robo["nome"], patrimonio)
                if proposta:
                    novas_propostas.append(proposta)

        except Exception as e:
            logger.error(f"Erro ao analisar {ativo['ticker']}: {e}")
            erros += 1

    # Guardar propostas novas
    dados["propostas"].extend(novas_propostas)
    # Manter apenas últimas 100 propostas pendentes
    pendentes = [p for p in dados["propostas"] if p["status"] == "pendente"]
    resolvidas = [p for p in dados["propostas"] if p["status"] != "pendente"]
    dados["propostas"] = pendentes[-50:] + resolvidas[-50:]
    dados["ultima_analise"] = datetime.now().isoformat()

    salvar_dados(dados)

    return {
        "analisados": analisados,
        "novas_propostas": len(novas_propostas),
        "erros": erros,
        "ultima_analise": dados["ultima_analise"],
    }


def calcular_resultado_proposta(proposta: dict) -> str:
    """Calcula se proposta foi acertada com base no preço actual."""
    if not proposta.get("preco_execucao"):
        return "sem_dados"
    entrada = proposta["preco_execucao"]
    atual = proposta.get("preco_atual_agora", entrada)
    sinal = proposta["sinal"]
    alvo = proposta["alvo"]
    stop = proposta["stop_loss"]

    if sinal == "compra":
        if atual >= alvo: return "acertou"
        if atual <= stop: return "errou"
        return "em_aberto"
    else:
        if atual <= alvo: return "acertou"
        if atual >= stop: return "errou"
        return "em_aberto"


def atualizar_score_robo(dados: dict, robo_id: str, acertou: bool):
    """Atualiza score do robô com base no resultado."""
    scores = dados.get("scores_robos", {})
    if robo_id not in scores:
        scores[robo_id] = {"acertos": 0, "erros": 0, "total": 0, "taxa_acerto": 0.5}

    scores[robo_id]["total"] += 1
    if acertou:
        scores[robo_id]["acertos"] += 1
    else:
        scores[robo_id]["erros"] += 1

    total = scores[robo_id]["total"]
    scores[robo_id]["taxa_acerto"] = round(scores[robo_id]["acertos"] / total, 3)

    dados["scores_robos"] = scores


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/")
async def listar_propostas(status: Optional[str] = None):
    """Lista todas as propostas (pendentes por defeito)."""
    dados = carregar_dados()
    propostas = dados.get("propostas", [])
    if status:
        propostas = [p for p in propostas if p["status"] == status]
    else:
        propostas = [p for p in propostas if p["status"] == "pendente"]
    # Ordenar por score decrescente
    propostas.sort(key=lambda p: p.get("score", 0), reverse=True)
    return {
        "propostas": propostas,
        "total": len(propostas),
        "ultima_analise": dados.get("ultima_analise"),
        "scores_robos": dados.get("scores_robos", {}),
    }


@router.post("/analisar")
async def analisar_agora(patrimonio: float = 2597.0):
    """Dispara análise imediata de todos os ativos."""
    resultado = await rodar_analise_automatica(patrimonio)
    return resultado


class FeedbackInput(BaseModel):
    proposta_id: str
    decisao: str          # "executei" ou "rejeitei"
    preco_execucao: Optional[float] = None
    notas: Optional[str] = ""


@router.post("/feedback")
async def registar_feedback(payload: FeedbackInput):
    """Regista decisão do utilizador sobre uma proposta."""
    dados = carregar_dados()
    proposta = next((p for p in dados["propostas"] if p["id"] == payload.proposta_id), None)
    if not proposta:
        raise HTTPException(404, "Proposta não encontrada")

    proposta["status"] = payload.decisao
    proposta["executada_em"] = datetime.now().isoformat()
    proposta["notas"] = payload.notas or ""

    if payload.decisao == "executei" and payload.preco_execucao:
        proposta["preco_execucao"] = payload.preco_execucao

    # Mover para histórico se rejeitada
    if payload.decisao == "rejeitei":
        dados["historico"].append(proposta)
        dados["propostas"] = [p for p in dados["propostas"] if p["id"] != payload.proposta_id]

    salvar_dados(dados)
    return {"ok": True, "proposta": proposta}


@router.post("/resultado/{proposta_id}")
async def registar_resultado(proposta_id: str, acertou: bool, preco_final: Optional[float] = None):
    """Regista resultado final de uma proposta executada (para aprendizagem)."""
    dados = carregar_dados()
    proposta = next((p for p in dados["propostas"] if p["id"] == proposta_id), None)
    if not proposta:
        # Procurar no histórico
        proposta = next((p for p in dados.get("historico", []) if p["id"] == proposta_id), None)
    if not proposta:
        raise HTTPException(404, "Proposta não encontrada")

    proposta["resultado"] = "acertou" if acertou else "errou"
    if preco_final:
        proposta["preco_atual_agora"] = preco_final

    # Atualizar score do robô
    atualizar_score_robo(dados, proposta["robo_id"], acertou)

    # Mover para histórico
    dados["historico"].append(proposta)
    dados["propostas"] = [p for p in dados["propostas"] if p["id"] != proposta_id]

    salvar_dados(dados)
    return {
        "ok": True,
        "score_atualizado": dados["scores_robos"].get(proposta["robo_id"])
    }


@router.get("/historico")
async def ver_historico(limite: int = 50):
    """Ver histórico de propostas com resultados."""
    dados = carregar_dados()
    historico = dados.get("historico", [])[-limite:]
    historico.reverse()

    # Estatísticas
    total = len(historico)
    executadas = [h for h in historico if h.get("status") == "executei"]
    acertos = [h for h in executadas if h.get("resultado") == "acertou"]
    taxa = round(len(acertos) / len(executadas) * 100, 1) if executadas else 0

    return {
        "historico": historico,
        "stats": {
            "total_propostas": total,
            "executadas": len(executadas),
            "acertos": len(acertos),
            "taxa_acerto": taxa,
        },
        "scores_robos": dados.get("scores_robos", {})
    }


@router.get("/watchlist")
async def ver_watchlist():
    dados = carregar_dados()
    return {"watchlist": dados.get("watchlist", WATCHLIST_DEFAULT)}


class WatchlistItem(BaseModel):
    ticker: str
    tipo: str
    nome: str


@router.post("/watchlist")
async def adicionar_watchlist(item: WatchlistItem):
    """Adicionar ativo à watchlist de monitoramento."""
    dados = carregar_dados()
    watchlist = dados.get("watchlist", WATCHLIST_DEFAULT)
    if not any(w["ticker"] == item.ticker for w in watchlist):
        watchlist.append(item.dict())
        dados["watchlist"] = watchlist
        salvar_dados(dados)
    return {"ok": True, "watchlist": watchlist}


@router.delete("/watchlist/{ticker}")
async def remover_watchlist(ticker: str):
    dados = carregar_dados()
    dados["watchlist"] = [w for w in dados.get("watchlist", []) if w["ticker"] != ticker]
    salvar_dados(dados)
    return {"ok": True}


@router.get("/scores")
async def ver_scores():
    """Ver scores actuais de todos os robôs."""
    dados = carregar_dados()
    scores = dados.get("scores_robos", {})

    ROBOS_INFO = {
        "alpha": {"nome": "Alpha-RSI", "estrategia": "Momentum — RSI + MACD"},
        "beta":  {"nome": "Beta-Bollinger", "estrategia": "Mean Reversion — Bollinger"},
        "gamma": {"nome": "Gamma-Trend", "estrategia": "Trend Following — Z-Score + Hurst"},
    }

    resultado = []
    for robo_id, info in ROBOS_INFO.items():
        score_data = scores.get(robo_id, {"acertos": 0, "erros": 0, "total": 0, "taxa_acerto": 0.5})
        resultado.append({
            "id": robo_id,
            **info,
            **score_data,
        })

    return {"robos": resultado}
