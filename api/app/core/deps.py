"""Auth dependencies for protecting routes."""
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import ACCESS, decode_token
from app.models import User

bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> User:
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != ACCESS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = await User.get(payload["sub"])
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or not found")
    return user


def require_roles(*roles: str) -> Callable:
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not set(roles).intersection(user.roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return checker
