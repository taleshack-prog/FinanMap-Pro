"""
FinanMap Pro — Integrações com Corretoras e Wallets
- Binance: API v3 completa (spot, saldo, ordens, histórico)
- Crypto.com: API v2 (spot, saldo, ordens)
- Coinbase: Advanced Trade API (JWT/ECDSA)
- MetaMask: Web3.py leitura de saldo ETH + ERC-20 via Infura
- Toro: simulado (sem API pública)
- Avenue: import de CSV
- HODL Lock: genérico por conta/ticker
- Realização parcial: gatilho configurável
"""

import asyncio, httpx, hmac, hashlib, time, json, logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


# ── HODL Lock ─────────────────────────────────────────────────────────────────

@dataclass
class HodlLock:
    ticker: str
    conta: str
    motivo: str = "hodl"
    criado_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class HodlManager:
    def __init__(self):
        self._locks: Dict[str, HodlLock] = {}

    def _key(self, conta: str, ticker: str) -> str:
        return f"{conta}:{ticker.upper()}"

    def bloquear(self, conta: str, ticker: str, motivo: str = "hodl") -> HodlLock:
        lock = HodlLock(ticker=ticker.upper(), conta=conta, motivo=motivo)
        self._locks[self._key(conta, ticker)] = lock
        logger.info(f"HODL LOCK: {ticker.upper()} em {conta}")
        return lock

    def desbloquear(self, conta: str, ticker: str) -> bool:
        key = self._key(conta, ticker)
        if key in self._locks:
            del self._locks[key]
            return True
        return False

    def esta_bloqueado(self, conta: str, ticker: str) -> bool:
        return self._key(conta, ticker) in self._locks

    def listar_locks(self, conta: Optional[str] = None) -> List[HodlLock]:
        locks = list(self._locks.values())
        return [l for l in locks if l.conta == conta] if conta else locks

    def verificar_proposta(self, conta: str, ticker: str) -> Tuple[bool, str]:
        if self.esta_bloqueado(conta, ticker):
            lock = self._locks[self._key(conta, ticker)]
            return False, f"Ativo {ticker.upper()} bloqueado em {conta} — motivo: {lock.motivo}"
        return True, "OK"

hodl_manager = HodlManager()


# ── Realização parcial ─────────────────────────────────────────────────────────

@dataclass
class RegraRealizacao:
    conta: str
    ticker: str
    gatilho_lucro_pct: float
    percentual_realizar: float = 0.30
    destino: str = "TESOURO"
    ativa: bool = True

class RealizacaoManager:
    def __init__(self):
        self._regras: List[RegraRealizacao] = []
        self._precos_entrada: Dict[str, float] = {}

    def adicionar_regra(self, regra: RegraRealizacao):
        self._regras.append(regra)

    def registrar_entrada(self, conta: str, ticker: str, preco: float):
        self._precos_entrada[f"{conta}:{ticker}"] = preco

    async def verificar_e_realizar(self, conta: str, ticker: str, preco_atual: float, cliente) -> Optional[Dict]:
        for regra in self._regras:
            if regra.conta != conta or regra.ticker != ticker or not regra.ativa:
                continue
            preco_entrada = self._precos_entrada.get(f"{conta}:{ticker}")
            if not preco_entrada:
                continue
            lucro_pct = (preco_atual - preco_entrada) / preco_entrada
            if lucro_pct >= regra.gatilho_lucro_pct:
                if hasattr(cliente, 'realizar_parcial'):
                    return await cliente.realizar_parcial(ticker, lucro_pct, regra.percentual_realizar, regra.destino)
        return None

realizacao_manager = RealizacaoManager()


# ── Binance API v3 ────────────────────────────────────────────────────────────

class BinanceClient:
    """
    Binance Spot API v3
    Docs: https://developers.binance.com/docs/binance-spot-api-docs
    Auth: HMAC-SHA256 (X-MBX-APIKEY header + signature param)
    Criar API key em: Binance → Perfil → API Management
    Permissões necessárias: Read Info + Spot & Margin Trading (SEM saque)
    """
    BASE = "https://api.binance.com"
    TESTNET = "https://testnet.binance.vision"

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base = self.TESTNET if testnet else self.BASE
        self.conta_id = "binance"

    def _assinar(self, params: Dict) -> str:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    async def _get_privado(self, path: str, params: Dict = None) -> Optional[Dict]:
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        params["signature"] = self._assinar(params)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base}{path}",
                    headers={"X-MBX-APIKEY": self.api_key}, params=params, timeout=10)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.error(f"Binance GET {path}: {e}")
            return None

    async def _post_privado(self, path: str, params: Dict) -> Optional[Dict]:
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        params["signature"] = self._assinar(params)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{self.base}{path}",
                    headers={"X-MBX-APIKEY": self.api_key}, params=params, timeout=10)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.error(f"Binance POST {path}: {e}")
            return None

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base}/api/v3/ping", timeout=5)
                return r.status_code == 200
        except:
            return False

    async def get_saldo(self) -> Dict[str, float]:
        data = await self._get_privado("/api/v3/account")
        if not data:
            return {}
        return {b["asset"]: float(b["free"])
                for b in data.get("balances", [])
                if float(b.get("free", 0)) > 0}

    async def get_preco(self, symbol: str) -> Optional[float]:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base}/api/v3/ticker/price",
                    params={"symbol": symbol}, timeout=5)
                r.raise_for_status()
                return float(r.json()["price"])
        except Exception as e:
            logger.error(f"Binance preço {symbol}: {e}")
            return None

    async def get_precos_multiplos(self, symbols: List[str]) -> Dict[str, float]:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base}/api/v3/ticker/price", timeout=5)
                r.raise_for_status()
                return {t["symbol"]: float(t["price"])
                        for t in r.json()
                        if t["symbol"] in symbols}
        except Exception as e:
            logger.error(f"Binance preços: {e}")
            return {}

    async def get_historico(self, symbol: str, limit: int = 100) -> List[Dict]:
        data = await self._get_privado("/api/v3/myTrades",
                                       {"symbol": symbol, "limit": limit})
        return data or []

    async def criar_ordem_market(self, symbol: str, side: str, quantity: float) -> Dict:
        # side: "BUY" ou "SELL"
        pode, motivo = hodl_manager.verificar_proposta(
            self.conta_id, symbol.replace("USDT","").replace("BRL","").replace("BTC",""))
        if not pode:
            return {"sucesso": False, "erro": motivo, "hodl_block": True}

        data = await self._post_privado("/api/v3/order", {
            "symbol": symbol, "side": side,
            "type": "MARKET", "quantity": f"{quantity:.8f}",
        })
        if not data:
            return {"sucesso": False, "erro": "Falha na API Binance"}

        preco = float(data.get("fills",[{}])[0].get("price",0)) if data.get("fills") else 0
        return {
            "sucesso": True,
            "ordem_id": str(data.get("orderId","")),
            "symbol": symbol, "side": side,
            "quantidade": float(data.get("executedQty",0)),
            "preco": preco,
            "valor": preco * float(data.get("executedQty",0)),
            "taxa": sum(float(f.get("commission",0)) for f in data.get("fills",[])),
            "mensagem": f"Binance {side} {quantity} {symbol} executado",
        }

    async def criar_ordem_limit(self, symbol: str, side: str,
                                 quantity: float, price: float) -> Dict:
        pode, motivo = hodl_manager.verificar_proposta(
            self.conta_id, symbol.replace("USDT","").replace("BRL",""))
        if not pode:
            return {"sucesso": False, "erro": motivo, "hodl_block": True}

        data = await self._post_privado("/api/v3/order", {
            "symbol": symbol, "side": side, "type": "LIMIT",
            "timeInForce": "GTC", "quantity": f"{quantity:.8f}",
            "price": f"{price:.8f}",
        })
        if not data:
            return {"sucesso": False, "erro": "Falha na API Binance"}
        return {"sucesso": True, "ordem_id": str(data.get("orderId","")),
                "status": data.get("status",""), "mensagem": f"Ordem limit {side} criada"}

    async def cancelar_ordem(self, symbol: str, order_id: str) -> Dict:
        data = await self._post_privado("/api/v3/order/delete",
                                        {"symbol": symbol, "orderId": order_id})
        return {"sucesso": bool(data), "dados": data}

    async def get_ordens_abertas(self, symbol: Optional[str] = None) -> List[Dict]:
        params = {}
        if symbol:
            params["symbol"] = symbol
        data = await self._get_privado("/api/v3/openOrders", params)
        return data or []


