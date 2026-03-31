from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.services.robo_service import (
    analisar_swing_trade, analisar_rebalanceamento_cripto,
    executar_proposta, rejeitar_proposta, listar_propostas,
    monitor, THRESHOLD_SEM_2FA
)

router = APIRouter()

class AnalisarInput(BaseModel):
    alocacao_atual:  Dict[str, float] = {}
    alocacao_target: Dict[str, float] = {}
    patrimonio:      float = 100
    precos_swing:    Optional[Dict[str, List[float]]] = None

class ExecutarInput(BaseModel):
    proposta_id: str
    token_2fa:   Optional[str] = None

class MonitorInput(BaseModel):
    patrimonio:      float
    alocacao_target: Dict[str, float]

@router.post("/analisar")
async def analisar(payload: AnalisarInput):
    try:
        propostas = []
        if payload.precos_swing:
            from app.services.robo_service import ATIVOS_BINANCE
            for ticker, precos in payload.precos_swing.items():
                symbol = ATIVOS_BINANCE.get(ticker.upper(), ticker.upper()+"USDT")
                prop = await analisar_swing_trade(
                    symbol=symbol, ticker_base=ticker,
                    precos=precos, patrimonio=payload.patrimonio,
                )
                if prop:
                    propostas.append(prop)
        return {
            "total": len(propostas),
            "threshold_2fa": THRESHOLD_SEM_2FA,
            "propostas": [{"id":p.id,"robo_id":p.robo_id,"tipo_robo":p.tipo_robo,
                "symbol":p.symbol,"lado":p.lado,"valor_total":p.valor_total,
                "justificativa":p.justificativa,"requer_2fa":p.requer_2fa,
                "urgencia":p.urgencia,"status":p.status.value} for p in propostas],
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/executar")
async def executar(payload: ExecutarInput):
    resultado = await executar_proposta(payload.proposta_id, payload.token_2fa)
    if resultado.get("aguardando_2fa"):
        return {"status":"aguardando_2fa","dev_token":resultado.get("dev_token"),
                "mensagem":resultado.get("mensagem"),"proposta_id":payload.proposta_id}
    if not resultado.get("sucesso"):
        raise HTTPException(400, resultado.get("erro","Erro"))
    return resultado

@router.post("/rejeitar/{proposta_id}")
async def rejeitar(proposta_id: str):
    if not rejeitar_proposta(proposta_id):
        raise HTTPException(404, "Proposta não encontrada")
    return {"rejeitada": True}

@router.get("/propostas")
async def propostas(status: Optional[str] = None):
    return {"propostas": listar_propostas(status)}

@router.post("/monitor/iniciar")
async def iniciar_monitor(payload: MonitorInput):
    await monitor.iniciar(payload.patrimonio, payload.alocacao_target)
    return {"rodando":True,"threshold_2fa":THRESHOLD_SEM_2FA,
            "mensagem":f"Monitor iniciado. Ordens < R${THRESHOLD_SEM_2FA:.0f} executam automaticamente."}

@router.post("/monitor/parar")
async def parar_monitor():
    await monitor.parar()
    return {"rodando":False}

@router.get("/monitor/status")
async def status_monitor():
    return {"rodando":monitor._rodando,"propostas_geradas":monitor.propostas_geradas,
            "ultima_analise":monitor.ultima_analise.isoformat() if monitor.ultima_analise else None,
            "threshold_2fa":THRESHOLD_SEM_2FA}
