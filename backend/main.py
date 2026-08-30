from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.orders import router as orders_router
from app.api.webhooks import router as webhooks_router
from app.db.database import SessionLocal
from app.services.recovery_scheduler import RecoveryScheduler


logger = logging.getLogger(__name__)


async def recovery_scheduler_loop() -> None:
    """
    Run the delayed recovery scheduler continuously.

    A fresh SQLAlchemy session is created for every polling cycle.
    This prevents a long-running background task from holding onto
    stale database state or a request-scoped session.
    """

    poll_interval_seconds = 10

    while True:
        db = SessionLocal()

        try:
            scheduler = RecoveryScheduler(db)

            processed_count = scheduler.process_due_attempts()

            if processed_count > 0:
                logger.info(
                    "Recovery scheduler processed %s due attempt(s).",
                    processed_count,
                )

        except Exception:
            logger.exception(
                "Unexpected error in recovery scheduler cycle."
            )

        finally:
            db.close()

        await asyncio.sleep(poll_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and graceful shutdown.

    The recovery scheduler runs as an independent background task.
    It is cancelled cleanly when FastAPI shuts down.
    """

    scheduler_task = asyncio.create_task(
        recovery_scheduler_loop()
    )

    logger.info(
        "Recovery scheduler started."
    )

    try:
        yield

    finally:
        logger.info(
            "Stopping recovery scheduler."
        )

        scheduler_task.cancel()

        with suppress(asyncio.CancelledError):
            await scheduler_task

        logger.info(
            "Recovery scheduler stopped."
        )


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