# ── Coinbase Advanced Trade API ───────────────────────────────────────────────

class CoinbaseClient:
    """
    Coinbase Advanced Trade API
    Docs: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview
    Auth: JWT com ECDSA key (diferente do HMAC)
    Criar em: Coinbase → Apps (grid icon) → Developer Platform → API Keys
    Permissões: View + Trade (SEM Transfer)
    """
    BASE = "https://api.coinbase.com"

    def __init__(self, api_key_name: str, api_key_private: str):
        self.api_key_name = api_key_name      # ex: "organizations/xxx/apiKeys/yyy"
        self.api_key_private = api_key_private # PEM EC PRIVATE KEY
        self.conta_id = "coinbase"

    def _gerar_jwt(self, method: str, path: str) -> str:
        """
        JWT com ECDSA para autenticação Coinbase Advanced Trade.
        Em produção: usar biblioteca coinbase-advanced-py ou cryptography.
        """
        try:
            import jwt as pyjwt
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            private_key = load_pem_private_key(
                self.api_key_private.encode(), password=None)
            payload = {
                "sub": self.api_key_name,
                "iss": "coinbase-cloud",
                "nbf": int(time.time()),
                "exp": int(time.time()) + 120,
                "uri": f"{method} api.coinbase.com{path}",
            }
            return pyjwt.encode(payload, private_key, algorithm="ES256",
                              headers={"kid": self.api_key_name, "nonce": str(int(time.time()*1000))})
        except Exception as e:
            logger.error(f"Coinbase JWT: {e}")
            return ""

    async def _request(self, method: str, path: str, body: Dict = None) -> Optional[Dict]:
        token = self._gerar_jwt(method.upper(), path)
        if not token:
            return None
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {token}",
                          "Content-Type": "application/json"}
                if method.upper() == "GET":
                    r = await client.get(f"{self.BASE}{path}",
                                        headers=headers, timeout=10)
                else:
                    r = await client.post(f"{self.BASE}{path}",
                                         headers=headers,
                                         json=body or {}, timeout=10)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.error(f"Coinbase {method} {path}: {e}")
            return None

    async def get_saldo(self) -> Dict[str, float]:
        data = await self._request("GET", "/api/v3/brokerage/accounts")
        if not data:
            return {}
        saldos = {}
        for acc in data.get("accounts", []):
            currency = acc.get("currency","")
            valor = float(acc.get("available_balance",{}).get("value",0))
            if valor > 0:
                saldos[currency] = valor
        return saldos

    async def get_preco(self, product_id: str) -> Optional[float]:
        # product_id: ex "BTC-USD", "ETH-USD"
        data = await self._request("GET", f"/api/v3/brokerage/products/{product_id}")
        if not data:
            return None
        return float(data.get("price","0") or 0)

    async def criar_ordem(self, product_id: str, side: str,
                           base_size: str, order_type: str = "MARKET") -> Dict:
        ticker_base = product_id.split("-")[0]
        pode, motivo = hodl_manager.verificar_proposta(self.conta_id, ticker_base)
        if not pode:
            return {"sucesso": False, "erro": motivo, "hodl_block": True}

        import uuid
        body = {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": side,  # "BUY" ou "SELL"
            "order_configuration": {
                "market_market_ioc": {"base_size": base_size}
            } if order_type == "MARKET" else {}
        }
        data = await self._request("POST", "/api/v3/brokerage/orders", body)
        if not data:
            return {"sucesso": False, "erro": "Falha API Coinbase"}

        order = data.get("success_response", {})
        return {
            "sucesso": data.get("success", False),
            "ordem_id": order.get("order_id",""),
            "product_id": product_id,
            "side": side,
            "mensagem": f"Coinbase {side} {base_size} {product_id}",
        }

    async def get_portfolio(self) -> Dict:
        data = await self._request("GET", "/api/v3/brokerage/portfolios")
        return data or {}


# ── Crypto.com API v2 ─────────────────────────────────────────────────────────

