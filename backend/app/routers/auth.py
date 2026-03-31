"""
Router: Autenticação — /api/v1/auth
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from app.services.auth_service import SupabaseAuth, criar_desafio_2fa, verificar_desafio_2fa

router = APIRouter()


class LoginInput(BaseModel):
    email: str
    password: str

class RegisterInput(BaseModel):
    email: str
    password: str
    nome: str = ""

class Refresh2FAInput(BaseModel):
    user_id: str
    token: str
    operacao: str


@router.post("/register", summary="Registrar novo usuário")
async def register(payload: RegisterInput):
    try:
        result = await SupabaseAuth.registrar(payload.email, payload.password)
        return {"message": "Usuário criado. Verifique seu email.", "user_id": result.get("id")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", summary="Login com email e senha")
async def login(payload: LoginInput):
    session = await SupabaseAuth.login(payload.email, payload.password)
    if not session:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return {
        "access_token":  session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at":    session.expires_at.isoformat(),
        "user_id":       session.user_id,
        "email":         session.email,
    }


@router.post("/refresh", summary="Renovar access token")
async def refresh_token(refresh_token: str):
    session = await SupabaseAuth.refresh(refresh_token)
    if not session:
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    return {"access_token": session.access_token, "expires_at": session.expires_at.isoformat()}


@router.post("/2fa/challenge", summary="Criar desafio 2FA para operação de robô")
async def criar_challenge(user_id: str, operacao: str):
    token = criar_desafio_2fa(user_id, operacao)
    return {
        "message": f"Token 2FA gerado para operação '{operacao}'",
        "dev_token": token,  # REMOVER em produção — enviar via SMS
        "expira_em": "5 minutos",
    }


@router.post("/2fa/verify", summary="Verificar token 2FA")
async def verificar_2fa(payload: Refresh2FAInput):
    aprovado, msg = verificar_desafio_2fa(payload.user_id, payload.token, payload.operacao)
    if not aprovado:
        raise HTTPException(status_code=403, detail=msg)
    return {"aprovado": True, "mensagem": msg}
