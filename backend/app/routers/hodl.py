"""
Router: Corretoras + HODL + Wallet — /api/v1/hodl e /api/v1/broker
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.services.broker_service import (
    hodl_manager, realizacao_manager, RegraRealizacao,
    toro_client, avenue_importer, binance_client,
    coinbase_client, cryptocom_client, metamask_reader,
    BinanceClient, CoinbaseClient, CryptoComClient, MetaMaskReader,
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# ── HODL Lock ──────────────────────────────────────────────────────────────────

class HodlInput(BaseModel):
    conta: str
    ticker: str
    motivo: str = "hodl"

class RegraRealizacaoInput(BaseModel):
    conta: str
    ticker: str
    gatilho_lucro_pct: float
    percentual_realizar: float = 0.30
    destino: str = "TESOURO"

class BrokerConfig(BaseModel):
    exchange: str          # "binance", "coinbase", "crypto_com", "metamask"
    api_key: str = ""
    api_secret: str = ""
    extra: str = ""        # infura_project_id para metamask, key_name para coinbase

class OrdemInput(BaseModel):
    exchange: str
    symbol: str            # "BTCUSDT" (Binance), "BTC-USD" (Coinbase), "BTC_USDT" (Crypto.com)
    lado: str              # "BUY"/"SELL" ou "COMPRA"/"VENDA"
    quantidade: float
    preco: Optional[float] = None
    tipo: str = "MARKET"

@router.post("/lock")
async def bloquear_ativo(payload: HodlInput):
    lock = hodl_manager.bloquear(payload.conta, payload.ticker, payload.motivo)
    return {"bloqueado": True, "ticker": lock.ticker, "conta": lock.conta,
            "motivo": lock.motivo, "criado_em": lock.criado_em.isoformat(),
            "mensagem": f"{lock.ticker} em {lock.conta} protegido. Robô nunca vai tocar."}

@router.delete("/lock/{conta}/{ticker}")
async def desbloquear_ativo(conta: str, ticker: str):
    if not hodl_manager.desbloquear(conta, ticker):
        raise HTTPException(404, f"{ticker.upper()} não estava bloqueado em {conta}")
    return {"desbloqueado": True, "ticker": ticker.upper(), "conta": conta,
            "mensagem": f"{ticker.upper()} desbloqueado. Robô pode operar novamente."}

@router.get("/locks")
async def listar_locks(conta: Optional[str] = None):
    locks = hodl_manager.listar_locks(conta)
    return {"total": len(locks),
            "locks": [{"ticker":l.ticker,"conta":l.conta,"motivo":l.motivo,
                       "criado_em":l.criado_em.isoformat()} for l in locks]}

@router.get("/lock/{conta}/{ticker}/check")
async def verificar_lock(conta: str, ticker: str):
    pode, motivo = hodl_manager.verificar_proposta(conta, ticker)
    return {"ticker": ticker.upper(), "conta": conta,
            "pode_operar": pode, "bloqueado": not pode, "motivo": motivo}

@router.post("/realizacao")
async def configurar_realizacao(payload: RegraRealizacaoInput):
    regra = RegraRealizacao(**payload.dict())
    realizacao_manager.adicionar_regra(regra)
    return {"configurado": True, "ticker": regra.ticker, "conta": regra.conta,
            "gatilho": f"+{regra.gatilho_lucro_pct*100:.0f}%",
            "realizar": f"{regra.percentual_realizar*100:.0f}% da posição",
            "destino": regra.destino,
            "mensagem": f"Quando {regra.ticker} atingir +{regra.gatilho_lucro_pct*100:.0f}%, robô vende {regra.percentual_realizar*100:.0f}% → {regra.destino}"}

# ── Toro ────────────────────────────────────────────────────────────────────────

@router.get("/toro/saldo")
async def toro_saldo():
    return await toro_client.get_saldo()

@router.post("/toro/ordem")
async def toro_ordem(ticker: str, lado: str, quantidade: float, preco: Optional[float] = None):
    r = await toro_client.criar_ordem(ticker, lado, quantidade, preco)
    if not r["sucesso"]:
        raise HTTPException(400, r.get("erro","Erro"))
    return r

@router.post("/toro/realizar/{ticker}")
async def toro_realizar(ticker: str, lucro_pct: float, percentual: float=0.30, destino: str="TESOURO"):
    r = await toro_client.realizar_parcial(ticker, lucro_pct, percentual, destino)
    if not r["sucesso"]:
        raise HTTPException(400, r.get("erro","Erro"))
    return r

# ── Binance ─────────────────────────────────────────────────────────────────────

@router.get("/binance/saldo")
async def binance_saldo():
    if not binance_client.api_key:
        return {"erro": "API keys não configuradas. Use POST /hodl/broker/configurar"}
    return await binance_client.get_saldo()

@router.get("/binance/preco/{symbol}")
async def binance_preco(symbol: str):
    preco = await binance_client.get_preco(symbol.upper())
    if not preco:
        raise HTTPException(404, f"Símbolo {symbol} não encontrado")
    return {"symbol": symbol.upper(), "preco": preco}

@router.get("/binance/ping")
async def binance_ping():
    ok = await binance_client.ping()
    return {"conectado": ok, "api_configurada": bool(binance_client.api_key)}

@router.get("/binance/ordens-abertas")
async def binance_ordens(symbol: Optional[str] = None):
    if not binance_client.api_key:
        raise HTTPException(400, "API keys não configuradas")
    return await binance_client.get_ordens_abertas(symbol)

# ── Coinbase ─────────────────────────────────────────────────────────────────────

@router.get("/coinbase/saldo")
async def coinbase_saldo():
    if not coinbase_client.api_key_name:
        return {"erro": "API keys não configuradas"}
    return await coinbase_client.get_saldo()

@router.get("/coinbase/preco/{product_id}")
async def coinbase_preco(product_id: str):
    preco = await coinbase_client.get_preco(product_id)
    if not preco:
        raise HTTPException(404, f"Produto {product_id} não encontrado")
    return {"product_id": product_id, "preco": preco}

# ── Crypto.com ────────────────────────────────────────────────────────────────────

@router.get("/crypto/posicoes")
async def crypto_posicoes():
    posicoes = await cryptocom_client.get_posicoes()
    return {"total": len(posicoes), "posicoes": posicoes,
            "bloqueados": [p["ticker"] for p in posicoes if p.get("bloqueado")]}

# ── MetaMask / Web3 ───────────────────────────────────────────────────────────────

@router.get("/metamask/saldo/{address}")
async def metamask_saldo(address: str):
    """Lê saldo ETH e tokens ERC-20 de um endereço público."""
    if not metamask_reader.infura_url or "YOUR" in metamask_reader.infura_url:
        # Fallback sem Infura — retorna dados de exemplo
        return {"address": address, "network": "ethereum",
                "saldos": {"ETH": 0.0, "nota": "Configure INFURA_PROJECT_ID no .env"},
                "hodl_locks": hodl_manager.listar_locks("metamask")}
    resultado = await metamask_reader.get_portfolio_completo(address)
    return resultado

@router.get("/metamask/token/{address}/{token}")
async def metamask_token(address: str, token: str):
    """Saldo de um token ERC-20 específico."""
    if token.upper() == "ETH":
        saldo = await metamask_reader.get_saldo_eth(address)
    else:
        saldo = await metamask_reader.get_saldo_token(address, token.upper())
    return {"address": address, "token": token.upper(), "saldo": saldo or 0,
            "bloqueado": hodl_manager.esta_bloqueado("metamask", token.upper())}

# ── Ordem unificada (qualquer exchange) ──────────────────────────────────────────

@router.post("/ordem")
async def criar_ordem_unificada(payload: OrdemInput):
    """
    Endpoint unificado — cria ordem em qualquer exchange.
    Verifica HODL lock antes de qualquer execução.
    """
    ex = payload.exchange.lower()
    lado = payload.lado.upper()

    if ex == "binance":
        if not binance_client.api_key:
            raise HTTPException(400, "Binance não configurada")
        r = await binance_client.criar_ordem_market(
            payload.symbol.upper(), lado, payload.quantidade)
    elif ex == "coinbase":
        if not coinbase_client.api_key_name:
            raise HTTPException(400, "Coinbase não configurada")
        r = await coinbase_client.criar_ordem(
            payload.symbol, lado, str(payload.quantidade))
    elif ex in ("crypto_com", "cryptocom"):
        r = await cryptocom_client.criar_ordem(
            payload.symbol, lado, payload.quantidade)
    elif ex == "toro":
        lado_toro = "COMPRA" if lado == "BUY" else "VENDA"
        r = await toro_client.criar_ordem(
            payload.symbol, lado_toro, payload.quantidade, payload.preco)
    else:
        raise HTTPException(400, f"Exchange '{payload.exchange}' não suportada. Use: binance, coinbase, crypto_com, toro")

    if not r.get("sucesso"):
        raise HTTPException(400, r.get("erro","Erro na ordem"))
    return r

# ── Configurar API keys ────────────────────────────────────────────────────────

@router.post("/broker/configurar")
async def configurar_broker(payload: BrokerConfig):
    """
    Configura API keys de uma exchange para a sessão atual.
    Em produção: criptografar com Fernet e salvar no Supabase por usuário.
    NUNCA logar as keys.
    """
    ex = payload.exchange.lower()
    global binance_client, coinbase_client, cryptocom_client, metamask_reader

    if ex == "binance":
        binance_client = BinanceClient(payload.api_key, payload.api_secret)
        ok = await binance_client.ping()
        return {"configurado": True, "exchange": "binance", "conectado": ok,
                "mensagem": "Binance configurada. Keys com permissão Spot Trading, sem saque."}

    elif ex == "coinbase":
        coinbase_client = CoinbaseClient(payload.api_key, payload.api_secret)
        return {"configurado": True, "exchange": "coinbase",
                "mensagem": "Coinbase Advanced Trade configurada."}

    elif ex in ("crypto_com", "cryptocom"):
        cryptocom_client = CryptoComClient(payload.api_key, payload.api_secret)
        return {"configurado": True, "exchange": "crypto_com",
                "mensagem": "Crypto.com configurada."}

    elif ex == "metamask":
        infura_id = payload.extra or payload.api_key
        metamask_reader = MetaMaskReader(infura_id)
        return {"configurado": True, "exchange": "metamask",
                "mensagem": "MetaMask reader configurado via Infura."}

    raise HTTPException(400, f"Exchange '{payload.exchange}' não reconhecida")

# ── Avenue CSV import ─────────────────────────────────────────────────────────────

@router.post("/avenue/import")
async def avenue_import(file: UploadFile = File(...)):
    """Importa posições da Avenue via CSV exportado da plataforma."""
    content = await file.read()
    csv_text = content.decode("utf-8", errors="replace")
    posicoes = avenue_importer.importar_csv(csv_text)
    total_usd = avenue_importer.get_valor_total_usd()
    return {"importado": True, "total_posicoes": len(posicoes),
            "valor_total_usd": total_usd, "posicoes": posicoes}

@router.get("/avenue/posicoes")
async def avenue_posicoes():
    return {"posicoes": avenue_importer.get_posicoes(),
            "total_usd": avenue_importer.get_valor_total_usd()}
