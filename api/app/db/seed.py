"""First-run seeding: roles + bootstrap admin user."""
import logging

from app.core.config import settings
from app.core.security import hash_password
from app.models import Role, User

logger = logging.getLogger(__name__)

DEFAULT_ROLES = {
    "admin": "Full administrative access",
    "user": "Standard read access",
    "editor": "Can edit honeypot definitions",
    "deploy": "Can deploy honeypots to hives",
}


async def seed() -> None:
    for name, description in DEFAULT_ROLES.items():
        if await Role.find_one(Role.name == name) is None:
            await Role(name=name, description=description).insert()

    if await User.find_one() is not None:
        return  # users already exist; nothing to bootstrap

    if not settings.admin_password:
        logger.warning(
            "No users exist and ADMIN_PASSWORD is not set; skipping admin bootstrap. "
            "Set ADMIN_EMAIL/ADMIN_PASSWORD and restart to create the first admin."
        )
        return

    admin = User(
        email=settings.admin_email,
        name="Administrator",
        password=hash_password(settings.admin_password),
        active=True,
        roles=["admin"],
    )
    await admin.insert()
    logger.info("Bootstrapped admin user %s", settings.admin_email)