class CryptoComClient:
    """
    Crypto.com Exchange API v2
    Docs: https://exchange-docs.crypto.com/spot/index.html
    Auth: HMAC-SHA256
    Criar em: Crypto.com Exchange → Settings → API Keys
    """
    BASE = "https://api.crypto.com/v2"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.conta_id = "crypto_com"

    def _assinar(self, method: str, params: dict, nonce: int) -> str:
        param_str = "".join(f"{k}{v}" for k, v in sorted(params.items()))
        payload = f"{method}{self.api_key}{param_str}{nonce}"
        return hmac.new(self.api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    async def _privado(self, method: str, params: dict = None) -> Optional[Dict]:
        params = params or {}
        nonce = int(time.time() * 1000)
        sig = self._assinar(method, params, nonce)
        body = {"id": nonce, "method": method, "api_key": self.api_key,
                "params": params, "sig": sig, "nonce": nonce}
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{self.BASE}/{method}",
                    json=body, timeout=10)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.error(f"Crypto.com {method}: {e}")
            return None

    async def get_saldo(self) -> Dict[str, float]:
        data = await self._privado("private/get-account-summary")
        if not data:
            return {}
        return {acc["currency"]: float(acc["available"])
                for acc in data.get("result",{}).get("accounts",[])
                if float(acc.get("available",0)) > 0}

    async def get_preco(self, instrument: str) -> Optional[float]:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.BASE}/public/get-ticker",
                    params={"instrument_name": instrument}, timeout=5)
                r.raise_for_status()
                return float(r.json()["result"]["data"]["a"])
        except Exception as e:
            logger.error(f"Crypto.com preço {instrument}: {e}")
            return None

    async def criar_ordem(self, instrument: str, side: str,
                           quantidade: float, tipo: str = "MARKET") -> Dict:
        ticker_base = instrument.split("_")[0]
        pode, motivo = hodl_manager.verificar_proposta(self.conta_id, ticker_base)
        if not pode:
            return {"sucesso": False, "erro": motivo, "hodl_block": True}

        params = {"instrument_name": instrument, "side": side,
                  "type": tipo, "quantity": str(quantidade)}
        data = await self._privado("private/create-order", params)
        if not data:
            return {"sucesso": False, "erro": "Falha API Crypto.com"}

        return {"sucesso": data.get("code") == 0,
                "ordem_id": str(data.get("result",{}).get("order_id","")),
                "mensagem": f"Crypto.com {side} {quantidade} {instrument}"}

    async def get_posicoes(self) -> List[Dict]:
        saldos = await self.get_saldo()
        return [{"ticker": t, "quantidade": q,
                 "bloqueado": hodl_manager.esta_bloqueado(self.conta_id, t)}
                for t, q in saldos.items()]


# ── MetaMask / Web3 (leitura de saldo) ───────────────────────────────────────

