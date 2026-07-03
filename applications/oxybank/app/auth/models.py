from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict


class UserInfo(BaseModel):
    username: str
    display_name: str = ""
    role: str = "user"
