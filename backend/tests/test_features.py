from datetime import datetime, timedelta

from app.ml.features import build_payment_features
from app.models.payment import Payment


def test_captured_payment_features() -> None:
    now = datetime.utcnow()

    payment = Payment(
        razorpay_order_id="order_test_1",
        amount=50000,
        currency="INR",
        status="captured",
        receipt="test_receipt",
        created_at=now,
    )

    features = build_payment_features(payment, now=now)

    assert features.amount == 50000.0
    assert features.currency_inr == 1
    assert features.payment_status_created == 0
    assert features.payment_status_paid == 0
    assert features.payment_status_captured == 1
    assert features.payment_status_failed == 0
    assert features.has_receipt == 1
    assert features.payment_age_seconds == 0.0


def test_failed_payment_features() -> None:
    now = datetime.utcnow()

    payment = Payment(
        razorpay_order_id="order_test_2",
        amount=25000,
        currency="INR",
        status="failed",
        receipt=None,
        created_at=now,
    )

    features = build_payment_features(payment, now=now)

    assert features.amount == 25000.0
    assert features.currency_inr == 1
    assert features.payment_status_created == 0
    assert features.payment_status_paid == 0
    assert features.payment_status_captured == 0
    assert features.payment_status_failed == 1
    assert features.has_receipt == 0


def test_created_payment_features() -> None:
    now = datetime.utcnow()

    payment = Payment(
        razorpay_order_id="order_test_3",
        amount=10000,
        currency="INR",
        status="created",
        receipt="test_receipt",
        created_at=now,
    )

    features = build_payment_features(payment, now=now)

    assert features.payment_status_created == 1
    assert features.payment_status_paid == 0
    assert features.payment_status_captured == 0
    assert features.payment_status_failed == 0


def test_payment_age_is_calculated() -> None:
    now = datetime.utcnow()
    created_at = now - timedelta(seconds=60)

    payment = Payment(
        razorpay_order_id="order_test_4",
        amount=10000,
        currency="INR",
        status="failed",
        receipt=None,
        created_at=created_at,
    )

    features = build_payment_features(payment, now=now)

    assert features.payment_age_seconds == 60.0


def test_currency_is_case_insensitive() -> None:
    now = datetime.utcnow()

    payment = Payment(
        razorpay_order_id="order_test_5",
        amount=10000,
        currency="inr",
        status="paid",
        receipt="test_receipt",
        created_at=now,
    )

    features = build_payment_features(payment, now=now)

    assert features.currency_inr == 1
    assert features.payment_status_paid == 1