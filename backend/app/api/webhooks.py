import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.models.webhook_event import WebhookEvent
from app.services.recovery_factory import get_recovery_service


router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)


# =============================================================
# RAZORPAY SIGNATURE VERIFICATION
# =============================================================


def verify_razorpay_signature(
    raw_body: bytes,
    signature: str,
    webhook_secret: str,
) -> bool:
    """
    Verify a Razorpay webhook signature using HMAC-SHA256.

    Razorpay signs the exact raw request body using the webhook
    secret. Therefore, the raw body must be used before parsing
    or modifying the JSON payload.
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
    succeeds before the recovery flow is completed.

    Example:

        Original payment fails
                ↓
        Recovery order created
                ↓
        Original payment succeeds
                ↓
        Recovery is no longer required
                ↓
        Active recovery attempts are cancelled

    Terminal recovery attempts such as completed, failed, and
    blocked are not modified.
    """

    active_statuses = (
        "pending",
        "executing",
        "awaiting_payment",
        "scheduled",
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
        attempt.status = "cancelled"
        attempt.recovered = False
        attempt.error_message = (
            "Original payment succeeded before recovery "
            "was completed."
        )
        attempt.completed_at = now

    print(
        "Active recovery attempts cancelled:",
        {
            "payment_db_id": payment.id,
            "count": len(attempts),
            "reason": (
                "Original payment succeeded before "
                "recovery was completed."
            ),
        },
    )

    return len(attempts)


# =============================================================
# WEBHOOK ENDPOINT
# =============================================================


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str | None = Header(default=None),
    x_razorpay_event_id: str | None = Header(default=None),
):
    """
    Receive and process Razorpay webhook events.

    Processing flow:

    1. Read raw request body.
    2. Validate required Razorpay headers.
    3. Verify webhook signature.
    4. Parse JSON.
    5. Validate event type.
    6. Check webhook event idempotency.
    7. Persist the webhook event.
    8. Dispatch the event.
    9. Mark the webhook event as processed.
    10. Commit the transaction.
    11. Return successful acknowledgement.
    """

    # ---------------------------------------------------------
    # 1. Read raw request body
    # ---------------------------------------------------------

    raw_body = await request.body()

    if not raw_body:
        raise HTTPException(
            status_code=400,
            detail="Empty webhook body.",
        )

    # ---------------------------------------------------------
    # 2. Validate required Razorpay headers
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
    # 3. Verify signature BEFORE parsing JSON
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
    # 4. Parse JSON AFTER signature verification
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

    # ---------------------------------------------------------
    # 5. Validate event type
    # ---------------------------------------------------------

    event = payload.get("event")

    if not event:
        raise HTTPException(
            status_code=400,
            detail="Missing event type.",
        )

    # ---------------------------------------------------------
    # 6. Idempotency check
    # ---------------------------------------------------------

    existing_event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.event_id
            == x_razorpay_event_id,
        )
        .first()
    )

    if existing_event:
        print(
            "Duplicate Razorpay webhook ignored:",
            {
                "event_id": x_razorpay_event_id,
                "event": event,
                "status": existing_event.status,
            },
        )

        return {
            "success": True,
            "event": event,
            "event_id": x_razorpay_event_id,
            "duplicate": True,
        }

    # ---------------------------------------------------------
    # 7. Persist webhook event
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

        print(
            "Duplicate Razorpay webhook detected by database:",
            {
                "event_id": x_razorpay_event_id,
                "event": event,
            },
        )

        return {
            "success": True,
            "event": event,
            "event_id": x_razorpay_event_id,
            "duplicate": True,
        }

    # ---------------------------------------------------------
    # 8. Safe logging
    # ---------------------------------------------------------

    print(
        "Razorpay webhook received:",
        {
            "event_id": x_razorpay_event_id,
            "event": event,
        },
    )

    # ---------------------------------------------------------
    # 9. Dispatch event
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

        else:
            print(
                f"Unhandled Razorpay event: {event}"
            )

        webhook_event.status = "processed"

        # -----------------------------------------------------
        # 10. Commit webhook + payment changes together
        # -----------------------------------------------------

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
    # 11. Acknowledge webhook
    # ---------------------------------------------------------

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
    Persist a failed Razorpay payment and trigger the recovery
    evaluation workflow.
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
            Payment.razorpay_order_id == order_id,
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

    recovery_service = get_recovery_service(
        db=db,
    )

    (
        recovery_attempt,
        recovery_decision,
        guardrail_result,
        execution_result,
    ) = recovery_service.evaluate_and_execute(
        payment,
    )

    print(
        "Recovery workflow completed:",
        {
            "payment_db_id": payment.id,
            "attempt_id": recovery_attempt.id,
            "action": recovery_decision.action,
            "allowed": guardrail_result.allowed,
            "execution_status": execution_result.status,
            "provider_reference_id": (
                execution_result.reference_id
            ),
        },
    )

    print(
        "Payment failed:",
        {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": payment_data.get("amount"),
            "currency": payment_data.get("currency"),
            "method": payment_data.get("method"),
            "error_code": payment_data.get("error_code"),
            "error_description": payment_data.get(
                "error_description"
            ),
            "error_source": payment_data.get(
                "error_source"
            ),
            "error_step": payment_data.get(
                "error_step"
            ),
            "error_reason": payment_data.get(
                "error_reason"
            ),
        },
    )


