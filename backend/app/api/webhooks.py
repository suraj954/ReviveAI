import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings


router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)


def verify_razorpay_signature(
    raw_body: bytes,
    signature: str,
    webhook_secret: str,
) -> bool:
    """
    Verify a Razorpay webhook signature using HMAC-SHA256.

    Razorpay signs the raw request body using the webhook secret.
    The raw body must be used exactly as received.
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


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    x_razorpay_event_id: str | None = Header(default=None),
):
    """
    Receive and securely verify Razorpay webhook events.

    Responsibilities at this stage:
    - Read the raw request body.
    - Validate Razorpay signature.
    - Validate event ID.
    - Parse the JSON payload.
    - Identify the event.
    - Dispatch lightweight event handling.

    Persistent event storage, idempotency checks, queueing,
    and recovery processing will be implemented next.
    """

    # ---------------------------------------------------------
    # 1. Read the raw request body
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
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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
    # 6. Log only safe metadata
    # ---------------------------------------------------------
    print(
        "Razorpay webhook received:",
        {
            "event_id": x_razorpay_event_id,
            "event": event,
        },
    )

    # ---------------------------------------------------------
    # 7. Temporary event dispatch
    #
    # Heavy processing will NOT happen here.
    # In the next step, this will publish/store the event.
    # ---------------------------------------------------------
    if event == "payment.failed":
        await handle_payment_failed(payload)

    elif event == "payment.captured":
        await handle_payment_captured(payload)

    elif event == "order.paid":
        await handle_order_paid(payload)

    elif event == "payment_link.paid":
        await handle_payment_link_paid(payload)

    else:
        print(f"Unhandled Razorpay event: {event}")

    # ---------------------------------------------------------
    # 8. Acknowledge the webhook
    # ---------------------------------------------------------
    return {
        "success": True,
        "event": event,
        "event_id": x_razorpay_event_id,
    }


# =============================================================
# EVENT HANDLERS
# =============================================================


async def handle_payment_failed(payload: dict) -> None:
    """
    Handle payment.failed.

    For now we only extract the useful metadata.
    Persistent storage and recovery processing come next.
    """

    payment = (
        payload
        .get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    print(
        "Payment failed:",
        {
            "payment_id": payment.get("id"),
            "order_id": payment.get("order_id"),
            "amount": payment.get("amount"),
            "currency": payment.get("currency"),
            "method": payment.get("method"),
            "error_code": payment.get("error_code"),
            "error_description": payment.get("error_description"),
            "error_source": payment.get("error_source"),
            "error_step": payment.get("error_step"),
            "error_reason": payment.get("error_reason"),
        },
    )


async def handle_payment_captured(payload: dict) -> None:
    """
    Handle payment.captured.

    Persistent state updates will be implemented next.
    """

    payment = (
        payload
        .get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    print(
        "Payment captured:",
        {
            "payment_id": payment.get("id"),
            "order_id": payment.get("order_id"),
            "amount": payment.get("amount"),
            "currency": payment.get("currency"),
            "method": payment.get("method"),
        },
    )


async def handle_order_paid(payload: dict) -> None:
    """
    Handle order.paid.

    This event will later be reconciled against payment state
    so the same revenue is not counted twice.
    """

    order = (
        payload
        .get("payload", {})
        .get("order", {})
        .get("entity", {})
    )

    print(
        "Order paid:",
        {
            "order_id": order.get("id"),
            "amount": order.get("amount"),
            "amount_paid": order.get("amount_paid"),
            "currency": order.get("currency"),
            "status": order.get("status"),
        },
    )


async def handle_payment_link_paid(payload: dict) -> None:
    """
    Handle payment_link.paid.

    This will eventually mark a recovery opportunity as recovered.
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
            "amount_paid": payment_link.get("amount_paid"),
            "status": payment_link.get("status"),
        },
    )