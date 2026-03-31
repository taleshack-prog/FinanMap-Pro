from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "FinanMap Pro"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_ORIGINS: List[str] = ["*"]
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    DATABASE_URL: str = ""
    ALPHA_VANTAGE_KEY: str = ""
    YFINANCE_CACHE_TTL: int = 300
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    MONTE_CARLO_SIMS: int = 10_000
    MONTE_CARLO_MU: float = 0.12
    MONTE_CARLO_SIGMA: float = 0.18
    RISK_FREE_RATE: float = 0.105
    IBGE_MONTHLY_REFERENCE: float = 2_000.0
    REDIS_URL: str = ""
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    CRYPTOCOM_API_KEY: str = ""
    CRYPTOCOM_API_SECRET: str = ""
    COINBASE_API_KEY_NAME: str = ""
    COINBASE_API_PRIVATE: str = ""
    INFURA_PROJECT_ID: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
