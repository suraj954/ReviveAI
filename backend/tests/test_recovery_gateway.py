from unittest.mock import patch

import pytest

from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.razorpay.recovery_gateway import RazorpayRecoveryGateway


def make_payment(
    payment_status: str,
) -> Payment:
    """
    Create a test payment object.

    Payment amounts are stored in paise.
    """

    payment = Payment(
        id=1,
        razorpay_order_id="order_original_123",
        amount=50000,
        currency="INR",
        status=payment_status,
        receipt="test_receipt",
    )

    return payment


def test_retry_creates_new_razorpay_order() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment(
        PaymentStatus.FAILED.value
    )

    with patch(
        "app.razorpay.recovery_gateway.create_order"
    ) as mock_create_order:
        mock_create_order.return_value = {
            "id": "order_recovery_123",
        }

        result = gateway.execute_retry(payment)

    assert result == "order_recovery_123"

    mock_create_order.assert_called_once_with(
        amount_in_paise=50000,
        currency="INR",
        receipt="recovery_order_1",
    )


def test_retry_rejects_non_failed_payment() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment(
        PaymentStatus.CREATED.value
    )

    with pytest.raises(
        ValueError,
        match="Recovery retry is only allowed for failed payments",
    ):
        gateway.execute_retry(payment)


def test_retry_fails_when_razorpay_returns_no_order_id() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment(
        PaymentStatus.FAILED.value
    )

    with patch(
        "app.razorpay.recovery_gateway.create_order"
    ) as mock_create_order:
        mock_create_order.return_value = {}

        with pytest.raises(
            RuntimeError,
            match=(
                "Razorpay did not return a recovery order ID"
            ),
        ):
            gateway.execute_retry(payment)

    mock_create_order.assert_called_once_with(
        amount_in_paise=50000,
        currency="INR",
        receipt="recovery_order_1",
    )


def test_retry_preserves_amount_in_paise() -> None:
    """
    Verify that the recovery gateway forwards the exact stored
    amount without converting it to major currency units.
    """

    gateway = RazorpayRecoveryGateway()
    payment = make_payment(
        PaymentStatus.FAILED.value
    )

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
        amount_in_paise=12345,
        currency="INR",
        receipt="recovery_order_1",
    )


def test_wait_and_retry_returns_scheduling_reference() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment(
        PaymentStatus.CREATED.value
    )

    result = gateway.execute_wait_and_retry(
        payment
    )

    assert result == (
        "scheduled_recovery_order_1"
    )


def test_wait_and_retry_rejects_non_created_payment() -> None:
    gateway = RazorpayRecoveryGateway()
    payment = make_payment(
        PaymentStatus.FAILED.value
    )

    with pytest.raises(
        ValueError,
        match=(
            "Wait-and-retry is only allowed "
            "for created payments"
        ),
    ):
        gateway.execute_wait_and_retry(
            payment
        )