"""
FastAPI application factory.

Boots the AI Voice Agent Platform:
- Connects to PostgreSQL + Redis on startup
- Mounts all API routers (calls, agents, webhooks, WebSocket)
- Shuts down cleanly on SIGTERM
"""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings

# ─── Structured logging ───────────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.app_env == "development"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # ── Startup ──
    log.info("starting", env=settings.app_env, port=settings.app_port)

    # Load Google Cloud credentials from base64 env var (for Railway/cloud deploy)
    import os
    import base64
    gcp_creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64", "")
    if gcp_creds_b64:
        creds_path = "/tmp/gcp-credentials.json"
        with open(creds_path, "wb") as f:
            f.write(base64.b64decode(gcp_creds_b64))
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        log.info("gcp_credentials_loaded", path=creds_path)

    # Ensure DB tables exist + seed data
    try:
        from backend.app.db.database import create_tables, AsyncSessionLocal
        await create_tables()
        log.info("database_tables_ensured")

        # Seed default tenant if not exists
        from backend.app.db.models import Tenant
        from sqlalchemy import select
        import uuid
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.api_key == "dev-api-key-change-in-production")
            )
            if not result.scalar_one_or_none():
                dev_tenant = Tenant(
                    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    name="Dev Tenant",
                    api_key="dev-api-key-change-in-production",
                    tier="standard",
                )
                db.add(dev_tenant)
                await db.commit()
                log.info("seed_tenant_created")
            else:
                log.info("seed_tenant_exists")
    except Exception as exc:
        log.warning("database_setup_error", error=str(exc))

    # Warm up Redis connection (optional — app works without it, just no session memory)
    try:
        from backend.app.services.memory.short_term import get_redis
        redis = await get_redis()
        await redis.ping()
        log.info("redis_connected", url=settings.redis_url)
    except Exception as exc:
        log.warning("redis_not_available", error=str(exc), url=settings.redis_url)

    log.info("startup_complete", public_url=settings.public_base_url)

    yield

    # ── Shutdown ──
    log.info("shutting_down")

    # Close Redis
    from backend.app.services.memory.short_term import _redis
    if _redis:
        await _redis.close()
        log.info("redis_closed")

    # Close DB engine
    from backend.app.db.database import engine
    await engine.dispose()
    log.info("database_closed")

    log.info("shutdown_complete")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Voice Agent Platform",
    description="Multi-tenant autonomous AI calling platform — GenAI native, cheapest in market.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routers ──────────────────────────────────────────────────────────────────

from backend.app.api.routes.agents import router as agents_router
from backend.app.api.routes.calls import router as calls_router
from backend.app.api.routes.knowledge import router as knowledge_router
from backend.app.api.routes.webhooks.telnyx import router as telnyx_webhook_router
from backend.app.api.routes.ws import router as ws_router
from backend.app.api.routes.dashboard import router as dashboard_router
from backend.app.api.routes.onboarding import router as onboarding_router
from backend.app.api.routes.landing import router as landing_router

app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(calls_router, prefix="/api/v1/calls", tags=["calls"])
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(telnyx_webhook_router, prefix="/webhooks/telnyx", tags=["webhooks"])
app.include_router(ws_router, tags=["websocket"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])
app.include_router(landing_router, prefix="/landing", tags=["landing"])


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "env": settings.app_env,
    }


@app.get("/", tags=["system"], response_class=__import__("fastapi.responses", fromlist=["RedirectResponse"]).RedirectResponse)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/landing")
