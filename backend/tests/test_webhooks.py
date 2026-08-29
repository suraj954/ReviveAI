import hashlib
import hmac
import json

import pytest

from app.api.webhooks import (
    handle_payment_captured,
    verify_razorpay_signature,
)


# =============================================================
# HELPERS
# =============================================================


def create_signature(
    raw_body: bytes,
    secret: str,
) -> str:
    """Create a valid HMAC-SHA256 signature for testing."""

    return hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


# =============================================================
# SIGNATURE TESTS
# =============================================================


def test_valid_razorpay_signature() -> None:
    secret = "test_webhook_secret"

    payload = {
        "event": "payment.failed",
        "payload": {},
    }

    raw_body = json.dumps(payload).encode("utf-8")

    signature = create_signature(
        raw_body,
        secret,
    )

    assert verify_razorpay_signature(
        raw_body=raw_body,
        signature=signature,
        webhook_secret=secret,
    )


def test_invalid_razorpay_signature() -> None:
    secret = "test_webhook_secret"

    payload = {
        "event": "payment.failed",
        "payload": {},
    }

    raw_body = json.dumps(payload).encode("utf-8")

    invalid_signature = "invalid_signature"

    assert not verify_razorpay_signature(
        raw_body=raw_body,
        signature=invalid_signature,
        webhook_secret=secret,
    )


def test_modified_body_fails_signature() -> None:
    secret = "test_webhook_secret"

    original_body = b'{"event":"payment.failed"}'

    signature = create_signature(
        original_body,
        secret,
    )

    modified_body = b'{"event":"payment.captured"}'

    assert not verify_razorpay_signature(
        raw_body=modified_body,
        signature=signature,
        webhook_secret=secret,
    )


# =============================================================
# RECOVERY RECONCILIATION TESTS
# =============================================================


class FakeRecoveryAttempt:
    def __init__(
        self,
        *,
        id: int,
        payment_id: int,
        provider_reference_id: str,
    ) -> None:
        self.id = id
        self.payment_id = payment_id
        self.provider_reference_id = provider_reference_id
        self.status = "awaiting_payment"
        self.recovered = None
        self.completed_at = None


class FakeQuery:
    def __init__(
        self,
        result,
    ) -> None:
        self.result = result

    def filter(
        self,
        *args,
    ):
        return self

    def first(self):
        return self.result


class FakeSession:
    def __init__(
        self,
        recovery_attempt,
    ) -> None:
        self.recovery_attempt = recovery_attempt

    def query(
        self,
        model,
    ):
        return FakeQuery(
            self.recovery_attempt,
        )


@pytest.mark.asyncio
async def test_recovery_payment_capture_marks_attempt_recovered() -> None:
    recovery_order_id = "order_recovery_123"

    recovery_attempt = FakeRecoveryAttempt(
        id=1,
        payment_id=10,
        provider_reference_id=recovery_order_id,
    )

    db = FakeSession(
        recovery_attempt,
    )

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_recovery_123",
                    "order_id": recovery_order_id,
                    "amount": 50000,
                    "currency": "INR",
                }
            }
        },
    }

    await handle_payment_captured(
        payload,
        db,
    )

    assert recovery_attempt.status == "completed"
    assert recovery_attempt.recovered is True
    assert recovery_attempt.completed_at is not None