class MetaMaskReader:
    """
    Leitura de saldo de wallet Ethereum via Web3.py + Infura.
    MetaMask é uma wallet, não uma exchange — não tem API de trading.
    Para LEITURA: só precisa do endereço público (0x...).
    Para OPERAR: os robôs usam Binance/Coinbase/Crypto.com.
    Criar API key Infura em: https://infura.io (free tier = 100k req/dia)
    """

    # Contratos ERC-20 mais comuns
    ERC20_CONTRATOS = {
        "USDT":  "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC":  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "WBTC":  "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "LINK":  "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "UNI":   "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "SHIB":  "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE",
        "ELON":  "0x761D38e5ddf6ccf6Cf7c55759d5210750B5D60F3",  # Dogelon Mars
        "MATIC": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
    }

    ERC20_ABI = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],
                  "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],
                  "type":"function"}]

    def __init__(self, infura_project_id: str, network: str = "mainnet"):
        self.infura_url = f"https://{network}.infura.io/v3/{infura_project_id}"
        self._web3 = None

    def _get_web3(self):
        if not self._web3:
            try:
                from web3 import Web3
                self._web3 = Web3(Web3.HTTPProvider(self.infura_url))
            except ImportError:
                logger.error("web3 não instalado — rode: pip install web3")
        return self._web3

    async def get_saldo_eth(self, address: str) -> Optional[float]:
        """Retorna saldo ETH de um endereço público."""
        def _read():
            w3 = self._get_web3()
            if not w3:
                return None
            try:
                checksum = w3.to_checksum_address(address)
                balance_wei = w3.eth.get_balance(checksum)
                return float(w3.from_wei(balance_wei, "ether"))
            except Exception as e:
                logger.error(f"Web3 ETH balance {address}: {e}")
                return None
        return await asyncio.to_thread(_read)

    async def get_saldo_token(self, address: str, token_symbol: str) -> Optional[float]:
        """Retorna saldo de token ERC-20 (USDT, USDC, WBTC, ELON, etc.)."""
        contrato = self.ERC20_CONTRATOS.get(token_symbol.upper())
        if not contrato:
            logger.warning(f"Contrato não mapeado: {token_symbol}")
            return None

        def _read():
            w3 = self._get_web3()
            if not w3:
                return None
            try:
                checksum_addr = w3.to_checksum_address(address)
                checksum_cont = w3.to_checksum_address(contrato)
                contract = w3.eth.contract(address=checksum_cont, abi=self.ERC20_ABI)
                balance = contract.functions.balanceOf(checksum_addr).call()
                # ERC-20 tem 18 decimais (exceto USDT/USDC = 6)
                decimais = 6 if token_symbol.upper() in ("USDT","USDC") else 18
                return float(balance) / (10 ** decimais)
            except Exception as e:
                logger.error(f"Web3 token {token_symbol} {address}: {e}")
                return None
        return await asyncio.to_thread(_read)

    async def get_portfolio_completo(self, address: str) -> Dict:
        """Retorna ETH + todos os tokens ERC-20 mapeados de um endereço."""
        tasks = {"ETH": self.get_saldo_eth(address)}
        for token in self.ERC20_CONTRATOS:
            tasks[token] = self.get_saldo_token(address, token)

        resultados = {}
        for token, coro in tasks.items():
            saldo = await coro
            if saldo and saldo > 0:
                resultados[token] = round(saldo, 8)

        # Verifica HODL locks
        for token in list(resultados.keys()):
            bloqueado = hodl_manager.esta_bloqueado("metamask", token)
            if bloqueado:
                resultados[f"{token}_hodl"] = True

        return {"address": address, "network": "ethereum", "saldos": resultados}


# ── Toro Investimentos (simulado) ─────────────────────────────────────────────

class ToroClient:
    """
    Toro Investimentos — sem API pública.
    Executor simulado completo com controle de saldo.
    Futuramente: Open Finance BR via BACEN.
    """
    def __init__(self):
        self.conta_id = "toro"
        self._saldo = {
            "BOVA11": 5000.0, "IVVB11": 3000.0,
            "HGLG11": 1500.0, "TESOURO": 8000.0, "BRL": 5000.0,
        }
        self._precos = {
            "BOVA11": 128.40, "IVVB11": 284.90,
            "HGLG11": 143.20, "TESOURO": 100.0,
        }

    async def get_saldo(self) -> Dict[str, float]:
        return dict(self._saldo)

    async def get_preco(self, ticker: str) -> Optional[float]:
        import random
        base = self._precos.get(ticker, 100.0)
        return round(base * (1 + random.uniform(-0.005, 0.005)), 2)

    async def criar_ordem(self, ticker: str, lado: str,
                           quantidade: float, preco: Optional[float] = None) -> Dict:
        pode, motivo = hodl_manager.verificar_proposta(self.conta_id, ticker)
        if not pode:
            return {"sucesso": False, "erro": motivo, "hodl_block": True}

        preco_exec = preco or await self.get_preco(ticker) or 100.0
        valor = quantidade * preco_exec

        if lado == "COMPRA":
            if self._saldo.get("BRL", 0) < valor:
                return {"sucesso": False, "erro": f"Saldo insuficiente: R${self._saldo.get('BRL',0):.2f}"}
            self._saldo["BRL"] = round(self._saldo.get("BRL",0) - valor, 2)
            self._saldo[ticker] = round(self._saldo.get(ticker,0) + quantidade, 4)
        else:
            if self._saldo.get(ticker, 0) < quantidade:
                return {"sucesso": False, "erro": f"Posição insuficiente em {ticker}"}
            self._saldo[ticker] = round(self._saldo.get(ticker,0) - quantidade, 4)
            self._saldo["BRL"] = round(self._saldo.get("BRL",0) + valor, 2)

        return {"sucesso": True, "ordem_id": f"TORO-{int(time.time()*1000)}",
                "ticker": ticker, "lado": lado, "quantidade": quantidade,
                "preco": preco_exec, "valor": round(valor, 2), "simulado": True,
                "mensagem": f"[SIMULADO] {lado} {quantidade} {ticker} @ R${preco_exec:.2f}"}

    async def realizar_parcial(self, ticker: str, lucro_pct: float,
                                percentual: float = 0.30, destino: str = "TESOURO") -> Dict:
        saldo = self._saldo.get(ticker, 0)
        if saldo <= 0:
            return {"sucesso": False, "erro": "Sem posição para realizar"}
        qtd_vender = round(saldo * percentual, 4)
        preco = await self.get_preco(ticker) or 100.0
        valor = qtd_vender * preco
        await self.criar_ordem(ticker, "VENDA", qtd_vender)
        return {"sucesso": True, "ticker": ticker, "qtd_vendida": qtd_vender,
                "valor_realizado": round(valor,2), "lucro_pct": round(lucro_pct*100,1),
                "percentual_vendido": round(percentual*100),
                "destino": destino,
                "mensagem": f"Realizado {percentual*100:.0f}% de {ticker} (+{lucro_pct*100:.1f}%) → {destino}"}


