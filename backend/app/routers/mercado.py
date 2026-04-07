# backend/app/routers/mercado.py
# Análise de qualquer ativo em tempo real: yfinance + Binance + Claude AI

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os

router = APIRouter(prefix="/api/v1/mercado", tags=["mercado"])
logger = logging.getLogger(__name__)

# ── Mapeamento de tickers ──────────────────────────────────────────────────────

CRIPTO_SYMBOLS = {
    'BTC','ETH','BNB','SOL','XRP','ADA','AVAX','DOT','MATIC','LINK',
    'UNI','ATOM','LTC','BCH','ALGO','VET','ICP','FIL','THETA','EOS',
    'DOGE','SHIB','PEPE','WIF','BONK','CRO','ELON','FLOKI'
}

ACOES_BR_SUFFIX = '.SA'
ACOES_EUA_SUFFIX = ''

def detectar_tipo_e_ticker(ticker: str) -> dict:
    """Detecta o tipo de ativo e formata o ticker para yfinance/Binance."""
    t = ticker.upper().strip()

    # Cripto
    base = t.replace('USDT','').replace('BRL','').replace('-USD','').replace('/USD','')
    if base in CRIPTO_SYMBOLS or t.endswith('USDT') or t.endswith('-USD'):
        symbol_binance = base + 'USDT'
        symbol_yfinance = base + '-USD'
        return {
            'tipo': 'cripto',
            'ticker_original': t,
            'ticker_binance': symbol_binance,
            'ticker_yfinance': symbol_yfinance,
            'nome': base,
            'moeda': 'USD'
        }

    # BDRs (ex: AAPL34, MSFT34, AMZO34, GOGL34) — 4 letras + 2 dígitos
    if len(t) == 6 and t[:4].isalpha() and t[4:].isdigit() and t[4:] not in ('11','12','13'):
        return {
            'tipo': 'bdr',
            'ticker_original': t,
            'ticker_yfinance': t + ACOES_BR_SUFFIX,
            'nome': t,
            'moeda': 'BRL'
        }

    # FIIs brasileiros (terminam em 11, 12)
    if len(t) == 6 and t[4:] in ('11','12','13'):
        return {
            'tipo': 'fii',
            'ticker_original': t,
            'ticker_yfinance': t + ACOES_BR_SUFFIX,
            'nome': t,
            'moeda': 'BRL'
        }

    # Ações BR (4 letras + 1 número)
    if len(t) == 5 and t[:4].isalpha() and t[4].isdigit():
        return {
            'tipo': 'acao_br',
            'ticker_original': t,
            'ticker_yfinance': t + ACOES_BR_SUFFIX,
            'nome': t,
            'moeda': 'BRL'
        }

    # ETFs BR (4-6 letras + 11)
    if t.endswith('11') and len(t) <= 7:
        return {
            'tipo': 'etf_br',
            'ticker_original': t,
            'ticker_yfinance': t + ACOES_BR_SUFFIX,
            'nome': t,
            'moeda': 'BRL'
        }

    # Acções EUA (1-5 letras)
    if t.isalpha() and len(t) <= 5:
        return {
            'tipo': 'acao_eua',
            'ticker_original': t,
            'ticker_yfinance': t,
            'nome': t,
            'moeda': 'USD'
        }

    # Fallback — tentar como EUA
    return {
        'tipo': 'desconhecido',
        'ticker_original': t,
        'ticker_yfinance': t,
        'nome': t,
        'moeda': 'USD'
    }


