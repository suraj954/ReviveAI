from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.payment import Payment


@dataclass(frozen=True)
class PaymentFeatures:
    """
    ML-ready features extracted from a payment record.

    These features form the initial input layer for the
    ReviveAI intelligence engine.
    """

    amount: float
    currency_inr: int
    payment_status_created: int
    payment_status_paid: int
    payment_status_captured: int
    payment_status_failed: int
    has_receipt: int
    payment_age_seconds: float


def build_payment_features(
    payment: Payment,
    *,
    now: datetime | None = None,
) -> PaymentFeatures:
    """
    Convert a Payment database model into an ML-ready feature vector.
    """

    if now is None:
        now = datetime.utcnow()

    age_seconds = max(
        0.0,
        (now - payment.created_at).total_seconds(),
    )

    status = payment.status.lower()

    return PaymentFeatures(
        amount=float(payment.amount),
        currency_inr=int(payment.currency.upper() == "INR"),
        payment_status_created=int(status == "created"),
        payment_status_paid=int(status == "paid"),
        payment_status_captured=int(status == "captured"),
        payment_status_failed=int(status == "failed"),
        has_receipt=int(bool(payment.receipt)),
        payment_age_seconds=age_seconds,
    )