# ── Avenue (import CSV) ───────────────────────────────────────────────────────

class AvenueImporter:
    """
    Avenue — sem API pública.
    Importação de posições via CSV exportado da plataforma.
    Avenue → Relatórios → Posições → Exportar CSV
    """
    def __init__(self):
        self.conta_id = "avenue"
        self._posicoes: Dict[str, Dict] = {}

    def importar_csv(self, csv_content: str) -> List[Dict]:
        """
        Processa CSV de extrato da Avenue.
        Formato típico: Ticker, Quantidade, Preço Médio, Valor Total, Moeda
        """
        import csv, io
        posicoes = []
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            for row in reader:
                # Normaliza cabeçalhos (Avenue usa diferentes versões)
                ticker = (row.get("Ticker") or row.get("Symbol") or row.get("Ativo","")).strip().upper()
                qtd    = float((row.get("Quantity") or row.get("Quantidade") or "0").replace(",","."))
                pm     = float((row.get("Avg Price") or row.get("Preco Medio") or "0").replace(",","."))
                valor  = float((row.get("Market Value") or row.get("Valor Total") or str(qtd*pm)).replace(",","."))
                moeda  = (row.get("Currency") or row.get("Moeda") or "USD").strip().upper()

                if ticker and qtd > 0:
                    pos = {"ticker": ticker, "quantidade": qtd, "preco_medio": pm,
                           "valor_total": valor, "moeda": moeda,
                           "bloqueado": hodl_manager.esta_bloqueado(self.conta_id, ticker)}
                    posicoes.append(pos)
                    self._posicoes[ticker] = pos

            logger.info(f"Avenue: {len(posicoes)} posições importadas")
        except Exception as e:
            logger.error(f"Avenue CSV parse: {e}")
        return posicoes

    def get_posicoes(self) -> Dict[str, Dict]:
        return dict(self._posicoes)

    def get_valor_total_usd(self) -> float:
        return sum(p["valor_total"] for p in self._posicoes.values()
                   if p.get("moeda","USD") == "USD")


# ── Instâncias globais ─────────────────────────────────────────────────────────
# Em produção: instanciar por usuário com keys do banco (criptografadas)

toro_client     = ToroClient()
avenue_importer = AvenueImporter()

# Instâncias vazias — preenchidas com keys reais via endpoint /broker/configurar
binance_client   = BinanceClient("", "")
coinbase_client  = CoinbaseClient("", "")
cryptocom_client = CryptoComClient("", "")
metamask_reader  = MetaMaskReader("")   # infura project id

def _init_clientes():
    from app.core.config import settings
    global binance_client, cryptocom_client, coinbase_client, metamask_reader
    if settings.BINANCE_API_KEY:
        binance_client = BinanceClient(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
    if settings.CRYPTOCOM_API_KEY:
        cryptocom_client = CryptoComClient(settings.CRYPTOCOM_API_KEY, settings.CRYPTOCOM_API_SECRET)

_init_clientes()