async def buscar_precos_yfinance(ticker_yf: str, periodo: str = '3mo') -> dict:
    """Busca preços históricos via yfinance."""
    try:
        import yfinance as yf
        import requests
        # Headers para evitar bloqueio
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        stock = yf.Ticker(ticker_yf)
        hist = stock.history(period=periodo)
        # Se falhou, tentar período menor
        if hist.empty:
            hist = stock.history(period='1mo')

        if hist.empty:
            return {'erro': f'Sem dados para {ticker_yf}'}

        info = {}
        try:
            info = stock.info or {}
        except Exception:
            pass

        precos = hist['Close'].tolist()
        volumes = hist['Volume'].tolist() if 'Volume' in hist else []
        datas = [str(d.date()) for d in hist.index]

        return {
            'precos': precos,
            'volumes': volumes,
            'datas': datas,
            'preco_atual': precos[-1] if precos else 0,
            'preco_abertura': hist['Open'].iloc[-1] if not hist.empty else 0,
            'preco_max': hist['High'].iloc[-1] if not hist.empty else 0,
            'preco_min': hist['Low'].iloc[-1] if not hist.empty else 0,
            'volume': volumes[-1] if volumes else 0,
            'nome_completo': info.get('longName') or info.get('shortName') or ticker_yf,
            'setor': info.get('sector','—'),
            'market_cap': info.get('marketCap', 0),
            'pe_ratio': info.get('trailingPE', 0),
            'dividend_yield': info.get('dividendYield', 0),
            'variacao_24h': ((precos[-1] - precos[-2]) / precos[-2] * 100) if len(precos) >= 2 else 0,
            'variacao_30d': ((precos[-1] - precos[-22]) / precos[-22] * 100) if len(precos) >= 22 else 0,
        }
    except Exception as e:
        logger.error(f"yfinance erro {ticker_yf}: {e}")
        return {'erro': str(e)}


async def buscar_precos_binance(symbol: str) -> dict:
    """Busca preços de cripto via Binance API pública."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=90"
            async with session.get(url) as r:
                klines = await r.json()

        precos = [float(k[4]) for k in klines]  # Close price
        volumes = [float(k[5]) for k in klines]
        datas = [str(__import__('datetime').datetime.fromtimestamp(k[0]/1000).date()) for k in klines]

        variacao_24h = ((precos[-1] - precos[-2]) / precos[-2] * 100) if len(precos) >= 2 else 0
        variacao_30d = ((precos[-1] - precos[-22]) / precos[-22] * 100) if len(precos) >= 22 else 0

        return {
            'precos': precos,
            'volumes': volumes,
            'datas': datas,
            'preco_atual': precos[-1],
            'preco_abertura': float(klines[-1][1]),
            'preco_max': float(klines[-1][2]),
            'preco_min': float(klines[-1][3]),
            'volume': volumes[-1],
            'nome_completo': symbol.replace('USDT',' / USDT'),
            'variacao_24h': variacao_24h,
            'variacao_30d': variacao_30d,
        }
    except Exception as e:
        logger.error(f"Binance erro {symbol}: {e}")
        return {'erro': str(e)}


async def buscar_coingecko(coin_id: str) -> dict:
    """Busca cripto desconhecida via CoinGecko API (gratuita, sem key)."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Buscar por ID ou símbolo
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id.lower()}/market_chart?vs_currency=usd&days=90"
            async with session.get(url, headers={'Accept':'application/json'}) as r:
                if r.status != 200:
                    return {'erro': f'CoinGecko: {r.status}'}
                data = await r.json()

            precos = [p[1] for p in data.get('prices', [])]
            if not precos:
                return {'erro': 'Sem dados CoinGecko'}

            # Info do coin
            url2 = f"https://api.coingecko.com/api/v3/coins/{coin_id.lower()}?localization=false&tickers=false&community_data=false&developer_data=false"
            async with session.get(url2) as r2:
                info = await r2.json() if r2.status == 200 else {}

            preco_atual = precos[-1]
            var24h = ((precos[-1]-precos[-2])/precos[-2]*100) if len(precos)>=2 else 0
            var30d = ((precos[-1]-precos[-22])/precos[-22]*100) if len(precos)>=22 else 0

            return {
                'precos': precos[-90:],
                'volumes': [],
                'datas': [],
                'preco_atual': preco_atual,
                'preco_abertura': precos[-2] if len(precos)>=2 else preco_atual,
                'preco_max': max(precos[-1:]),
                'preco_min': min(precos[-1:]),
                'volume': 0,
                'nome_completo': info.get('name', coin_id),
                'variacao_24h': var24h,
                'variacao_30d': var30d,
                'market_cap': info.get('market_data',{}).get('market_cap',{}).get('usd',0),
            }
    except Exception as e:
        return {'erro': str(e)}


