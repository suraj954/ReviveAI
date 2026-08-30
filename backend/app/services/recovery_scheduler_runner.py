from __future__ import annotations

import asyncio
import logging

from app.db.database import SessionLocal
from app.services.recovery_scheduler import RecoveryScheduler


logger = logging.getLogger(__name__)


def run_recovery_scheduler_once(
    *,
    limit: int = 50,
) -> int:
    """
    Execute one recovery scheduler polling cycle.

    A fresh database session is created for every cycle to prevent
    long-lived sessions and stale database state.

    Returns the number of successfully processed recovery attempts.
    """

    db = SessionLocal()

    try:
        scheduler = RecoveryScheduler(db)

        processed = scheduler.process_due_attempts(
            limit=limit,
        )

        logger.info(
            "Recovery scheduler processed %s attempt(s).",
            processed,
        )

        return processed

    except Exception:
        logger.exception(
            "Recovery scheduler polling cycle failed."
        )
        raise

    finally:
        db.close()


async def run_recovery_scheduler_loop(
    stop_event: asyncio.Event,
    *,
    interval_seconds: float = 30.0,
    limit: int = 50,
) -> None:
    """
    Run the recovery scheduler periodically until stopped.

    The synchronous database scheduler is executed in a worker thread
    so it does not block the FastAPI event loop.

    Args:
        stop_event:
            Signals the loop to stop gracefully.

        interval_seconds:
            Number of seconds to wait between scheduler polling cycles.

        limit:
            Maximum number of due recovery attempts processed per cycle.
    """

    if interval_seconds <= 0:
        raise ValueError(
            "interval_seconds must be greater than zero."
        )

    logger.info(
        "Recovery scheduler loop started "
        "(interval=%s seconds, limit=%s).",
        interval_seconds,
        limit,
    )

    try:
        while not stop_event.is_set():
            try:
                processed = await asyncio.to_thread(
                    run_recovery_scheduler_once,
                    limit=limit,
                )

                logger.debug(
                    "Recovery scheduler loop completed "
                    "with %s processed attempt(s).",
                    processed,
                )

            except Exception:
                # One failed polling cycle must not terminate
                # the background scheduler.
                logger.exception(
                    "Recovery scheduler cycle failed."
                )

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval_seconds,
                )

            except TimeoutError:
                # Normal timeout: begin the next polling cycle.
                pass

    except asyncio.CancelledError:
        logger.info(
            "Recovery scheduler loop was cancelled."
        )
        raise

    finally:
        logger.info(
            "Recovery scheduler loop stopped."
        )