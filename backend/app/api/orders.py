from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.payment import Payment
from app.razorpay.orders import create_order


router = APIRouter(prefix="/api/orders", tags=["Orders"])


class CreateOrderRequest(BaseModel):
    amount: float
    receipt: str = "revive_demo"


@router.post("")
def create_new_order(
    request: CreateOrderRequest,
    db: Session = Depends(get_db),
):
    try:
        # 1. Create order on Razorpay
        order = create_order(
            amount_in_rupees=request.amount,
            receipt=request.receipt,
        )

        # 2. Save the Razorpay order in PostgreSQL
        payment = Payment(
            razorpay_order_id=order["id"],
            amount=order["amount"],
            currency=order["currency"],
            status=order["status"],
            receipt=request.receipt,
        )

        db.add(payment)
        db.commit()
        db.refresh(payment)

        # 3. Return the Razorpay order
        return {
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "status": order["status"],
        }

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc