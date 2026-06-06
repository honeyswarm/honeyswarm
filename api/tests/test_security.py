"""Tests for C3 (JWT secret fail-fast) and C1 (role enforcement)."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import DEFAULT_JWT_SECRET, MIN_JWT_SECRET_LEN, Settings
from app.core.deps import require_roles


# --- C3: assert_secure -------------------------------------------------------

def test_assert_secure_rejects_default_secret():
    with pytest.raises(RuntimeError):
        Settings(JWT_SECRET=DEFAULT_JWT_SECRET).assert_secure()


def test_assert_secure_rejects_short_secret():
    with pytest.raises(RuntimeError):
        Settings(JWT_SECRET="x" * (MIN_JWT_SECRET_LEN - 1)).assert_secure()


def test_assert_secure_accepts_strong_secret():
    # Should not raise.
    Settings(JWT_SECRET="a" * MIN_JWT_SECRET_LEN).assert_secure()


def test_assert_secure_bypass_for_local_dev():
    # The escape hatch lets the default through.
    Settings(JWT_SECRET=DEFAULT_JWT_SECRET, ALLOW_INSECURE_JWT_SECRET=True).assert_secure()


# --- C1: require_roles -------------------------------------------------------

def _user(roles):
    # The checker only reads user.roles, so a lightweight stand-in avoids needing
    # an initialised Beanie document.
    return SimpleNamespace(roles=roles)


def test_require_roles_allows_matching_role():
    checker = require_roles("deploy")
    user = _user(["deploy"])
    assert asyncio.run(checker(user=user)) is user


def test_require_roles_admin_is_superuser():
    # An admin passes a check for a role it doesn't explicitly hold.
    checker = require_roles("deploy")
    user = _user(["admin"])
    assert asyncio.run(checker(user=user)) is user


def test_require_roles_denies_insufficient_role():
    checker = require_roles("deploy")
    user = _user(["user"])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(checker(user=user))
    assert exc.value.status_code == 403