async def buscar_coingecko_por_simbolo(simbolo: str) -> dict:
    """Busca ID do coin no CoinGecko pelo símbolo (ex: PEPE, WIF, BONK)."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"https://api.coingecko.com/api/v3/search?query={simbolo.lower()}"
            async with session.get(url) as r:
                data = await r.json()
            coins = data.get('coins', [])
            if not coins:
                return {'erro': f'Coin {simbolo} não encontrado'}
            # Pegar o primeiro resultado
            coin_id = coins[0]['id']
            return await buscar_coingecko(coin_id)
    except Exception as e:
        return {'erro': str(e)}


async def analisar_com_ia(ticker_info: dict, dados_mercado: dict, analise_tecnica: dict) -> str:
    """Chama Claude API para gerar análise em linguagem natural."""
    try:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return "⚠️ Configure ANTHROPIC_API_KEY no .env para análise com IA."

        client = anthropic.Anthropic(api_key=api_key)

        preco = dados_mercado.get('preco_atual', 0)
        var24h = dados_mercado.get('variacao_24h', 0)
        var30d = dados_mercado.get('variacao_30d', 0)
        rsi = analise_tecnica.get('rsi', 50)
        sinal = analise_tecnica.get('sinal', 'neutro')
        forca = analise_tecnica.get('forca_sinal', 0)
        bb = analise_tecnica.get('bollinger', {})
        zscore = analise_tecnica.get('zscore', 0)
        hurst = analise_tecnica.get('hurst', 0.5)
        regime = analise_tecnica.get('regime', 'indefinido')
        tendencia = analise_tecnica.get('tendencia', '—')

        prompt = f"""Você é um analista financeiro especializado. Analise o ativo abaixo e responda em português brasileiro de forma clara e objectiva.

ATIVO: {ticker_info.get('nome')} ({ticker_info.get('tipo')})
Nome completo: {dados_mercado.get('nome_completo', '—')}
Setor: {dados_mercado.get('setor', '—')}

PREÇOS:
- Preço actual: {preco:.4f}
- Variação 24h: {var24h:+.2f}%
- Variação 30d: {var30d:+.2f}%
- Máx hoje: {dados_mercado.get('preco_max', 0):.4f}
- Mín hoje: {dados_mercado.get('preco_min', 0):.4f}

INDICADORES TÉCNICOS:
- RSI (14): {rsi:.1f} {"(sobrecomprado ⚠️)" if rsi > 70 else "(oversold 🟢)" if rsi < 30 else "(neutro)"}
- Sinal: {sinal.upper()} (força {forca*100:.0f}%)
- Bollinger: posição {bb.get('posicao', 0):.2f} (0=suporte, 1=resistência)
- Z-Score: {zscore:.2f}
- Hurst: {hurst:.2f} (>0.5=trending, <0.5=mean-reverting)
- Regime: {regime}
- Tendência: {tendencia}

Responda com exactamente estas 5 secções (seja conciso, máx 3 linhas cada):

🎯 VEREDICTO: [COMPRA FORTE / COMPRA / NEUTRO / VENDA / VENDA FORTE] - justificativa em 1-2 frases

📊 ANÁLISE TÉCNICA: Interprete os indicadores acima de forma clara para um investidor

💰 ENTRADA SUGERIDA: Preço ideal de entrada e porquê (baseado em suporte/Bollinger inferior)

🛡️ STOP LOSS: Nível de stop loss sugerido e percentagem de risco

⚡ OPORTUNIDADE: Existe alguma oportunidade específica agora? Catalisadores ou riscos a monitorar?"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    except Exception as e:
        logger.error(f"Claude API erro: {e}")
        return f"Erro na análise IA: {str(e)}"


# ── Endpoints ──────────────────────────────────────────────────────────────────

class AnaliseMercadoInput(BaseModel):
    ticker: str
    periodo: Optional[str] = '3mo'  # 1mo, 3mo, 6mo, 1y
    com_ia: Optional[bool] = True


