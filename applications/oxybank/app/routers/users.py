from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.auth.dependencies import require_admin
from app.auth.service import hash_password

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "annotator"

class UserUpdate(BaseModel):
    display_name: str | None = None
    password: str | None = None
    role: str | None = None

@router.get("")
async def list_users(request: Request, user: dict = Depends(require_admin)):
    es = request.app.state.es
    result = es.search("users", size=1000)
    items = result.get("items", [])
    for item in items:
        item.pop("password_hash", None)
    return items

@router.post("")
async def create_user(data: UserCreate, request: Request, user: dict = Depends(require_admin)):
    es = request.app.state.es
    existing = es.search("users", query={"term": {"username": data.username}}, size=1)
    if existing.get("items"):
        raise HTTPException(400, "Username already exists")
    from datetime import datetime, timezone
    doc = {
        "username": data.username,
        "password_hash": hash_password(data.password),
        "display_name": data.display_name or data.username,
        "role": data.role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    import uuid
    user_id = str(uuid.uuid4())
    es.index_doc("users", doc, doc_id=user_id, refresh=True)
    doc["id"] = user_id
    doc.pop("password_hash", None)
    return doc

@router.put("/{user_id}")
async def update_user(user_id: str, data: UserUpdate, request: Request, user: dict = Depends(require_admin)):
    es = request.app.state.es
    existing = es.get_doc("users", user_id)
    if not existing:
        raise HTTPException(404, "User not found")
    updates = {}
    if data.display_name is not None:
        updates["display_name"] = data.display_name
    if data.role is not None:
        updates["role"] = data.role
    if data.password is not None:
        updates["password_hash"] = hash_password(data.password)
    if updates:
        es.update_doc("users", user_id, updates, refresh=True)
    result = es.get_doc("users", user_id)
    result.pop("password_hash", None)
    return result

@router.delete("/{user_id}")
async def delete_user(user_id: str, request: Request, user: dict = Depends(require_admin)):
    es = request.app.state.es
    existing = es.get_doc("users", user_id)
    if not existing:
        raise HTTPException(404, "User not found")
    if existing.get("username") == "admin":
        raise HTTPException(400, "Cannot delete admin user")
    es.delete_doc("users", user_id, refresh=True)
    return {"message": "User deleted"}
