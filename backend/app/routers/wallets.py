# backend/app/routers/wallets.py
# Leitura de saldos de wallets multi-chain via RPC público
# Suporta: Ethereum/EVM, Base, Solana, VeChain, NEAR

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os
import aiohttp
import json

router = APIRouter(prefix="/api/v1/wallets", tags=["wallets"])
logger = logging.getLogger(__name__)

# ── Detecção automática de chain pelo endereço ────────────────────────────────

def detectar_chain(endereco: str) -> str:
    """Detecta a blockchain pelo formato do endereço."""
    e = endereco.strip()
    if e.startswith('0x') and len(e) == 42:
        return 'evm'           # Ethereum, Base, Polygon, etc.
    if len(e) in (43, 44) and e[0] in ('A','B','C','D','E','F','G','H','J','K','L','M','N','P','Q','R','S','T','U','V','W','X','Y','Z','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','1','2','3','4','5','6','7','8','9'):
        return 'solana'        # Solana base58
    if e.startswith('0x') and len(e) == 66:
        return 'vechain'       # VeChain
    if e.endswith('.near') or (len(e) == 64 and all(c in '0123456789abcdef' for c in e)):
        return 'near'          # NEAR Protocol
    if e.startswith('V') and len(e) in (40, 42):
        return 'vechain'
    return 'desconhecido'


# ── EVM (Ethereum, Base, Polygon) ────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv()

_INFURA = os.getenv('INFURA_PROJECT_ID', '')
EVM_RPCS = {
    'ethereum': f'https://mainnet.infura.io/v3/{_INFURA}' if _INFURA else 'https://ethereum.publicnode.com',
    'base': 'https://mainnet.base.org',
    'polygon': 'https://polygon.publicnode.com',
}

