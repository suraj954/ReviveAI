from datetime import datetime, timedelta

import pytest

from app.ml.dataset import build_training_example
from app.ml.training_dataset import (
    build_training_dataset,
    build_training_dataset_from_records,
)
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt


def make_payment(
    payment_id: int,
    status: str = "failed",
) -> Payment:
    return Payment(
        id=payment_id,
        razorpay_order_id=f"order_{payment_id}",
        amount=50000,
        currency="INR",
        status=status,
        receipt=f"receipt_{payment_id}",
        created_at=datetime(2026, 8, 28, 10, 0, 0),
    )


def make_attempt(
    payment_id: int,
    recovered: bool,
    minutes_after_payment: int = 5,
) -> RecoveryAttempt:
    return RecoveryAttempt(
        payment_id=payment_id,
        action="retry",
        attempt_number=1,
        status="completed",
        recovered=recovered,
        created_at=datetime(2026, 8, 28, 10, 0, 0)
        + timedelta(minutes=minutes_after_payment),
    )


def test_build_training_dataset() -> None:
    payment_1 = make_payment(1)
    payment_2 = make_payment(2)

    attempt_1 = make_attempt(1, True)
    attempt_2 = make_attempt(2, False)

    examples = [
        build_training_example(payment_1, attempt_1),
        build_training_example(payment_2, attempt_2),
    ]

    dataset = build_training_dataset(examples)

    assert len(dataset.X) == 2
    assert len(dataset.y) == 2

    assert dataset.y == [1, 0]

    assert len(dataset.X[0]) == 8
    assert dataset.X[0][0] == 50000.0
    assert dataset.X[0][5] == 1.0


def test_dataset_preserves_example_order() -> None:
    payment_1 = make_payment(1)
    payment_2 = make_payment(2)

    attempt_1 = make_attempt(1, False)
    attempt_2 = make_attempt(2, True)

    examples = [
        build_training_example(payment_1, attempt_1),
        build_training_example(payment_2, attempt_2),
    ]

    dataset = build_training_dataset(examples)

    assert dataset.y == [0, 1]


def test_build_dataset_from_records() -> None:
    records = [
        (
            make_payment(1),
            make_attempt(1, True),
        ),
        (
            make_payment(2),
            make_attempt(2, False),
        ),
    ]

    dataset = build_training_dataset_from_records(records)

    assert dataset.y == [1, 0]
    assert len(dataset.X) == 2
    assert all(len(vector) == 8 for vector in dataset.X)


def test_incomplete_recovery_outcome_is_rejected() -> None:
    payment = make_payment(1)

    attempt = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=1,
        status="pending",
        recovered=None,
    )

    with pytest.raises(ValueError, match="completed recovery outcome"):
        build_training_dataset_from_records(
            [(payment, attempt)]
        )


def test_empty_dataset_is_supported() -> None:
    dataset = build_training_dataset([])

    assert dataset.X == []
    assert dataset.y == []