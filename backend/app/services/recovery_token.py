from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.config import settings


TOKEN_PURPOSE = "recovery_status"


def issue_recovery_token(payment_id: int) -> str:
    """
    Create a signed, time-limited recovery access token.

    The token is scoped only for recovery-status access and contains
    no Razorpay order ID or RecoveryAttempt ID.
    """

    now = int(time.time())

    payload = {
        "pid": payment_id,
        "purpose": TOKEN_PURPOSE,
        "iat": now,
        "exp": now + settings.recovery_token_ttl_seconds,
    }

    payload_json = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    encoded_payload = base64.urlsafe_b64encode(
        payload_json
    ).rstrip(b"=")

    signature = hmac.new(
        settings.recovery_token_secret.encode("utf-8"),
        encoded_payload,
        hashlib.sha256,
    ).digest()

    encoded_signature = base64.urlsafe_b64encode(
        signature
    ).rstrip(b"=")

    return (
        encoded_payload.decode("utf-8")
        + "."
        + encoded_signature.decode("utf-8")
    )


def verify_recovery_token(token: str) -> int:
    """
    Verify a recovery access token.

    Returns:
        The internal Payment ID.

    Raises:
        ValueError if the token is invalid, expired, malformed,
        or has an incorrect purpose.
    """

    try:
        encoded_payload, encoded_signature = token.split(".", 1)

        expected_signature = hmac.new(
            settings.recovery_token_secret.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        padded_signature = (
            encoded_signature
            + "=" * (-len(encoded_signature) % 4)
        )

        provided_signature = base64.urlsafe_b64decode(
            padded_signature.encode("utf-8")
        )

        if not hmac.compare_digest(
            expected_signature,
            provided_signature,
        ):
            raise ValueError("Invalid token signature")

        padded_payload = (
            encoded_payload
            + "=" * (-len(encoded_payload) % 4)
        )

        payload = json.loads(
            base64.urlsafe_b64decode(
                padded_payload.encode("utf-8")
            )
        )

        if payload.get("purpose") != TOKEN_PURPOSE:
            raise ValueError("Invalid token purpose")

        expires_at = payload.get("exp")

        if (
            not isinstance(expires_at, int)
            or int(time.time()) >= expires_at
        ):
            raise ValueError("Token expired")

        payment_id = payload.get("pid")

        if (
            not isinstance(payment_id, int)
            or payment_id <= 0
        ):
            raise ValueError("Invalid payment ID")

        return payment_id

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        base64.binascii.Error,
    ) as exc:
        raise ValueError(
            "Invalid or expired recovery token"
        ) from exc