ERC20_TOKENS = [
    {'symbol': 'USDT', 'address': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'decimals': 6},
    {'symbol': 'USDC', 'address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'decimals': 6},
    {'symbol': 'WBTC', 'address': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', 'decimals': 8},
    {'symbol': 'LINK', 'address': '0x514910771AF9Ca656af840dff83E8264EcF986CA', 'decimals': 18},
    {'symbol': 'UNI',  'address': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 'decimals': 18},
]

async def get_evm_balance(endereco: str, rpc_url: str, chain: str) -> dict:
    """Busca saldo ETH + tokens ERC20 via JSON-RPC."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            # Saldo ETH nativo
            payload = {
                "jsonrpc": "2.0", "method": "eth_getBalance",
                "params": [endereco, "latest"], "id": 1
            }
            async with session.post(rpc_url, json=payload) as r:
                data = await r.json()
            eth_wei = int(data.get('result', '0x0'), 16)
            eth_balance = eth_wei / 1e18

            # Buscar preço ETH em USD
            eth_usd = await get_price_usd('ETH')

            saldos = {}
            if eth_balance > 0.0001:
                saldos['ETH'] = {
                    'amount': eth_balance,
                    'usd': eth_balance * eth_usd,
                    'symbol': 'ETH'
                }

            # Saldos ERC20
            for token in ERC20_TOKENS:
                # eth_call para balanceOf
                data_hex = '0x70a08231' + '000000000000000000000000' + endereco[2:]
                payload2 = {
                    "jsonrpc": "2.0", "method": "eth_call",
                    "params": [{"to": token['address'], "data": data_hex}, "latest"],
                    "id": 2
                }
                async with session.post(rpc_url, json=payload2) as r2:
                    data2 = await r2.json()
                result = data2.get('result', '0x0')
                if result and result != '0x':
                    amount = int(result, 16) / (10 ** token['decimals'])
                    if amount > 0.01:
                        usd_price = await get_price_usd(token['symbol'])
                        saldos[token['symbol']] = {
                            'amount': amount,
                            'usd': amount * usd_price,
                            'symbol': token['symbol']
                        }

            total_usd = sum(v['usd'] for v in saldos.values())
            return {
                'chain': chain,
                'endereco': endereco,
                'saldos': saldos,
                'total_usd': round(total_usd, 2),
                'ok': True
            }
    except Exception as e:
        logger.error(f"EVM erro {endereco}: {e}")
        return {'erro': str(e), 'ok': False}


# ── Solana ────────────────────────────────────────────────────────────────────

SOLANA_RPC = 'https://api.mainnet-beta.solana.com'

SPL_TOKENS_KNOWN = {
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': ('USDC', 6),
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': ('USDT', 6),
    'So11111111111111111111111111111111111111112':   ('SOL', 9),
}

async def get_solana_balance(endereco: str) -> dict:
    """Busca saldo SOL + SPL tokens."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            # Saldo SOL
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "getBalance",
                "params": [endereco]
            }
            async with session.post(SOLANA_RPC, json=payload) as r:
                data = await r.json()
            lamports = data.get('result', {}).get('value', 0)
            sol_balance = lamports / 1e9

            sol_usd = await get_price_usd('SOL')
            saldos = {}

            if sol_balance > 0.001:
                saldos['SOL'] = {
                    'amount': sol_balance,
                    'usd': sol_balance * sol_usd,
                    'symbol': 'SOL'
                }

            # SPL Tokens
            payload2 = {
                "jsonrpc": "2.0", "id": 2,
                "method": "getTokenAccountsByOwner",
                "params": [
                    endereco,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"}
                ]
            }
            async with session.post(SOLANA_RPC, json=payload2) as r2:
                data2 = await r2.json()

            accounts = data2.get('result', {}).get('value', [])
            for acc in accounts:
                info = acc.get('account', {}).get('data', {}).get('parsed', {}).get('info', {})
                mint = info.get('mint', '')
                amount = float(info.get('tokenAmount', {}).get('uiAmount', 0) or 0)
                if amount > 0 and mint in SPL_TOKENS_KNOWN:
                    symbol, _ = SPL_TOKENS_KNOWN[mint]
                    usd_price = await get_price_usd(symbol)
                    saldos[symbol] = {
                        'amount': amount,
                        'usd': amount * usd_price,
                        'symbol': symbol
                    }

            total_usd = sum(v['usd'] for v in saldos.values())
            return {
                'chain': 'solana',
                'endereco': endereco,
                'saldos': saldos,
                'total_usd': round(total_usd, 2),
                'ok': True
            }
    except Exception as e:
        logger.error(f"Solana erro {endereco}: {e}")
        return {'erro': str(e), 'ok': False}


# ── VeChain ───────────────────────────────────────────────────────────────────

VECHAIN_RPC = 'https://mainnet.veblocks.net'

async def get_vechain_balance(endereco: str) -> dict:
    """Busca saldo VET + VTHO."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(f"{VECHAIN_RPC}/accounts/{endereco}") as r:
                data = await r.json()

            vet_balance = int(data.get('balance', '0x0'), 16) / 1e18
            vtho_balance = int(data.get('energy', '0x0'), 16) / 1e18

            vet_usd = await get_price_usd('VET')
            vtho_usd = await get_price_usd('VTHO')

            saldos = {}
            if vet_balance > 1:
                saldos['VET'] = {'amount': vet_balance, 'usd': vet_balance * vet_usd, 'symbol': 'VET'}
            if vtho_balance > 1:
                saldos['VTHO'] = {'amount': vtho_balance, 'usd': vtho_balance * vtho_usd, 'symbol': 'VTHO'}

            total_usd = sum(v['usd'] for v in saldos.values())
            return {
                'chain': 'vechain',
                'endereco': endereco,
                'saldos': saldos,
                'total_usd': round(total_usd, 2),
                'ok': True
            }
    except Exception as e:
        logger.error(f"VeChain erro {endereco}: {e}")
        return {'erro': str(e), 'ok': False}


# ── NEAR ──────────────────────────────────────────────────────────────────────

NEAR_RPC = 'https://rpc.mainnet.near.org'

async def get_near_balance(endereco: str) -> dict:
    """Busca saldo NEAR."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "query",
                "params": {
                    "request_type": "view_account",
                    "finality": "final",
                    "account_id": endereco
                }
            }
            async with session.post(NEAR_RPC, json=payload) as r:
                data = await r.json()

            result = data.get('result', {})
            yocto = int(result.get('amount', '0'))
            near_balance = yocto / 1e24

            near_usd = await get_price_usd('NEAR')
            saldos = {}
            if near_balance > 0.01:
                saldos['NEAR'] = {
                    'amount': near_balance,
                    'usd': near_balance * near_usd,
                    'symbol': 'NEAR'
                }

            # SWEAT token (contrato NEAR)
            try:
                payload2 = {
                    "jsonrpc": "2.0", "id": 2,
                    "method": "query",
                    "params": {
                        "request_type": "call_function",
                        "finality": "final",
                        "account_id": "token.sweat",
                        "method_name": "ft_balance_of",
                        "args_base64": __import__('base64').b64encode(
                            json.dumps({"account_id": endereco}).encode()
                        ).decode()
                    }
                }
                async with session.post(NEAR_RPC, json=payload2) as r2:
                    data2 = await r2.json()
                result2 = data2.get('result', {})
                if 'result' in result2:
                    sweat_raw = bytes(result2['result']).decode()
                    sweat_balance = int(sweat_raw.strip('"')) / 1e18
                    sweat_usd = await get_price_usd('SWEAT')
                    if sweat_balance > 1:
                        saldos['SWEAT'] = {
                            'amount': sweat_balance,
                            'usd': sweat_balance * sweat_usd,
                            'symbol': 'SWEAT'
                        }
            except Exception:
                pass

            total_usd = sum(v['usd'] for v in saldos.values())
            return {
                'chain': 'near',
                'endereco': endereco,
                'saldos': saldos,
                'total_usd': round(total_usd, 2),
                'ok': True
            }
    except Exception as e:
        logger.error(f"NEAR erro {endereco}: {e}")
        return {'erro': str(e), 'ok': False}


