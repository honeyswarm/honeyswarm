"""Admin: user + role management. All routes require the 'admin' role.

Replaces the old admin blueprint (minus HPFeeds auth-keys, which are gone).
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import require_roles
from app.models import Role, User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles("admin"))])

VALID_ROLES = {"admin", "user", "editor", "deploy"}


class RolesUpdate(BaseModel):
    roles: list[str]


def _user_public(user: User) -> dict[str, Any]:
    return {"id": str(user.id), "email": user.email, "name": user.name, "roles": user.roles, "active": user.active}


@router.get("/users")
async def list_users() -> list[dict[str, Any]]:
    return [_user_public(u) async for u in User.find_all()]


@router.post("/users/{user_id}/activate")
async def activate_user(user_id: str) -> dict[str, Any]:
    user = await User.get(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.active = True
    await user.save()
    return _user_public(user)


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str) -> dict[str, Any]:
    user = await User.get(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.active = False
    await user.save()
    return _user_public(user)


@router.put("/users/{user_id}/roles")
async def set_roles(user_id: str, body: RolesUpdate) -> dict[str, Any]:
    invalid = set(body.roles) - VALID_ROLES
    if invalid:
        raise HTTPException(400, f"Invalid roles: {sorted(invalid)}")
    user = await User.get(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.roles = body.roles
    await user.save()
    return _user_public(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str) -> None:
    user = await User.get(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    await user.delete()


@router.get("/roles")
async def list_roles() -> list[dict[str, Any]]:
    roles = [{"name": r.name, "description": r.description} async for r in Role.find_all()]
    return roles or [{"name": r, "description": None} for r in sorted(VALID_ROLES)]
