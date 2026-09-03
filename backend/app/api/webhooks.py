from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import ClientDisconnect

from app.config import settings
from app.db.session import get_db
from app.models.enums import PaymentStatus, WebhookStatus
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.models.webhook_event import WebhookEvent
from app.services.recovery_factory import get_recovery_service
from app.services.recovery_trigger import (
    trigger_recovery_for_payment,
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

    Flow:

    1. Read raw request body.
    2. Verify Razorpay signature.
    3. Validate event metadata.
    4. Check webhook idempotency.
    5. Persist webhook event.
    6. Process payment lifecycle.
    7. Commit database transaction.
    8. Trigger recovery independently after commit.

    Important:
    Recovery execution is intentionally separated from webhook
    transaction processing. A recovery execution failure must not
    cause the provider webhook to be retried.
    """

    # ---------------------------------------------------------
    # READ RAW BODY
    # ---------------------------------------------------------

    try:
        raw_body = await request.body()

    except ClientDisconnect:
        raise HTTPException(
            status_code=400,
            detail="Webhook client disconnected.",
        )

    if not raw_body:
        raise HTTPException(
            status_code=400,
            detail="Empty webhook body.",
        )

    # ---------------------------------------------------------
    # VALIDATE REQUIRED HEADERS
    # ---------------------------------------------------------

    if not x_razorpay_signature:
        raise HTTPException(
            status_code=400,
            detail="Missing Razorpay webhook signature.",
        )

    if not x_razorpay_event_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Razorpay webhook event ID.",
        )

    # ---------------------------------------------------------
    # VERIFY SIGNATURE
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
    # PARSE JSON
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
            detail="Invalid JSON webhook payload.",
        ) from exc

    event = payload.get("event")

    if not event:
        raise HTTPException(
            status_code=400,
            detail="Missing webhook event type.",
        )

    # ---------------------------------------------------------
    # IDEMPOTENCY CHECK
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
    # PERSIST WEBHOOK EVENT
    # ---------------------------------------------------------

    webhook_event = WebhookEvent(
        event_id=x_razorpay_event_id,
        event_type=event,
        payload=raw_body.decode("utf-8"),
        status=WebhookStatus.RECEIVED.value,
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
    # DISPATCH EVENT
    # ---------------------------------------------------------

    recovery_payment_id: int | None = None

    try:

        if event == "payment.failed":

            recovery_payment_id = (
                await handle_payment_failed(
                    payload,
                    db,
                )
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

        else:
            print(
                "Ignoring unsupported Razorpay webhook event:",
                {
                    "event": event,
                    "event_id": x_razorpay_event_id,
                },
            )

        webhook_event.status = (
            WebhookStatus.PROCESSED.value
        )

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

    # ---------------------------------------------------------
    # TRIGGER RECOVERY AFTER WEBHOOK COMMIT
    # ---------------------------------------------------------

    if recovery_payment_id is not None:

        try:
            trigger_recovery_for_payment(
                recovery_payment_id
            )

        except Exception as exc:

            # Webhook processing already succeeded.
            # Never fail the webhook response because recovery
            # orchestration failed afterwards.
            print(
                "Recovery trigger failed:",
                {
                    "payment_id": recovery_payment_id,
                    "error": str(exc),
                },
            )

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
) -> int | None:
    """
    Handle payment.failed events.

    Cases:

    1. Recovery payment failure:
       Mark the corresponding recovery attempt as failed.
       Never recursively trigger recovery.

    2. Original tracked payment failure:
       Mark the original payment as failed.
       Return its ID so recovery can start after webhook commit.

    3. Unknown payment:
       Ignore safely.

    Returning None means no new recovery workflow should start.
    """

    payment_data = (
        payload
        .get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    razorpay_payment_id = payment_data.get("id")
    order_id = payment_data.get("order_id")

    if not razorpay_payment_id:
        raise ValueError(
            "payment.failed event missing payment ID."
        )

    if not order_id:
        raise ValueError(
            "payment.failed event missing order ID."
        )

    # ---------------------------------------------------------
    # CASE 1: RECOVERY ORDER FAILURE
    # ---------------------------------------------------------

    recovery_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.provider_reference_id
            == order_id
        )
        .first()
    )

    if recovery_attempt is not None:

        terminal_statuses = {
            "completed",
            "failed",
            "cancelled",
            "blocked",
            "exhausted",
        }

        # Ignore duplicate or late failure events.
        if recovery_attempt.status in terminal_statuses:
            return None

        recovery_service = get_recovery_service(db)

        failure_description = (
            payment_data.get("error_description")
            or payment_data.get("error_reason")
            or payment_data.get("error_code")
            or "Recovery payment failed."
        )

        recovery_service.mark_execution_failed(
            recovery_attempt,
            reason=failure_description,
        )

        print(
            "Recovery payment marked as failed:",
            {
                "order_id": order_id,
                "attempt_id": recovery_attempt.id,
            },
        )

        # Critical: never recursively trigger recovery from
        # a recovery payment webhook.
        return None

    # ---------------------------------------------------------
    # CASE 2: ORIGINAL TRACKED PAYMENT FAILURE
    # ---------------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id
        )
        .first()
    )

    if payment is None:

        print(
            "Ignoring payment.failed for unknown order:",
            {
                "order_id": order_id,
                "payment_id": razorpay_payment_id,
            },
        )

        return None

    # ---------------------------------------------------------
    # IDEMPOTENT PAYMENT STATE UPDATE
    # ---------------------------------------------------------

    if payment.status in {
        PaymentStatus.PAID.value,
        PaymentStatus.CAPTURED.value,
    }:
        return None

    payment.status = PaymentStatus.FAILED.value
    payment.razorpay_payment_id = razorpay_payment_id

    print(
        "Original payment marked as failed:",
        {
            "payment_id": payment.id,
            "order_id": order_id,
        },
    )

    return payment.id


async def handle_payment_captured(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle payment.captured events.

    Supports both:

    1. Original payment success.
    2. Recovery payment success.

    Recovery is marked completed only after provider-confirmed
    payment success.
    """

    payment_data = (
        payload
        .get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    razorpay_payment_id = payment_data.get("id")
    order_id = payment_data.get("order_id")
    amount = payment_data.get("amount")

    if not razorpay_payment_id:
        raise ValueError(
            "payment.captured event missing payment ID."
        )

    if not order_id:
        raise ValueError(
            "payment.captured event missing order ID."
        )

    # ---------------------------------------------------------
    # CASE 1: RECOVERY PAYMENT SUCCESS
    # ---------------------------------------------------------

    recovery_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.provider_reference_id
            == order_id
        )
        .first()
    )

    if recovery_attempt is not None:

        recovery_service = get_recovery_service(db)

        recovery_service.complete_from_provider_webhook(
            recovery_attempt,
            recovery_payment_id=razorpay_payment_id,
            recovered_amount=(
                int(amount)
                if amount is not None
                else None
            ),
        )

        print(
            "Recovery payment completed:",
            {
                "attempt_id": recovery_attempt.id,
                "order_id": order_id,
                "payment_id": razorpay_payment_id,
            },
        )

        return

    # ---------------------------------------------------------
    # CASE 2: ORIGINAL PAYMENT SUCCESS
    # ---------------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id
        )
        .first()
    )

    if payment is None:

        print(
            "Ignoring payment.captured for unknown order:",
            {
                "order_id": order_id,
                "payment_id": razorpay_payment_id,
            },
        )

        return

    payment.status = PaymentStatus.CAPTURED.value
    payment.razorpay_payment_id = razorpay_payment_id

    # Cancel any active recovery workflows because the original
    # payment itself succeeded.
    recovery_service = get_recovery_service(db)

    recovery_service.cancel_active_attempts_for_payment(
        payment,
    )


async def handle_order_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle order.paid events.

    payment.captured is the primary source of payment completion.
    This handler safely synchronizes the original payment state
    when an order.paid event is received.
    """

    order_data = (
        payload
        .get("payload", {})
        .get("order", {})
        .get("entity", {})
    )

    order_id = order_data.get("id")

    if not order_id:
        return

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id
        )
        .first()
    )

    if payment is None:
        return

    if payment.status not in {
        PaymentStatus.PAID.value,
        PaymentStatus.CAPTURED.value,
    }:
        payment.status = PaymentStatus.PAID.value

    recovery_service = get_recovery_service(db)

    recovery_service.cancel_active_attempts_for_payment(
        payment,
    )


async def handle_payment_link_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Payment links are currently outside the main recovery execution
    flow.

    The event is intentionally accepted and recorded for
    observability without triggering recovery.
    """

    return None