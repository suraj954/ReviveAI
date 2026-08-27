from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.razorpay.orders import create_order


router = APIRouter(prefix="/api/orders", tags=["Orders"])


class CreateOrderRequest(BaseModel):
    amount: float
    receipt: str = "revive_demo"


@router.post("")
def create_new_order(request: CreateOrderRequest):
    try:
        order = create_order(
            amount_in_rupees=request.amount,
            receipt=request.receipt,
        )

        return {
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "status": order["status"],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc