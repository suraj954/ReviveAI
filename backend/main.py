from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.orders import router as orders_router
from app.api.webhooks import router as webhooks_router
from app.services.recovery_scheduler_runner import (
    run_recovery_scheduler_loop,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and graceful shutdown.

    The recovery scheduler runs as an independent background task.
    Database polling is delegated to the dedicated scheduler runner,
    which creates fresh sessions for each polling cycle.
    """

    stop_event = asyncio.Event()

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


app = FastAPI(
    title="ReviveAI",
    description="AI-powered revenue recovery orchestration platform",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(orders_router)
app.include_router(webhooks_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {
        "name": "ReviveAI",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }