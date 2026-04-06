# backend/app/routers/state.py
# Persiste dados do frontend (contas, patrimônio) em ficheiro JSON local
# Simples e sem dependência de base de dados

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
import json
import os

router = APIRouter(prefix="/api/v1/state", tags=["state"])

# Ficheiro de dados — fica na pasta do backend
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "state.json")

def carregar_state() -> dict:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def salvar_state(data: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class StateItem(BaseModel):
    key: str
    value: Any

@router.get("/{key}")
def get_state(key: str):
    data = carregar_state()
    if key not in data:
        return {"key": key, "value": None, "found": False}
    return {"key": key, "value": data[key], "found": True}

@router.post("/")
def set_state(item: StateItem):
    data = carregar_state()
    data[item.key] = item.value
    salvar_state(data)
    return {"key": item.key, "saved": True}

@router.delete("/{key}")
def delete_state(key: str):
    data = carregar_state()
    if key in data:
        del data[key]
        salvar_state(data)
    return {"key": key, "deleted": True}

@router.get("/")
def list_keys():
    data = carregar_state()
    return {"keys": list(data.keys())}
