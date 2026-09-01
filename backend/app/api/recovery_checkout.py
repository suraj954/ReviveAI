from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.recovery_attempt import RecoveryAttempt


router = APIRouter(
    prefix="/api/recovery-checkout",
    tags=["Recovery Checkout"],
)


# =============================================================
# RESPONSE SCHEMA
# =============================================================


class RecoveryCheckoutResponse(BaseModel):
    """
    Checkout information required by the frontend to open an
    existing Razorpay recovery order.

    This response does NOT imply that recovery has succeeded.
    Revenue recovery is confirmed only through a verified provider
    success webhook.
    """

    success: bool
    attempt_id: int
    payment_id: int
    order_id: str
    amount: int
    currency: str
    key_id: str
    status: str


# =============================================================
# RECOVERY CHECKOUT ENDPOINT
# =============================================================


@router.get(
    "/{attempt_id}",
    response_model=RecoveryCheckoutResponse,
    status_code=status.HTTP_200_OK,
)
def get_recovery_checkout(
    attempt_id: int,
    db: Session = Depends(get_db),
) -> RecoveryCheckoutResponse:
    """
    Return checkout information for an existing recovery attempt.

    Important:
    This endpoint does NOT create a new Razorpay order.

    Recovery orders are created only by the approved recovery
    execution pipeline. This endpoint exposes the existing provider
    order reference so the frontend can open Razorpay Checkout.
    """

    # ---------------------------------------------------------
    # Fetch recovery attempt
    # ---------------------------------------------------------

    recovery_attempt = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.id == attempt_id
        )
        .first()
    )

    if not recovery_attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recovery attempt not found.",
        )

    # ---------------------------------------------------------
    # Validate lifecycle state
    # ---------------------------------------------------------

    if recovery_attempt.status != "awaiting_payment":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recovery checkout is not available for "
                f"attempt status '{recovery_attempt.status}'."
            ),
        )

    if recovery_attempt.recovered is True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This recovery attempt has already succeeded.",
        )

    # ---------------------------------------------------------
    # Validate provider reference
    # ---------------------------------------------------------

    if not recovery_attempt.provider_reference_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recovery attempt does not have a provider "
                "checkout reference."
            ),
        )

    # ---------------------------------------------------------
    # Validate original payment
    # ---------------------------------------------------------

    payment = recovery_attempt.payment

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recovery attempt is missing its payment.",
        )

    # ---------------------------------------------------------
    # Return checkout configuration
    # ---------------------------------------------------------

    return RecoveryCheckoutResponse(
        success=True,
        attempt_id=recovery_attempt.id,
        payment_id=payment.id,
        order_id=recovery_attempt.provider_reference_id,
        amount=payment.amount,
        currency=payment.currency,
        key_id=settings.razorpay_key_id,
        status=recovery_attempt.status,
    )