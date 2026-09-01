from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.razorpay.orders import create_order
from app.services.recovery_token import (
    issue_recovery_token,
    verify_recovery_token,
)


router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"],
)


# =============================================================
# REQUEST SCHEMA
# =============================================================

class CreateOrderRequest(BaseModel):
    """
    Request for creating a merchant payment order.

    `amount` is supplied in major currency units.
    For INR:
        500.00 means ₹500.00
    """

    amount: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=10,
    )

    receipt: str = Field(
        default="revive_demo",
        min_length=1,
        max_length=100,
    )


# =============================================================
# AMOUNT UTILITY
# =============================================================

def amount_to_smallest_unit(
    amount: Decimal,
) -> int:
    """
    Convert a major currency amount to the smallest currency unit.

    For INR:
        500.00 -> 50000 paise

    Decimal is used instead of float to avoid payment rounding errors.
    """

    normalized = amount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    amount_in_paise = int(
        normalized * Decimal("100")
    )

    if amount_in_paise <= 0:
        raise ValueError(
            "Amount must be greater than zero."
        )

    return amount_in_paise


# =============================================================
# RECOVERY STATUS ENDPOINT
# =============================================================

@router.get(
    "/recovery-status",
    status_code=status.HTTP_200_OK,
)
def get_recovery_status(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Return the customer-safe recovery status for a payment.

    This endpoint is strictly read-only.

    It never:
    - triggers recovery
    - creates recovery attempts
    - modifies payment state
    - calls the recovery executor

    Access is authorized using a short-lived signed recovery token
    issued when the original order was created.
    """

    # ---------------------------------------------------------
    # Extract Bearer token
    # ---------------------------------------------------------

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "expired"},
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "expired"},
        )

    # ---------------------------------------------------------
    # Verify signed recovery token
    # ---------------------------------------------------------

    try:
        payment_id = verify_recovery_token(token)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "expired"},
        ) from exc

    # ---------------------------------------------------------
    # Load original payment
    # ---------------------------------------------------------

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id
        )
        .first()
    )

    # Do not reveal whether the payment exists.
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "expired"},
        )

    # ---------------------------------------------------------
    # Find latest recovery attempt
    # ---------------------------------------------------------

    latest_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.payment_id == payment.id
        )
        .order_by(
            RecoveryAttempt.attempt_number.desc(),
            RecoveryAttempt.id.desc(),
        )
        .first()
    )

    # No recovery attempt exists yet.
    # The payment webhook or recovery pipeline may still be
    # processing.
    if not latest_attempt:
        return {
            "status": "pending",
        }

    attempt_status = latest_attempt.status

    # ---------------------------------------------------------
    # Recovery checkout is ready
    # ---------------------------------------------------------

    if (
        attempt_status == "awaiting_payment"
        and latest_attempt.recovered is not True
        and latest_attempt.provider_reference_id
    ):
        return {
            "status": "recovery_available",
            "checkout": {
                "order_id": (
                    latest_attempt.provider_reference_id
                ),
                "amount": payment.amount,
                "currency": payment.currency,
                "key_id": settings.razorpay_key_id,
            },
        }

    # ---------------------------------------------------------
    # Recovery successfully completed
    # ---------------------------------------------------------

    if (
        attempt_status == "completed"
        or latest_attempt.recovered is True
    ):
        return {
            "status": "resolved",
        }

    # ---------------------------------------------------------
    # Recovery unavailable / terminal failure states
    # ---------------------------------------------------------

    unavailable_statuses = {
        "blocked",
        "failed",
        "cancelled",
        "exhausted",
        "no_action",
    }

    if attempt_status in unavailable_statuses:
        return {
            "status": "unavailable",
        }

    # ---------------------------------------------------------
    # All remaining lifecycle states are processing
    # ---------------------------------------------------------

    return {
        "status": "pending",
    }


# =============================================================
# CREATE ORIGINAL PAYMENT ORDER
# =============================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_new_order(
    request: CreateOrderRequest,
    db: Session = Depends(get_db),
):
    """
    Create a Razorpay order and persist its local payment record.

    Internal monetary representation is always the smallest
    currency unit (paise for INR).
    """

    try:
        amount_in_paise = amount_to_smallest_unit(
            request.amount
        )

        normalized_currency = (
            request.currency.upper().strip()
        )

        order = create_order(
            amount_in_paise=amount_in_paise,
            currency=normalized_currency,
            receipt=request.receipt.strip(),
        )

        payment = Payment(
            razorpay_order_id=order["id"],
            amount=int(order["amount"]),
            currency=order["currency"],
            status=order["status"],
            receipt=request.receipt.strip(),
        )

        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Issue a short-lived signed token that allows the
        # customer storefront to poll recovery status without
        # exposing internal payment identifiers.
        recovery_access_token = issue_recovery_token(
            payment.id
        )

        return {
            "success": True,
            "payment_id": payment.id,
            "order_id": payment.razorpay_order_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "key_id": settings.razorpay_key_id,
            "recovery_access_token": recovery_access_token,
        }

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A conflicting payment record already exists."
            ),
        ) from exc

    except Exception as exc:
        db.rollback()

        # Do not expose provider/internal implementation details.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Unable to create payment order with "
                "the payment provider."
            ),
        ) from exc