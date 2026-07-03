from __future__ import annotations

import logging
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_config
from app.storage.es_client import ESClient

logger = logging.getLogger("oxybank.auth")

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def create_token(data: dict) -> str:
    cfg = get_config().auth
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=cfg.token_expire_hours)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, cfg.secret_key, algorithm=cfg.algorithm)


def decode_token(token: str) -> dict | None:
    cfg = get_config().auth
    try:
        payload = jwt.decode(token, cfg.secret_key, algorithms=[cfg.algorithm])
        return payload
    except JWTError:
        return None


def authenticate_user(es_client: ESClient, username: str, password: str) -> dict | None:
    result = es_client.search(
        "users",
        query={"term": {"username": username}},
        size=1,
    )
    items = result.get("items", [])
    if not items:
        return None
    user = items[0]
    if not verify_password(password, user.get("password_hash", "")):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name", ""),
        "role": user.get("role", "user"),
    }


def init_admin_user(es_client: ESClient) -> None:
    count = es_client.count("users")
    if count > 0:
        return
    admin_doc = {
        "username": "admin",
        "password_hash": hash_password("admin"),
        "display_name": "Administrator",
        "role": "admin",
        "created_at": datetime.utcnow().isoformat(),
    }
    es_client.index_doc("users", admin_doc, refresh=True)
    logger.info("Created default admin user (admin/admin)")
