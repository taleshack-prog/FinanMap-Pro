"""
FinanMap Pro — Serviço de Execução de Robôs v3
Corrigido: apenas ativos disponíveis na exchange configurada
Binance: apenas cripto (BTC, ETH, BNB, etc.)
Toro/XP: ações B3 (BOVA11, PETR4, etc.)
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.services.broker_service import hodl_manager, binance_client
from app.services.auth_service import criar_desafio_2fa, verificar_desafio_2fa
from app.services.technical_service import calcular_rsi, calcular_macd, calcular_bollinger, sintetizar_sinal

logger = logging.getLogger(__name__)

THRESHOLD_SEM_2FA = 500.0

# Ativos disponíveis por exchange
ATIVOS_BINANCE = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "BNB":  "BNBUSDT",
    "SOL":  "SOLUSDT",
    "ADA":  "ADAUSDT",
    "MATIC":"MATICUSDT",
    "DOT":  "DOTUSDT",
    "LINK": "LINKUSDT",
    "AVAX": "AVAXUSDT",
    "XRP":  "XRPUSDT",
}

ATIVOS_TORO = {
    "BOVA11": "BOVA11",
    "IVVB11": "IVVB11",
    "PETR4":  "PETR4",
    "VALE3":  "VALE3",
    "ITUB4":  "ITUB4",
}


class StatusProposta(str, Enum):
    PENDENTE      = "pendente"
    AGUARDANDO_2FA= "aguardando_2fa"
    APROVADA      = "aprovada"
    EXECUTADA     = "executada"
    REJEITADA     = "rejeitada"
    EXPIRADA      = "expirada"


@dataclass
class PropostaOrdem:
    id:           str
    robo_id:      str
    tipo_robo:    str
    exchange:     str
    symbol:       str
    ticker_base:  str
    lado:         str
    quantidade:   float
    preco_alvo:   float
    valor_total:  float
    justificativa:str
    stop_loss_pct:float
    urgencia:     str = "normal"
    status:       StatusProposta = StatusProposta.PENDENTE
    requer_2fa:   bool = False
    criado_em:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executado_em: Optional[datetime] = None
    resultado:    Optional[Dict] = None


_propostas: Dict[str, PropostaOrdem] = {}


def _gerar_id() -> str:
    return f"prop-{int(time.time()*1000)}"


async def analisar_swing_trade(
    symbol: str,
    ticker_base: str,
    precos: List[float],
    patrimonio: float,
    exchange: str = "binance",
    stop_loss_pct: float = -0.08,
    tamanho_posicao: float = 0.05,
) -> Optional[PropostaOrdem]:
    """Swing trade apenas em ativos disponíveis na exchange."""
    if len(precos) < 20:
        return None

    # Verificar se ativo existe na exchange
    if exchange == "binance" and ticker_base.upper() not in ATIVOS_BINANCE:
        return None
    if exchange == "toro" and ticker_base.upper() not in ATIVOS_TORO:
        return None

    pode, motivo = hodl_manager.verificar_proposta(exchange, ticker_base)
    if not pode:
        return None

    rsi = calcular_rsi(precos)
    macd_v, macd_s, macd_h = calcular_macd(precos)
    bb_u, bb_m, bb_l, bb_p = calcular_bollinger(precos)
    sinal, forca = sintetizar_sinal(rsi, macd_h, bb_p)

    if forca < 0.55:
        return None

    preco_atual = precos[-1]
    valor = patrimonio * tamanho_posicao
    qtd   = round(valor / preco_atual, 6)
    lado  = "BUY" if sinal == "compra" else "SELL"

    pid  = _gerar_id()
    prop = PropostaOrdem(
        id=pid, robo_id=f"robo-swing-{ticker_base}",
        tipo_robo="swing_trade", exchange=exchange,
        symbol=symbol, ticker_base=ticker_base,
        lado=lado, quantidade=qtd, preco_alvo=preco_atual,
        valor_total=round(valor, 2),
        justificativa=f"RSI={rsi:.1f} | MACD={macd_h:.4f} | BB={bb_p:.2f} | {sinal} força={forca:.0%}",
        stop_loss_pct=stop_loss_pct,
        requer_2fa=valor > THRESHOLD_SEM_2FA,
        urgencia="alta" if rsi < 25 or rsi > 78 else "normal",
    )
    _propostas[pid] = prop
    return prop


async def analisar_rebalanceamento_cripto(
    saldo_atual: Dict[str, float],
    patrimonio: float,
) -> List[PropostaOrdem]:
    """
    Rebalanceamento apenas entre ativos cripto da Binance.
    Ex: se BTC > 80% do portfólio, sugere diversificar para ETH/BNB.
    """
    propostas = []
    if not saldo_atual or patrimonio < 10:
        return propostas

    total = sum(v for v in saldo_atual.values())
    if total <= 0:
        return propostas

    for ticker, valor in saldo_atual.items():
        pct = (valor / total) * 100
        # Se um ativo representa >90% e há outros ativos → sugerir diversificação
        if pct > 90 and len(saldo_atual) == 1:
            pid = _gerar_id()
            prop = PropostaOrdem(
                id=pid, robo_id="robo-rebalance-cripto",
                tipo_robo="rebalanceamento", exchange="binance",
                symbol=ATIVOS_BINANCE.get(ticker, ticker+"USDT"),
                ticker_base=ticker, lado="HOLD",
                quantidade=0, preco_alvo=0,
                valor_total=0,
                justificativa=f"{ticker} representa {pct:.0f}% da carteira Binance. Considere diversificar em ETH ou BNB para reduzir risco de concentração.",
                stop_loss_pct=-0.10,
                requer_2fa=False,
                urgencia="normal",
            )
            _propostas[pid] = prop
            propostas.append(prop)

    return propostas


async def executar_proposta(proposta_id: str, token_2fa: Optional[str] = None) -> Dict:
    prop = _propostas.get(proposta_id)
    if not prop:
        return {"sucesso": False, "erro": "Proposta não encontrada"}

    if prop.status in (StatusProposta.EXECUTADA, StatusProposta.REJEITADA):
        return {"sucesso": False, "erro": f"Proposta já {prop.status.value}"}

    # Ordens HOLD são apenas informativas
    if prop.lado == "HOLD":
        prop.status = StatusProposta.EXECUTADA
        return {"sucesso": True, "mensagem": prop.justificativa, "tipo": "informativo"}

    if prop.requer_2fa:
        if not token_2fa:
            token = criar_desafio_2fa("usuario", f"ordem_{prop.symbol}")
            prop.status = StatusProposta.AGUARDANDO_2FA
            return {
                "sucesso": False, "aguardando_2fa": True,
                "dev_token": token,
                "mensagem": f"Ordem R${prop.valor_total:,.0f} requer 2FA.",
                "proposta_id": prop.id,
            }
        aprovado, msg = verificar_desafio_2fa("usuario", token_2fa, f"ordem_{prop.symbol}")
        if not aprovado:
            return {"sucesso": False, "erro": f"2FA inválido: {msg}"}

    pode, motivo = hodl_manager.verificar_proposta(prop.exchange, prop.ticker_base)
    if not pode:
        prop.status = StatusProposta.REJEITADA
        return {"sucesso": False, "erro": motivo, "hodl_block": True}

    prop.status = StatusProposta.APROVADA
    try:
        if prop.exchange == "binance" and binance_client.api_key:
            resultado = await binance_client.criar_ordem_market(
                prop.symbol, prop.lado, prop.quantidade
            )
        else:
            import random
            resultado = {
                "sucesso": True,
                "ordem_id": f"SIM-{int(time.time()*1000)}",
                "preco_executado": prop.preco_alvo * (1 + random.uniform(-0.001, 0.001)),
                "quantidade_executada": prop.quantidade,
                "taxa": prop.valor_total * 0.001,
                "mensagem": f"[SIMULADO] {prop.lado} {prop.quantidade} {prop.symbol}",
                "simulado": True,
            }

        if resultado.get("sucesso"):
            prop.status = StatusProposta.EXECUTADA
            prop.executado_em = datetime.now(timezone.utc)
            prop.resultado = resultado

        return {
            "sucesso":     resultado.get("sucesso", False),
            "proposta_id": prop.id,
            "ordem_id":    resultado.get("ordem_id"),
            "symbol":      prop.symbol,
            "lado":        prop.lado,
            "valor":       prop.valor_total,
            "mensagem":    resultado.get("mensagem", ""),
            "simulado":    resultado.get("simulado", False),
        }
    except Exception as e:
        prop.status = StatusProposta.REJEITADA
        return {"sucesso": False, "erro": str(e)}


class RoboMonitor:
    def __init__(self):
        self._rodando  = False
        self._task     = None
        self.propostas_geradas = 0
        self.ultima_analise: Optional[datetime] = None

    async def iniciar(self, patrimonio: float, alocacao_target: Dict):
        if self._rodando:
            return
        self._rodando = True
        self._task = asyncio.create_task(self._loop(patrimonio, alocacao_target))
        logger.info("Monitor de robôs iniciado")

    async def parar(self):
        self._rodando = False
        if self._task:
            self._task.cancel()

    async def _loop(self, patrimonio: float, alocacao_target: Dict):
        while self._rodando:
            try:
                await self._analisar(patrimonio, alocacao_target)
                self.ultima_analise = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(f"Monitor erro: {e}")
            await asyncio.sleep(60)

    async def _analisar(self, patrimonio: float, alocacao_target: Dict):
        # Buscar saldo real da Binance
        if binance_client.api_key:
            saldo = await binance_client.get_saldo()
            if saldo:
                props = await analisar_rebalanceamento_cripto(
                    {k: v for k, v in saldo.items() if k not in ("USDT","USDC","BNB") and v > 0},
                    patrimonio
                )
                self.propostas_geradas += len(props)


monitor = RoboMonitor()


def listar_propostas(status: Optional[str] = None) -> List[Dict]:
    props = list(_propostas.values())
    if status:
        props = [p for p in props if p.status.value == status]
    return [
        {
            "id": p.id, "robo_id": p.robo_id, "tipo_robo": p.tipo_robo,
            "exchange": p.exchange, "symbol": p.symbol, "lado": p.lado,
            "valor_total": p.valor_total, "justificativa": p.justificativa,
            "status": p.status.value, "requer_2fa": p.requer_2fa,
            "urgencia": p.urgencia, "criado_em": p.criado_em.isoformat(),
        }
        for p in sorted(props, key=lambda x: x.criado_em, reverse=True)
    ]


def rejeitar_proposta(proposta_id: str) -> bool:
    prop = _propostas.get(proposta_id)
    if prop and prop.status == StatusProposta.PENDENTE:
        prop.status = StatusProposta.REJEITADA
        return True
    return False
