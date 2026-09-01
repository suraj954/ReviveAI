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

from app.config import settings
from app.db.session import get_db
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

    Transaction flow:

    1. Verify webhook signature.
    2. Validate and persist webhook event.
    3. Process payment state changes.
    4. Commit webhook transaction.
    5. Trigger recovery independently for failed payments.

    Recovery lifecycle transitions are delegated to
    RecoveryService so lifecycle state management and audit
    logging remain centralized.
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
    # Idempotency check
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
    # Persist webhook event
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
    # Dispatch event
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

        webhook_event.status = "processed"

        # Commit webhook transaction before triggering
        # independent recovery execution.
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
    # Trigger recovery AFTER successful webhook commit
    # ---------------------------------------------------------

    if recovery_payment_id is not None:
        try:
            trigger_recovery_for_payment(
                recovery_payment_id
            )

        except Exception as exc:
            # The webhook itself was successfully processed.
            # Do not return HTTP 500 because that would cause
            # unnecessary provider retries and duplicate events.
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
) -> int:
    """
    Persist failed payment state.

    Recovery execution is intentionally not performed inside the
    webhook transaction.

    The caller triggers recovery only after the failed payment
    state has been successfully committed.

    Returns:
        Database ID of the failed payment.
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

    payment.razorpay_payment_id = razorpay_payment_id
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

    return payment.id


async def handle_payment_captured(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle captured Razorpay payments.

    A captured payment may belong to:

    1. A recovery order created by ReviveAI.
    2. The original merchant payment.

    Recovery lifecycle completion is delegated to RecoveryService.
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
    # Check whether this is a recovery payment
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
        recovery_service = get_recovery_service(db)

        recovery_service.complete_from_provider_webhook(
            recovery_attempt,
            recovery_payment_id=razorpay_payment_id,
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
            "Payment record not found for Razorpay order "
            f"{order_id}."
        )

    payment.razorpay_payment_id = razorpay_payment_id

    if payment.status != "paid":
        payment.status = "captured"

    # Original payment succeeded, so any active recovery
    # attempts must be cancelled.
    recovery_service = get_recovery_service(db)

    recovery_service.cancel_active_attempts_for_payment(
        payment
    )


async def handle_order_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle successful Razorpay orders.

    An order may belong to:

    1. A recovery order.
    2. The original merchant payment.

    Recovery lifecycle transitions are delegated to
    RecoveryService.
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
    # Check whether this is a recovery order
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
        # payment.captured is the preferred event for completing
        # recovery because it contains the provider payment ID.
        #
        # order.paid is kept as a fallback confirmation event.
        # The lifecycle method is idempotent, so if payment.captured
        # already completed the attempt, this does nothing.

        recovery_service = get_recovery_service(db)

        recovery_service.complete_from_provider_webhook(
            recovery_attempt,
            recovery_payment_id=None,
            recovered_amount=order.get(
                "amount_paid"
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

    # Original payment succeeded before recovery completed.
    # Cancel any active recovery attempts through the centralized
    # lifecycle service.
    recovery_service = get_recovery_service(db)

    recovery_service.cancel_active_attempts_for_payment(
        payment
    )


async def handle_payment_link_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Observe successful payment links.

    Payment links are currently logged but are not yet mapped
    directly into the ReviveAI recovery lifecycle.
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