"""
FinanMap Pro — Auth Service
Supabase Auth: JWT + refresh tokens + 2FA para operações de robôs
"""

import hmac
import hashlib
import base64
import time
import struct
import os
import httpx
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class UserSession:
    user_id:      str
    email:        str
    access_token: str
    refresh_token:str
    expires_at:   datetime
    perfil_risco: Optional[str] = None
    score_risco:  Optional[int] = None


@dataclass
class TwoFAChallenge:
    user_id:    str
    operacao:   str        # "robo_executar", "rebalancear", "stop_loss"
    token_hash: str
    expires_at: datetime
    confirmado: bool = False


# ── TOTP (Time-based One-Time Password) ──────────────────────────────────────

def gerar_totp(secret_b32: str, step: int = 30) -> str:
    """
    Gera TOTP compatível com Google Authenticator.
    RFC 6238 — HOTP com contador baseado em tempo.
    """
    try:
        # Decodifica segredo Base32
        key = base64.b32decode(secret_b32.upper() + '=' * (-len(secret_b32) % 8))
        # Contador de tempo
        counter = int(time.time()) // step
        msg = struct.pack('>Q', counter)
        # HMAC-SHA1
        h = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code = (struct.unpack('>I', h[offset:offset+4])[0] & 0x7FFFFFFF) % 1_000_000
        return f"{code:06d}"
    except Exception as e:
        logger.error(f"TOTP error: {e}")
        return "000000"


def verificar_totp(secret_b32: str, codigo: str, janela: int = 1) -> bool:
    """
    Verifica TOTP com janela de ±1 período (tolerância de 30s cada lado).
    """
    step = 30
    try:
        key = base64.b32decode(secret_b32.upper() + '=' * (-len(secret_b32) % 8))
        counter_base = int(time.time()) // step
        for delta in range(-janela, janela + 1):
            counter = counter_base + delta
            msg = struct.pack('>Q', counter)
            h = hmac.new(key, msg, hashlib.sha1).digest()
            offset = h[-1] & 0x0F
            code = (struct.unpack('>I', h[offset:offset+4])[0] & 0x7FFFFFFF) % 1_000_000
            if f"{code:06d}" == str(codigo).strip():
                return True
    except Exception as e:
        logger.error(f"TOTP verify error: {e}")
    return False


def gerar_secret_totp() -> str:
    """Gera um segredo TOTP Base32 aleatório."""
    return base64.b32encode(os.urandom(20)).decode().rstrip('=')


# ── Supabase Auth ─────────────────────────────────────────────────────────────

class SupabaseAuth:
    """
    Wrapper para Supabase Auth API.
    Em produção: usar supabase-py client.
    """

    BASE = settings.SUPABASE_URL + "/auth/v1"
    HEADERS = {
        "apikey":       settings.SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }

    @classmethod
    async def registrar(cls, email: str, password: str) -> Dict:
        """POST /auth/v1/signup"""
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{cls.BASE}/signup",
                headers=cls.HEADERS,
                json={"email": email, "password": password},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()

    @classmethod
    async def login(cls, email: str, password: str) -> Optional[UserSession]:
        """POST /auth/v1/token?grant_type=password"""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{cls.BASE}/token?grant_type=password",
                    headers=cls.HEADERS,
                    json={"email": email, "password": password},
                    timeout=10,
                )
                r.raise_for_status()
                data = r.json()
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
                return UserSession(
                    user_id=data["user"]["id"],
                    email=data["user"]["email"],
                    access_token=data["access_token"],
                    refresh_token=data["refresh_token"],
                    expires_at=expires_at,
                )
        except Exception as e:
            logger.error(f"Supabase login error: {e}")
            return None

    @classmethod
    async def refresh(cls, refresh_token: str) -> Optional[UserSession]:
        """POST /auth/v1/token?grant_type=refresh_token"""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{cls.BASE}/token?grant_type=refresh_token",
                    headers=cls.HEADERS,
                    json={"refresh_token": refresh_token},
                    timeout=10,
                )
                r.raise_for_status()
                data = r.json()
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
                return UserSession(
                    user_id=data["user"]["id"],
                    email=data["user"]["email"],
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token", refresh_token),
                    expires_at=expires_at,
                )
        except Exception as e:
            logger.error(f"Supabase refresh error: {e}")
            return None

    @classmethod
    async def verificar_token(cls, access_token: str) -> Optional[Dict]:
        """GET /auth/v1/user — verifica e decodifica o JWT."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{cls.BASE}/user",
                    headers={**cls.HEADERS, "Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    return r.json()
        except Exception as e:
            logger.error(f"Supabase verify error: {e}")
        return None


# ── 2FA para operações de Robôs ───────────────────────────────────────────────

# Cache em memória (produção: Redis com TTL)
_desafios_2fa: Dict[str, TwoFAChallenge] = {}


def criar_desafio_2fa(user_id: str, operacao: str) -> str:
    """
    Cria um desafio 2FA para operação sensível de robô.
    Retorna o token de 6 dígitos (enviado por SMS/email em produção).
    Em dev: retornado diretamente.
    """
    token = f"{int(time.time() * 1000) % 1_000_000:06d}"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)

    _desafios_2fa[user_id] = TwoFAChallenge(
        user_id=user_id,
        operacao=operacao,
        token_hash=token_hash,
        expires_at=expires,
    )

    logger.info(f"2FA challenge criado para {user_id} — operação: {operacao}")
    return token   # Em prod: enviar via SMS/email, não retornar


def verificar_desafio_2fa(user_id: str, token: str, operacao: str) -> Tuple[bool, str]:
    """
    Verifica o token 2FA.
    Retorna (aprovado, mensagem).
    """
    desafio = _desafios_2fa.get(user_id)

    if not desafio:
        return False, "Nenhum desafio 2FA pendente"

    if desafio.operacao != operacao:
        return False, f"Desafio é para operação '{desafio.operacao}', não '{operacao}'"

    if datetime.now(timezone.utc) > desafio.expires_at:
        del _desafios_2fa[user_id]
        return False, "Desafio 2FA expirado (5 minutos)"

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if not hmac.compare_digest(token_hash, desafio.token_hash):
        return False, "Token 2FA inválido"

    # Aprovado — remove desafio (one-time use)
    del _desafios_2fa[user_id]
    return True, "2FA aprovado"


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

from fastapi import HTTPException, Depends, Header


async def get_current_user(authorization: str = Header(None)) -> Dict:
    """
    Dependency do FastAPI — valida Bearer token do Supabase.
    Uso: endpoint(..., user=Depends(get_current_user))
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticação ausente")

    token = authorization.split(" ", 1)[1]
    user = await SupabaseAuth.verificar_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    return user


async def require_2fa(
    operacao: str,
    user_id: str,
    token_2fa: Optional[str] = None,
) -> bool:
    """
    Dependency — exige 2FA para operações de robôs.
    Se token_2fa não fornecido, cria desafio e lança exceção com instruções.
    """
    if not token_2fa:
        token = criar_desafio_2fa(user_id, operacao)
        # Em produção: enviar via SMS/email
        raise HTTPException(
            status_code=202,
            detail={
                "message": f"2FA necessário para '{operacao}'. Token enviado por SMS.",
                "dev_token": token,  # Remover em produção
                "operacao": operacao,
            }
        )

    aprovado, msg = verificar_desafio_2fa(user_id, token_2fa, operacao)
    if not aprovado:
        raise HTTPException(status_code=403, detail=f"2FA falhou: {msg}")

    return True
