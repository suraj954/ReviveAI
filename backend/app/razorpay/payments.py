from typing import Any

from app.razorpay.client import client


def fetch_payment(payment_id: str) -> dict[str, Any]:
    """Fetch a payment from Razorpay using its payment ID."""
    return client.payment.fetch(payment_id)