# ── Preços em USD via Binance ──────────────────────────────────────────────────

_price_cache = {}

async def get_price_usd(symbol: str) -> float:
    """Busca preço em USD via Binance (com cache)."""
    if symbol in _price_cache:
        return _price_cache[symbol]
    stablecoins = {'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD'}
    if symbol in stablecoins:
        return 1.0
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
            async with session.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    price = float(data.get('price', 0))
                    _price_cache[symbol] = price
                    return price
    except Exception:
        pass
    return 0.0


# ── Endpoints ──────────────────────────────────────────────────────────────────

class WalletInput(BaseModel):
    endereco: str
    chain: Optional[str] = None  # auto-detectar se None
    nome: Optional[str] = None


@router.post("/saldo")
async def get_wallet_saldo(payload: WalletInput):
    """Busca saldo de qualquer wallet pelo endereço público."""
    endereco = payload.endereco.strip()
    chain = payload.chain or detectar_chain(endereco)

    logger.info(f"Wallet saldo: {endereco[:12]}... chain={chain}")

    if chain == 'evm':
        # Tentar Ethereum primeiro, depois Base
        resultado = await get_evm_balance(endereco, EVM_RPCS['ethereum'], 'ethereum')
        if resultado.get('ok') and resultado.get('total_usd', 0) == 0:
            # Tentar Base
            base_result = await get_evm_balance(endereco, EVM_RPCS['base'], 'base')
            if base_result.get('total_usd', 0) > 0:
                resultado = base_result
    elif chain == 'solana':
        resultado = await get_solana_balance(endereco)
    elif chain == 'vechain':
        resultado = await get_vechain_balance(endereco)
    elif chain == 'near':
        resultado = await get_near_balance(endereco)
    else:
        raise HTTPException(400, f"Chain não suportada: {chain}. Endereço: {endereco}")

    if not resultado.get('ok'):
        raise HTTPException(400, resultado.get('erro', 'Erro desconhecido'))

    # Converter total_usd para BRL
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get('https://api.binance.com/api/v3/ticker/price?symbol=USDTBRL') as r:
                brl_data = await r.json()
        usd_brl = float(brl_data.get('price', 5.17))
    except Exception:
        usd_brl = 5.17

    resultado['total_brl'] = round(resultado['total_usd'] * usd_brl, 2)
    resultado['usd_brl'] = usd_brl
    resultado['chain_detectada'] = chain
    resultado['nome'] = payload.nome or endereco[:8] + '...'

    return resultado


@router.get("/chains")
async def listar_chains():
    """Lista as blockchains suportadas."""
    return {
        "chains": [
            {"id": "evm", "nome": "Ethereum / Base / Polygon", "wallets": ["MetaMask", "OneKey", "Base Wallet"], "prefixo": "0x..."},
            {"id": "solana", "nome": "Solana", "wallets": ["Phantom", "Solflare"], "prefixo": "base58 (44 chars)"},
            {"id": "vechain", "nome": "VeChain", "wallets": ["VeWorld"], "prefixo": "0x... (66 chars)"},
            {"id": "near", "nome": "NEAR Protocol", "wallets": ["Sweat Wallet"], "prefixo": "nome.near ou hash64"},
        ]
    }
