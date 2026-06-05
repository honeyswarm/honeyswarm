"""Authentication: login, refresh, register, me.

Replaces the Flask-Security session login. JWT access + refresh tokens.
New users register inactive and must be activated by an admin (mirrors the old
behaviour). Login does not distinguish "no such user" from "wrong password",
fixing the username-enumeration issue flagged in the legacy auth.py.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.core.security import (
    REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _user_public(user: User) -> dict[str, Any]:
    return {"id": str(user.id), "email": user.email, "name": user.name, "roles": user.roles, "active": user.active}


def _tokens(user: User) -> dict[str, Any]:
    return {
        "access_token": create_access_token(str(user.id), user.roles),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
        "user": _user_public(user),
    }


@router.post("/login")
async def login(body: LoginRequest) -> dict[str, Any]:
    user = await User.find_one(User.email == body.email)
    # Constant-ish behaviour: same error whether user missing or password wrong.
    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is not active")
    return _tokens(user)


@router.post("/register", status_code=201)
async def register(body: RegisterRequest) -> dict[str, Any]:
    if await User.find_one(User.email == body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=body.email,
        name=body.name,
        password=hash_password(body.password),
        active=False,  # admin must activate
        roles=["user"],
    )
    await user.insert()
    return {"message": "Registered. An administrator must activate your account.", "user": _user_public(user)}


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> dict[str, Any]:
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != REFRESH:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = await User.get(payload["sub"])
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or not found")
    return _tokens(user)


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return _user_public(user)
