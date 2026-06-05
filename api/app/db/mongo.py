"""MongoDB / Beanie initialisation.

Beanie 2.x uses PyMongo's native async client (``AsyncMongoClient``); Motor is
no longer used.
"""
import logging

from beanie import init_beanie
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.models import DOCUMENT_MODELS

logger = logging.getLogger(__name__)

_client: AsyncMongoClient | None = None


async def init_mongo() -> AsyncMongoClient:
    """Connect to Mongo and bind Beanie document models."""
    global _client
    logger.info("Connecting to MongoDB at %s:%s", settings.mongodb_host, settings.mongodb_port)
    _client = AsyncMongoClient(settings.mongodb_uri)
    await init_beanie(
        database=_client[settings.mongodb_database],
        document_models=DOCUMENT_MODELS,
    )
    return _client


async def close_mongo() -> None:
    global _client
    if _client is not None:
        logger.info("Closing MongoDB connection")
        await _client.close()
        _client = None
