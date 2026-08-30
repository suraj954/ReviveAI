import asyncio
from unittest.mock import MagicMock

import pytest

from app.services import recovery_scheduler_runner


def test_runner_creates_scheduler_and_processes_attempts(
    monkeypatch,
) -> None:
    """
    The runner should create a fresh database session, construct
    the scheduler, process due attempts, and return the count.
    """

    db = MagicMock()

    scheduler = MagicMock()
    scheduler.process_due_attempts.return_value = 3

    monkeypatch.setattr(
        recovery_scheduler_runner,
        "SessionLocal",
        lambda: db,
    )

    monkeypatch.setattr(
        recovery_scheduler_runner,
        "RecoveryScheduler",
        lambda session: scheduler,
    )

    processed = (
        recovery_scheduler_runner.run_recovery_scheduler_once()
    )

    assert processed == 3

    scheduler.process_due_attempts.assert_called_once_with(
        limit=50,
    )

    db.close.assert_called_once()


def test_runner_passes_custom_processing_limit(
    monkeypatch,
) -> None:
    """
    The runner should forward a custom processing limit to the
    recovery scheduler.
    """

    db = MagicMock()

    scheduler = MagicMock()
    scheduler.process_due_attempts.return_value = 7

    monkeypatch.setattr(
        recovery_scheduler_runner,
        "SessionLocal",
        lambda: db,
    )

    monkeypatch.setattr(
        recovery_scheduler_runner,
        "RecoveryScheduler",
        lambda session: scheduler,
    )

    processed = (
        recovery_scheduler_runner.run_recovery_scheduler_once(
            limit=10,
        )
    )

    assert processed == 7

    scheduler.process_due_attempts.assert_called_once_with(
        limit=10,
    )

    db.close.assert_called_once()


def test_runner_closes_session_when_scheduler_fails(
    monkeypatch,
) -> None:
    """
    The database session must always be closed, even when the
    scheduler raises an exception.
    """

    db = MagicMock()

    scheduler = MagicMock()

    scheduler.process_due_attempts.side_effect = RuntimeError(
        "Scheduler processing failed"
    )

    monkeypatch.setattr(
        recovery_scheduler_runner,
        "SessionLocal",
        lambda: db,
    )

    monkeypatch.setattr(
        recovery_scheduler_runner,
        "RecoveryScheduler",
        lambda session: scheduler,
    )

    with pytest.raises(
        RuntimeError,
        match="Scheduler processing failed",
    ):
        recovery_scheduler_runner.run_recovery_scheduler_once()

    db.close.assert_called_once()


# ============================================================
# ASYNC LOOP VALIDATION
# ============================================================


def test_scheduler_loop_rejects_invalid_interval():
    async def run_test():
        stop_event = asyncio.Event()

        with pytest.raises(
            ValueError,
            match="interval_seconds must be greater than zero",
        ):
            await recovery_scheduler_runner.run_recovery_scheduler_loop(
                stop_event,
                interval_seconds=0,
            )

    asyncio.run(run_test())


# ============================================================
# ASYNC LOOP EXECUTION
# ============================================================


def test_scheduler_loop_runs_and_stops_gracefully(
    monkeypatch,
):
    async def run_test():
        stop_event = asyncio.Event()
        call_count = 0

        def fake_run_once(
            *,
            limit=50,
        ):
            nonlocal call_count

            call_count += 1

            if call_count >= 2:
                stop_event.set()

            return 1

        monkeypatch.setattr(
            recovery_scheduler_runner,
            "run_recovery_scheduler_once",
            fake_run_once,
        )

        await recovery_scheduler_runner.run_recovery_scheduler_loop(
            stop_event,
            interval_seconds=0.01,
            limit=10,
        )

        assert call_count == 2

    asyncio.run(run_test())


def test_scheduler_loop_survives_cycle_failure(
    monkeypatch,
):
    async def run_test():
        stop_event = asyncio.Event()
        call_count = 0

        def fake_run_once(
            *,
            limit=50,
        ):
            nonlocal call_count

            call_count += 1

            if call_count == 1:
                raise RuntimeError(
                    "Temporary scheduler failure"
                )

            stop_event.set()

            return 1

        monkeypatch.setattr(
            recovery_scheduler_runner,
            "run_recovery_scheduler_once",
            fake_run_once,
        )

        await recovery_scheduler_runner.run_recovery_scheduler_loop(
            stop_event,
            interval_seconds=0.01,
        )

        assert call_count == 2

    asyncio.run(run_test())