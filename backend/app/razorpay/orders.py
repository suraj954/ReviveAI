from __future__ import annotations

from typing import Any

from app.razorpay.client import client


def create_order(
    *,
    amount_in_paise: int,
    currency: str = "INR",
    receipt: str,
) -> dict[str, Any]:
    """
    Create a Razorpay order.

    Amount must be provided in the smallest currency unit.

    Examples:
        INR 500.00 -> 50000 paise
        INR 1.00   -> 100 paise

    Using integer smallest units avoids floating-point rounding
    errors in payment amounts.
    """

    if not isinstance(amount_in_paise, int):
        raise TypeError(
            "amount_in_paise must be an integer."
        )

    if amount_in_paise <= 0:
        raise ValueError(
            "amount_in_paise must be greater than zero."
        )

    normalized_currency = currency.upper().strip()

    if not normalized_currency:
        raise ValueError(
            "currency must not be empty."
        )

    if not receipt or not receipt.strip():
        raise ValueError(
            "receipt must not be empty."
        )

    order_data = {
        "amount": amount_in_paise,
        "currency": normalized_currency,
        "receipt": receipt.strip(),
    }

    return client.order.create(data=order_data)