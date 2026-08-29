from unittest.mock import MagicMock

import pytest

from app.services import recovery_trigger


def test_trigger_loads_payment_and_executes_recovery(
    monkeypatch,
) -> None:
    db = MagicMock()
    payment = MagicMock()
    payment.id = 1

    query = db.query.return_value
    query.filter.return_value.first.return_value = payment

    recovery_service = MagicMock()

    monkeypatch.setattr(
        recovery_trigger,
        "SessionLocal",
        lambda: db,
    )

    monkeypatch.setattr(
        recovery_trigger,
        "get_recovery_service",
        lambda session: recovery_service,
    )

    recovery_trigger.trigger_recovery_for_payment(1)

    db.query.assert_called_once()
    recovery_service.evaluate_and_execute.assert_called_once_with(
        payment,
    )
    db.close.assert_called_once()


def test_trigger_raises_for_missing_payment(
    monkeypatch,
) -> None:
    db = MagicMock()

    query = db.query.return_value
    query.filter.return_value.first.return_value = None

    monkeypatch.setattr(
        recovery_trigger,
        "SessionLocal",
        lambda: db,
    )

    with pytest.raises(
        ValueError,
        match="Payment with ID 999 was not found",
    ):
        recovery_trigger.trigger_recovery_for_payment(999)

    db.close.assert_called_once()


def test_trigger_closes_session_when_recovery_fails(
    monkeypatch,
) -> None:
    db = MagicMock()
    payment = MagicMock()
    payment.id = 1

    query = db.query.return_value
    query.filter.return_value.first.return_value = payment

    recovery_service = MagicMock()
    recovery_service.evaluate_and_execute.side_effect = RuntimeError(
        "Recovery execution failed"
    )

    monkeypatch.setattr(
        recovery_trigger,
        "SessionLocal",
        lambda: db,
    )

    monkeypatch.setattr(
        recovery_trigger,
        "get_recovery_service",
        lambda session: recovery_service,
    )

    with pytest.raises(
        RuntimeError,
        match="Recovery execution failed",
    ):
        recovery_trigger.trigger_recovery_for_payment(1)

    db.close.assert_called_once()