@router.post("/analisar")
async def analisar_ativo_mercado(payload: AnaliseMercadoInput):
    """Analisa qualquer ativo em tempo real: preços + técnica + IA."""
    try:
        ticker_info = detectar_tipo_e_ticker(payload.ticker)
        logger.info(f"Analisando {payload.ticker} → tipo={ticker_info['tipo']}")

        # Buscar dados de mercado
        if ticker_info['tipo'] == 'cripto':
            dados = await buscar_precos_binance(ticker_info['ticker_binance'])
            if dados.get('erro'):
                # Fallback 1: yfinance
                dados = await buscar_precos_yfinance(ticker_info['ticker_yfinance'], payload.periodo)
            if dados.get('erro'):
                # Fallback 2: CoinGecko (para tokens obscuros)
                dados = await buscar_coingecko_por_simbolo(ticker_info['nome'])
        else:
            dados = await buscar_precos_yfinance(ticker_info['ticker_yfinance'], payload.periodo)
            # Se yfinance falhar, tentar com .SA para activos BR não detectados
            if dados.get('erro') and '.' not in ticker_info['ticker_yfinance']:
                dados = await buscar_precos_yfinance(ticker_info['ticker_yfinance'] + '.SA', payload.periodo)

        if dados.get('erro'):
            raise HTTPException(400, f"Não foi possível obter dados para {payload.ticker}: {dados['erro']}")

        precos = dados.get('precos', [])
        volumes = dados.get('volumes', [])

        if len(precos) < 14:
            raise HTTPException(400, f"Dados insuficientes para análise ({len(precos)} dias)")

        # Análise técnica
        from app.services.technical_service import analisar_ativo
        tecnica = analisar_ativo(ticker_info['nome'], precos, volumes if volumes else None)

        # Análise IA
        analise_ia = ""
        if payload.com_ia:
            analise_ia = await analisar_com_ia(ticker_info, dados, tecnica)

        return {
            'ticker': ticker_info['nome'],
            'ticker_original': payload.ticker,
            'tipo': ticker_info['tipo'],
            'nome_completo': dados.get('nome_completo', payload.ticker),
            'moeda': ticker_info.get('moeda', 'USD'),
            'setor': dados.get('setor', '—'),
            # Preços
            'preco_atual': dados.get('preco_atual', 0),
            'preco_abertura': dados.get('preco_abertura', 0),
            'preco_max': dados.get('preco_max', 0),
            'preco_min': dados.get('preco_min', 0),
            'volume': dados.get('volume', 0),
            'variacao_24h': dados.get('variacao_24h', 0),
            'variacao_30d': dados.get('variacao_30d', 0),
            'market_cap': dados.get('market_cap', 0),
            'pe_ratio': dados.get('pe_ratio', 0),
            'dividend_yield': dados.get('dividend_yield', 0),
            # Histórico para gráfico
            'precos_historico': precos[-60:],  # últimos 60 dias
            'datas_historico': dados.get('datas', [])[-60:],
            # Técnica
            'tecnica': tecnica,
            # IA
            'analise_ia': analise_ia,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao analisar {payload.ticker}: {e}")
        raise HTTPException(500, str(e))


@router.get("/sugestoes")
async def sugestoes_tickers(q: str = ""):
    """Retorna sugestões de tickers baseadas na pesquisa."""
    todos = [
        # Cripto
        {"ticker": "BTC", "nome": "Bitcoin", "tipo": "cripto"},
        {"ticker": "ETH", "nome": "Ethereum", "tipo": "cripto"},
        {"ticker": "SOL", "nome": "Solana", "tipo": "cripto"},
        {"ticker": "BNB", "nome": "BNB", "tipo": "cripto"},
        {"ticker": "XRP", "nome": "Ripple", "tipo": "cripto"},
        {"ticker": "ADA", "nome": "Cardano", "tipo": "cripto"},
        {"ticker": "AVAX", "nome": "Avalanche", "tipo": "cripto"},
        {"ticker": "DOGE", "nome": "Dogecoin", "tipo": "cripto"},
        {"ticker": "LINK", "nome": "Chainlink", "tipo": "cripto"},
        {"ticker": "DOT", "nome": "Polkadot", "tipo": "cripto"},
        # Ações BR
        {"ticker": "PETR4", "nome": "Petrobras", "tipo": "acao_br"},
        {"ticker": "VALE3", "nome": "Vale", "tipo": "acao_br"},
        {"ticker": "ITUB4", "nome": "Itaú Unibanco", "tipo": "acao_br"},
        {"ticker": "BBDC4", "nome": "Bradesco", "tipo": "acao_br"},
        {"ticker": "ABEV3", "nome": "Ambev", "tipo": "acao_br"},
        {"ticker": "WEGE3", "nome": "WEG", "tipo": "acao_br"},
        {"ticker": "RENT3", "nome": "Localiza", "tipo": "acao_br"},
        {"ticker": "MGLU3", "nome": "Magazine Luiza", "tipo": "acao_br"},
        {"ticker": "BPAC11", "nome": "BTG Pactual", "tipo": "acao_br"},
        {"ticker": "BBAS3", "nome": "Banco do Brasil", "tipo": "acao_br"},
        # Ações EUA
        {"ticker": "AAPL", "nome": "Apple", "tipo": "acao_eua"},
        {"ticker": "NVDA", "nome": "NVIDIA", "tipo": "acao_eua"},
        {"ticker": "MSFT", "nome": "Microsoft", "tipo": "acao_eua"},
        {"ticker": "GOOGL", "nome": "Alphabet", "tipo": "acao_eua"},
        {"ticker": "AMZN", "nome": "Amazon", "tipo": "acao_eua"},
        {"ticker": "TSLA", "nome": "Tesla", "tipo": "acao_eua"},
        {"ticker": "META", "nome": "Meta", "tipo": "acao_eua"},
        {"ticker": "AMD", "nome": "AMD", "tipo": "acao_eua"},
        {"ticker": "PLTR", "nome": "Palantir", "tipo": "acao_eua"},
        {"ticker": "COIN", "nome": "Coinbase", "tipo": "acao_eua"},
        # ETFs
        {"ticker": "BOVA11", "nome": "ETF Ibovespa", "tipo": "etf_br"},
        {"ticker": "IVVB11", "nome": "ETF S&P500", "tipo": "etf_br"},
        {"ticker": "SPY", "nome": "SPDR S&P500", "tipo": "etf_eua"},
        {"ticker": "QQQ", "nome": "Nasdaq 100", "tipo": "etf_eua"},
        # BDRs
        {"ticker": "AAPL34", "nome": "Apple BDR", "tipo": "bdr"},
        {"ticker": "MSFT34", "nome": "Microsoft BDR", "tipo": "bdr"},
        {"ticker": "AMZO34", "nome": "Amazon BDR", "tipo": "bdr"},
        {"ticker": "GOGL34", "nome": "Google BDR", "tipo": "bdr"},
        {"ticker": "TSLA34", "nome": "Tesla BDR", "tipo": "bdr"},
        {"ticker": "NVDC34", "nome": "NVIDIA BDR", "tipo": "bdr"},
        # Bonds / Tesouro EUA
        {"ticker": "TLT", "nome": "Treasury 20+ anos", "tipo": "bond"},
        {"ticker": "BND", "nome": "Vanguard Total Bond", "tipo": "bond"},
        {"ticker": "HYG", "nome": "High Yield Bond", "tipo": "bond"},
        # REITs
        {"ticker": "VNQ", "nome": "Vanguard Real Estate", "tipo": "reit"},
        {"ticker": "O", "nome": "Realty Income", "tipo": "reit"},
        {"ticker": "AMT", "nome": "American Tower", "tipo": "reit"},
        # Fundos mútuos EUA
        {"ticker": "FXAIX", "nome": "Fidelity 500 Index", "tipo": "fundo"},
        {"ticker": "VFIAX", "nome": "Vanguard 500 Index", "tipo": "fundo"},
        {"ticker": "VTSAX", "nome": "Vanguard Total Stock", "tipo": "fundo"},
        # Cripto alternativas
        {"ticker": "PEPE", "nome": "Pepe", "tipo": "cripto"},
        {"ticker": "WIF", "nome": "dogwifhat", "tipo": "cripto"},
        {"ticker": "BONK", "nome": "Bonk", "tipo": "cripto"},
        {"ticker": "ARB", "nome": "Arbitrum", "tipo": "cripto"},
        {"ticker": "OP", "nome": "Optimism", "tipo": "cripto"},
        # FIIs
        {"ticker": "HGLG11", "nome": "CSHG Logística", "tipo": "fii"},
        {"ticker": "KNRI11", "nome": "Kinea Renda", "tipo": "fii"},
        {"ticker": "XPML11", "nome": "XP Malls", "tipo": "fii"},
        {"ticker": "VISC11", "nome": "Vinci Shopping", "tipo": "fii"},
        {"ticker": "MXRF11", "nome": "Maxi Renda", "tipo": "fii"},
    ]

    if not q:
        return {"sugestoes": todos[:10]}

    q_upper = q.upper()
    filtrado = [
        t for t in todos
        if q_upper in t['ticker'] or q_upper in t['nome'].upper()
    ][:8]

    return {"sugestoes": filtrado}
