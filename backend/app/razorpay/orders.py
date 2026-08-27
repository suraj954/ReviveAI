from typing import Any

from app.razorpay.client import client


def create_order(amount_in_rupees: float, receipt: str) -> dict[str, Any]:
    """
    Create a Razorpay order.

    Razorpay expects amount in the smallest currency unit.
    For INR:
        ₹500.00 -> 50000 paise
    """

    if amount_in_rupees <= 0:
        raise ValueError("Amount must be greater than zero.")

    amount_in_paise = int(round(amount_in_rupees * 100))

    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": receipt,
    }

    return client.order.create(data=order_data)