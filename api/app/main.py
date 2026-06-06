"""FastAPI application factory and lifespan.

Replaces honeyswarm/honeyswarm/honeyswarm/__init__.py (Flask app factory +
APScheduler). Startup wires Mongo (Beanie), OpenSearch, and the MQTT ingest
service; shutdown tears them down cleanly.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.mongo import close_mongo, init_mongo
from app.db.opensearch import (
    close_opensearch,
    ensure_dashboards_index_pattern,
    init_opensearch,
)
from app.db.seed import seed
from app.routers import admin, agents, auth, events, hives, honeypots, instances, jobs
from app.services.control_plane import control_plane
from app.services.ingest import ingest_service
from app.ws import browser

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("honeyswarm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Honeyswarm API starting up")
    await init_mongo()
    await seed()
    await init_opensearch()
    # Provision the Dashboards index pattern in the background so startup is not
    # blocked while Dashboards finishes booting.
    dashboards_task = asyncio.create_task(ensure_dashboards_index_pattern())
    await ingest_service.start()
    await control_plane.start()
    yield
    logger.info("Honeyswarm API shutting down")
    dashboards_task.cancel()
    await control_plane.stop()
    await ingest_service.stop()
    await close_opensearch()
    await close_mongo()


app = FastAPI(title="Honeyswarm API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Open endpoints: auth (login/register), agent enrollment, health, websocket.
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(admin.router)  # self-guarded (require admin role)

# Browser-facing endpoints require a valid access token.
_protected = [Depends(get_current_user)]
app.include_router(events.router, dependencies=_protected)
app.include_router(hives.router, dependencies=_protected)
app.include_router(honeypots.router, dependencies=_protected)
app.include_router(instances.router, dependencies=_protected)
app.include_router(jobs.router, dependencies=_protected)

app.include_router(browser.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