async def handle_payment_captured(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle a captured Razorpay payment.

    A captured payment can belong to either:

    1. A recovery order created by ReviveAI.
    2. The original payment order.

    Recovery payments complete the corresponding recovery attempt.

    Original payment success cancels any active recovery attempts
    because recovery is no longer necessary.
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
            "payment.captured event missing payment ID."
        )

    if not order_id:
        raise ValueError(
            "payment.captured event missing order ID."
        )

    # ---------------------------------------------------------
    # 1. Check whether this belongs to a recovery order
    # ---------------------------------------------------------

    recovery_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.provider_reference_id
            == order_id,
        )
        .first()
    )

    if recovery_attempt:
        recovery_attempt.status = "completed"
        recovery_attempt.recovered = True
        recovery_attempt.completed_at = datetime.now(
            UTC
        )

        print(
            "Recovery payment captured:",
            {
                "payment_id": payment_id,
                "recovery_order_id": order_id,
                "recovery_attempt_id": (
                    recovery_attempt.id
                ),
                "original_payment_id": (
                    recovery_attempt.payment_id
                ),
                "amount": payment_data.get("amount"),
                "currency": payment_data.get("currency"),
            },
        )

        return

    # ---------------------------------------------------------
    # 2. Otherwise process as a normal payment
    # ---------------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id,
        )
        .first()
    )

    if not payment:
        raise ValueError(
            f"Payment record not found for Razorpay order {order_id}."
        )

    payment.razorpay_payment_id = payment_id

    # Do not downgrade a payment that has already reached
    # the final "paid" state due to webhook arrival order.
    if payment.status != "paid":
        payment.status = "captured"

    print(
        "Payment captured:",
        {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": payment_data.get("amount"),
            "currency": payment_data.get("currency"),
            "method": payment_data.get("method"),
        },
    )


async def handle_order_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle order.paid.

    The order may belong to:

    1. A ReviveAI recovery order.
    2. An original payment record.

    Recovery orders must not be treated as original orders.

    When an original order is paid, any active recovery attempts
    are cancelled because recovery is no longer required.
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
    # 1. Check whether this is a recovery order
    # ---------------------------------------------------------

    recovery_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.provider_reference_id
            == order_id,
        )
        .first()
    )

    if recovery_attempt:
        # payment.captured may already have completed this
        # recovery. Keep this operation idempotent.
        if recovery_attempt.status != "completed":
            recovery_attempt.status = "completed"
            recovery_attempt.recovered = True
            recovery_attempt.completed_at = datetime.now(
                UTC
            )

        print(
            "Recovery order paid:",
            {
                "recovery_order_id": order_id,
                "recovery_attempt_id": (
                    recovery_attempt.id
                ),
                "original_payment_id": (
                    recovery_attempt.payment_id
                ),
                "amount": order.get("amount"),
                "amount_paid": order.get("amount_paid"),
                "currency": order.get("currency"),
            },
        )

        return

    # ---------------------------------------------------------
    # 2. Process as original order
    # ---------------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == order_id,
        )
        .first()
    )

    if not payment:
        raise ValueError(
            "Payment record not found for "
            f"Razorpay order {order_id}."
        )

    payment.status = "paid"

    # This is intentionally safe even if payment.captured already
    # cancelled the attempts. There will simply be zero active
    # attempts remaining.
    cancelled_count = cancel_active_recovery_attempts(
        payment,
        db,
    )

    print(
        "Order paid:",
        {
            "order_id": order_id,
            "amount": order.get("amount"),
            "amount_paid": order.get("amount_paid"),
            "currency": order.get("currency"),
            "status": order.get("status"),
            "cancelled_recovery_attempts": (
                cancelled_count
            ),
        },
    )


async def handle_payment_link_paid(
    payload: dict,
    db: Session,
) -> None:
    """
    Handle payment_link.paid.

    Payment-link events are logged separately because they do not
    necessarily map directly to a payments-table order ID.
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