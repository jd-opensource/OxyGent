from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.service import authenticate_user, create_token, decode_token

auth_router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@auth_router.post("/login")
def login(body: LoginRequest, request: Request):
    es = request.app.state.es
    user = authenticate_user(es, body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({
        "sub": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name", ""),
        "role": user.get("role", "user"),
    })
    return {"token": token, "user": user}


@auth_router.get("/me")
def me(request: Request):
    user = get_current_user(request)
    return user


_ANONYMOUS_ADMIN = {
    "id": "anonymous",
    "username": "anonymous",
    "display_name": "Anonymous",
    "role": "admin",
}


def get_current_user(request: Request) -> dict:
    from app.config import get_config
    if not get_config().auth.enabled:
        return _ANONYMOUS_ADMIN
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = auth_header[len("Bearer "):]
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return {
        "id": payload.get("sub", ""),
        "username": payload.get("username", ""),
        "display_name": payload.get("display_name", ""),
        "role": payload.get("role", "user"),
    }


def require_admin(request: Request) -> dict:
    from app.config import get_config
    if not get_config().auth.enabled:
        return _ANONYMOUS_ADMIN
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def resolve_bank_id(request: Request) -> str:
    """Resolve bank_name path param to bank_id. Also accepts bank_id directly as fallback."""
    bank_name = request.path_params.get("bank_name", "")
    if not bank_name:
        raise HTTPException(status_code=400, detail="bank_name is required")
    from app.services.bank_service import resolve_bank, get_bank
    es = request.app.state.es
    # Try by name first
    bank = resolve_bank(es, bank_name)
    if bank:
        return bank["id"]
    # Fallback: try as bank_id directly
    bank = get_bank(es, bank_name)
    if bank:
        return bank["id"]
    raise HTTPException(status_code=404, detail=f"Bank '{bank_name}' not found")
