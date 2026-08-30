from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.enums import (
    RecoveryStatus,
)
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.models.webhook_event import WebhookEvent
from app.services.recovery_factory import (
    get_recovery_service,
)


router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)


# =============================================================
# SIGNATURE VERIFICATION
# =============================================================


def verify_razorpay_signature(
    raw_body: bytes,
    signature: str,
    webhook_secret: str,
) -> bool:
    """
    Verify Razorpay webhook signature using HMAC-SHA256.
    """

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected_signature,
        signature,
    )


# =============================================================
# RECOVERY STATE MANAGEMENT
# =============================================================


def cancel_active_recovery_attempts(
    payment: Payment,
    db: Session,
) -> int:
    """
    Cancel active recovery attempts when the original payment
    succeeds.
    """

    active_statuses = (
        RecoveryStatus.PENDING.value,
        RecoveryStatus.APPROVED.value,
        RecoveryStatus.EXECUTING.value,
        RecoveryStatus.AWAITING_PAYMENT.value,
        RecoveryStatus.SCHEDULED.value,
    )

    attempts = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.payment_id == payment.id,
            RecoveryAttempt.status.in_(active_statuses),
        )
        .all()
    )

    if not attempts:
        return 0

    now = datetime.now(UTC)

    for attempt in attempts:
        attempt.status = (
            RecoveryStatus.CANCELLED.value
        )
        attempt.recovered = False
        attempt.error_message = (
            "Original payment succeeded before recovery "
            "was completed."
        )
        attempt.completed_at = now

    return len(attempts)


def complete_recovery_attempt(
    recovery_attempt: RecoveryAttempt,
    *,
    recovery_payment_id: str | None,
    recovered_amount: int | None,
) -> None:
    """
    Mark a recovery attempt as successfully recovered.

    This is called only after a verified Razorpay success webhook.
    """

    if (
        recovery_attempt.status
        == RecoveryStatus.COMPLETED.value
        and recovery_attempt.recovered is True
    ):
        return

    recovery_attempt.status = (
        RecoveryStatus.COMPLETED.value
    )
    recovery_attempt.executed = True
    recovery_attempt.recovered = True
    recovery_attempt.recovery_payment_id = (
        recovery_payment_id
    )
    recovery_attempt.recovered_amount = (
        recovered_amount
    )
    recovery_attempt.error_message = None
    recovery_attempt.completed_at = datetime.now(
        UTC
    )


# =============================================================
# WEBHOOK ENDPOINT
# =============================================================


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str | None = Header(
        default=None
    ),
    x_razorpay_event_id: str | None = Header(
        default=None
    ),
):
    """
    Receive and process Razorpay webhook events.
    """

    # ---------------------------------------------------------
    # Read raw body
    # ---------------------------------------------------------

    raw_body = await request.body()

    if not raw_body:
        raise HTTPException(
            status_code=400,
            detail="Empty webhook body.",
        )

    # ---------------------------------------------------------
    # Validate headers
    # ---------------------------------------------------------

    if not x_razorpay_signature:
        raise HTTPException(
            status_code=400,
            detail="Missing Razorpay webhook signature.",
        )

    if not x_razorpay_event_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Razorpay event ID.",
        )

    # ---------------------------------------------------------
    # Verify signature
    # ---------------------------------------------------------

    if not verify_razorpay_signature(
        raw_body=raw_body,
        signature=x_razorpay_signature,
        webhook_secret=settings.razorpay_webhook_secret,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay webhook signature.",
        )

    # ---------------------------------------------------------
    # Parse JSON
    # ---------------------------------------------------------

    try:
        payload = json.loads(
            raw_body.decode("utf-8")
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload.",
        ) from exc

    event = payload.get("event")

    if not event:
        raise HTTPException(
            status_code=400,
            detail="Missing event type.",
        )

    # ---------------------------------------------------------
    # Idempotency
    # ---------------------------------------------------------

    existing_event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.event_id
            == x_razorpay_event_id
        )
        .first()
    )

    if existing_event:
        return {
            "success": True,
            "event": event,
            "event_id": x_razorpay_event_id,
            "duplicate": True,
        }

    # ---------------------------------------------------------
    # Persist event
    # ---------------------------------------------------------

    webhook_event = WebhookEvent(
        event_id=x_razorpay_event_id,
        event_type=event,
        payload=raw_body.decode("utf-8"),
        status="received",
    )

    db.add(webhook_event)

    try:
        db.flush()

    except IntegrityError:
        db.rollback()

        return {
            "success": True,
            "event": event,
            "event_id": x_razorpay_event_id,
            "duplicate": True,
        }

    # ---------------------------------------------------------
    # Dispatch
    # ---------------------------------------------------------

    try:
        if event == "payment.failed":
            await handle_payment_failed(
                payload,
                db,
            )

        elif event == "payment.captured":
            await handle_payment_captured(
                payload,
                db,
            )

        elif event == "order.paid":
            await handle_order_paid(
                payload,
                db,
            )

        elif event == "payment_link.paid":
            await handle_payment_link_paid(
                payload,
                db,
            )

        webhook_event.status = "processed"

        db.commit()

    except Exception as exc:
        db.rollback()

        print(
            "Webhook processing failed:",
            {
                "event_id": x_razorpay_event_id,
                "event": event,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail="Webhook processing failed.",
        ) from exc

    return {
        "success": True,
        "event": event,
        "event_id": x_razorpay_event_id,
        "duplicate": False,
    }


# =============================================================
# EVENT HANDLERS
# =============================================================


async def handle_payment_failed(
    payload: dict,
    db: Session,
) -> None:
    """
    Persist failed payment state and trigger recovery evaluation.
    """

    payment_data = (
        payload
        .get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    payment_id = payment_data.get("id")
    order_id = payment_data.get("order_id")

    if not payment_id:
        raise ValueError(
            "payment.failed event missing payment ID."
        )

    if not order_id:
        raise ValueError(
            "payment.failed event missing order ID."
        )

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id
        )
        .first()
    )

    if not payment:
        raise ValueError(
            "Payment record not found for "
            f"Razorpay order {order_id}."
        )

    payment.razorpay_payment_id = payment_id
    payment.status = "failed"
    payment.failure_code = payment_data.get(
        "error_code"
    )
    payment.failure_reason = payment_data.get(
        "error_reason"
    )
    payment.failure_description = payment_data.get(
        "error_description"
    )

    recovery_service = get_recovery_service(
        db=db
    )

    (
        recovery_attempt,
        recovery_decision,
        guardrail_result,
        execution_result,
    ) = recovery_service.evaluate_and_execute(
        payment
    )

    print(
        "Recovery workflow completed:",
        {
            "payment_db_id": payment.id,
            "attempt_id": (
                recovery_attempt.id
                if recovery_attempt is not None
                else None
            ),
            "action": recovery_decision.action,
            "allowed": guardrail_result.allowed,
            "execution_status": (
                execution_result.status
            ),
            "provider_reference_id": (
                execution_result.reference_id
            ),
        },
    )


