from datetime import datetime, timedelta

import pytest

from app.ml.dataset import build_training_example
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt


def make_payment() -> Payment:
    return Payment(
        id=1,
        razorpay_order_id="order_training_test",
        amount=50000,
        currency="INR",
        status="failed",
        receipt="training_receipt",
        created_at=datetime(2026, 8, 28, 10, 0, 0),
    )


def test_build_successful_training_example() -> None:
    payment = make_payment()

    attempt = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=1,
        status="completed",
        recovered=True,
        created_at=payment.created_at + timedelta(minutes=5),
    )

    example = build_training_example(payment, attempt)

    assert example.label == 1
    assert example.features.amount == 50000.0
    assert example.features.currency_inr == 1
    assert example.features.payment_status_failed == 1
    assert example.features.has_receipt == 1
    assert example.features.payment_age_seconds == 300.0


def test_build_failed_training_example() -> None:
    payment = make_payment()

    attempt = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=1,
        status="completed",
        recovered=False,
        created_at=payment.created_at + timedelta(minutes=2),
    )

    example = build_training_example(payment, attempt)

    assert example.label == 0
    assert example.features.payment_status_failed == 1
    assert example.features.payment_age_seconds == 120.0


def test_uncompleted_attempt_cannot_be_training_example() -> None:
    payment = make_payment()

    attempt = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=1,
        status="pending",
        recovered=None,
    )

    with pytest.raises(ValueError, match="completed recovery outcome"):
        build_training_example(payment, attempt)