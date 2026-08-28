from datetime import datetime
from unittest.mock import patch

import pytest

from app.models.payment import Payment
from app.razorpay.recovery_gateway import RazorpayRecoveryGateway


def make_payment(
    status: str,
    payment_id: int = 1,
) -> Payment:
    return Payment(
        id=payment_id,
        razorpay_order_id=f"order_{payment_id}",
        amount=50000,
        currency="INR",
        status=status,
        receipt="test_receipt",
        created_at=datetime.utcnow(),
    )


def test_retry_creates_new_razorpay_order() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment("failed")

    with patch(
        "app.razorpay.recovery_gateway.create_order"
    ) as mock_create_order:
        mock_create_order.return_value = {
            "id": "order_recovery_123",
        }

        result = gateway.execute_retry(payment)

    assert result == "order_recovery_123"

    mock_create_order.assert_called_once_with(
        amount_in_rupees=500.0,
        receipt="recovery_order_1",
    )


def test_retry_rejects_non_failed_payment() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment("created")

    with patch(
        "app.razorpay.recovery_gateway.create_order"
    ) as mock_create_order:
        with pytest.raises(
            ValueError,
            match="Recovery retry is only allowed for failed payments",
        ):
            gateway.execute_retry(payment)

    mock_create_order.assert_not_called()


def test_retry_fails_when_razorpay_returns_no_order_id() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment("failed")

    with patch(
        "app.razorpay.recovery_gateway.create_order"
    ) as mock_create_order:
        mock_create_order.return_value = {}

        with pytest.raises(
            RuntimeError,
            match="Razorpay did not return a recovery order ID",
        ):
            gateway.execute_retry(payment)

    mock_create_order.assert_called_once_with(
        amount_in_rupees=500.0,
        receipt="recovery_order_1",
    )


def test_retry_converts_paise_to_rupees() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment("failed")
    payment.amount = 12345

    with patch(
        "app.razorpay.recovery_gateway.create_order"
    ) as mock_create_order:
        mock_create_order.return_value = {
            "id": "order_recovery_456",
        }

        result = gateway.execute_retry(payment)

    assert result == "order_recovery_456"

    mock_create_order.assert_called_once_with(
        amount_in_rupees=123.45,
        receipt="recovery_order_1",
    )


def test_wait_and_retry_returns_scheduling_reference() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment("created")

    result = gateway.execute_wait_and_retry(payment)

    assert result == "scheduled_recovery_order_1"


def test_wait_and_retry_rejects_non_created_payment() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment("failed")

    with pytest.raises(
        ValueError,
        match="Wait-and-retry is only allowed for created payments",
    ):
        gateway.execute_wait_and_retry(payment)