async def handle_payment_captured(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle captured payments.

    A captured payment may belong to:
    1. A recovery order.
    2. The original merchant order.
    """

    payment_data = (
        payload
        .get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    payment_id = payment_data.get("id")
    order_id = payment_data.get("order_id")
    amount = payment_data.get("amount")

    if not payment_id:
        raise ValueError(
            "payment.captured event missing payment ID."
        )

    if not order_id:
        raise ValueError(
            "payment.captured event missing order ID."
        )

    # ---------------------------------------------------------
    # Recovery payment
    # ---------------------------------------------------------

    recovery_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.provider_reference_id
            == order_id
        )
        .first()
    )

    if recovery_attempt:
        complete_recovery_attempt(
            recovery_attempt,
            recovery_payment_id=payment_id,
            recovered_amount=amount,
        )

        return

    # ---------------------------------------------------------
    # Original payment
    # ---------------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id
        )
        .first()
    )

    if not payment:
        raise ValueError(
            f"Payment record not found for Razorpay order "
            f"{order_id}."
        )

    payment.razorpay_payment_id = payment_id

    if payment.status != "paid":
        payment.status = "captured"


async def handle_order_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle successful Razorpay orders.
    """

    order = (
        payload
        .get("payload", {})
        .get("order", {})
        .get("entity", {})
    )

    order_id = order.get("id")

    if not order_id:
        raise ValueError(
            "order.paid event missing order ID."
        )

    # ---------------------------------------------------------
    # Recovery order
    # ---------------------------------------------------------

    recovery_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.provider_reference_id
            == order_id
        )
        .first()
    )

    if recovery_attempt:
        complete_recovery_attempt(
            recovery_attempt,
            recovery_payment_id=None,
            recovered_amount=(
                order.get("amount_paid")
            ),
        )

        return

    # ---------------------------------------------------------
    # Original order
    # ---------------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id
        )
        .first()
    )

    if not payment:
        raise ValueError(
            "Payment record not found for "
            f"Razorpay order {order_id}."
        )

    payment.status = "paid"

    cancel_active_recovery_attempts(
        payment,
        db,
    )


async def handle_payment_link_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Payment links are currently observed but not mapped directly
    into the ReviveAI payment recovery lifecycle.
    """

    payment_link = (
        payload
        .get("payload", {})
        .get("payment_link", {})
        .get("entity", {})
    )

    print(
        "Payment link paid:",
        {
            "payment_link_id": payment_link.get("id"),
            "amount": payment_link.get("amount"),
            "amount_paid": payment_link.get(
                "amount_paid"
            ),
            "status": payment_link.get("status"),
        },
    )