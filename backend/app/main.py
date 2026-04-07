"""
FinanMap Pro — Backend FastAPI v3
Novidades: Auth JWT+2FA, GA 7 genes, RSI/MACD/Bollinger, VaR/CVaR, >
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.routers import fire, portfolio, ai_advisor, market, onboarding
from app.routers import auth, robos, tecnico
from app.core.config import settings

app = FastAPI(
    title="FinanMap Pro API v3",
    description="GA 7 genes · RSI/MACD/BB · VaR/CVaR · Robôs com 2FA · Monte Carlo 10k",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routers originais
app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
app.include_router(fire.router,       prefix="/api/v1/fire",       tags=["FIRE Tracker"])
app.include_router(portfolio.router,  prefix="/api/v1/portfolio",  tags=["Portfólio"])
app.include_router(ai_advisor.router, prefix="/api/v1/ia",         tags=["IA Advisor"])
app.include_router(market.router,     prefix="/api/v1/market",     tags=["Market Data"])

# Novos routers v3
app.include_router(auth.router,    prefix="/api/v1/auth",    tags=["Autenticação"])
app.include_router(robos.router,   prefix="/api/v1/robos",   tags=["Robôs & Execução"])
app.include_router(tecnico.router, prefix="/api/v1/tecnico", tags=["Análise Técnica + VaR"])

@app.get("/", tags=["Health"])
async def root():
    return {"app":"FinanMap Pro","version":"3.0.0","status":"online",
            "novidades":["GA 7 genes","RSI/MACD/Bollinger","VaR/CVaR","Robôs 2FA","Auth JWT"]}

@app.get("/health", tags=["Health"])
async def health():
    return {"status":"healthy"}

from app.routers import hodl as hodl_router
app.include_router(hodl_router.router, prefix='/api/v1/hodl', tags=['HODL + Corretoras'])

from app.routers import state
app.include_router(state.router)

from app.routers import mercado
app.include_router(mercado.router)
from app.routers import wallets
app.include_router(wallets.router)
