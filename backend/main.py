from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.orders import router as orders_router
from app.api.recovery_checkout import router as recovery_router
from app.api.insights import router as insights_router
from app.api.webhooks import router as webhooks_router

from app.services.recovery_scheduler_runner import (
    run_recovery_scheduler_loop,
)


# =============================================================
# LOGGING
# =============================================================

logger = logging.getLogger(__name__)


# =============================================================
# APPLICATION LIFESPAN
# =============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and graceful shutdown.

    The recovery scheduler runs as an independent background task.

    The scheduler periodically checks for delayed recovery attempts
    that are due for execution.
    """

    stop_event = asyncio.Event()

    # ---------------------------------------------------------
    # Start recovery scheduler
    # ---------------------------------------------------------

    scheduler_task = asyncio.create_task(
        run_recovery_scheduler_loop(
            stop_event,
            interval_seconds=10.0,
            limit=50,
        )
    )

    logger.info("Recovery scheduler started.")

    try:
        yield

    finally:
        logger.info("Stopping recovery scheduler.")

        # -----------------------------------------------------
        # Signal scheduler to stop
        # -----------------------------------------------------

        stop_event.set()

        try:
            await asyncio.wait_for(
                scheduler_task,
                timeout=10.0,
            )

        except TimeoutError:
            logger.warning(
                "Recovery scheduler did not stop gracefully; "
                "cancelling task."
            )

            scheduler_task.cancel()

            with suppress(asyncio.CancelledError):
                await scheduler_task

        logger.info("Recovery scheduler stopped.")


# =============================================================
# FASTAPI APPLICATION
# =============================================================

app = FastAPI(
    title="ReviveAI",
    description=(
        "AI-powered revenue recovery orchestration platform"
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================
# CORS CONFIGURATION
# =============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    # Old frontend
    "http://127.0.0.1:5500",
    "http://localhost:5500",

    # ReviveAI dashboard
    "http://localhost:5173",
    "http://127.0.0.1:5173",

    # Customer demo storefront
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================
# API ROUTERS
# =============================================================

app.include_router(orders_router)
app.include_router(webhooks_router)
app.include_router(dashboard_router)
app.include_router(recovery_router)
app.include_router(insights_router)


# =============================================================
# ROOT ENDPOINT
# =============================================================

@app.get("/")
def root():
    """
    Basic application information.
    """

    return {
        "name": "ReviveAI",
        "status": "running",
        "version": "0.1.0",
    }


# =============================================================
# HEALTH CHECK
# =============================================================

@app.get("/health")
def health_check():
    """
    Application health check endpoint.
    """

    return {
        "status": "healthy",
    }