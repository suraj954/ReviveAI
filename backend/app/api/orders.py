from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import get_db
from app.models.payment import Payment
from app.razorpay.orders import create_order


router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"],
)


class CreateOrderRequest(BaseModel):
    """
    Request for creating a merchant payment order.

    `amount` is supplied in major currency units by the API client.
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


def amount_to_smallest_unit(
    amount: Decimal,
) -> int:
    """
    Convert a major currency amount to paise.

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

        return {
        "success": True,
        "payment_id": payment.id,
        "order_id": payment.razorpay_order_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,
        "key_id": settings.razorpay_key_id,
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