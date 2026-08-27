import hashlib
import hmac
import json

from app.api.webhooks import verify_razorpay_signature


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