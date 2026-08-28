from __future__ import annotations

from dataclasses import dataclass

from app.ml.features import PaymentFeatures
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt


@dataclass(frozen=True)
class TrainingExample:
    """
    One supervised-learning example.

    Features describe the payment at the time of evaluation.
    Label represents whether the recovery attempt succeeded.
    """

    features: PaymentFeatures
    label: int


def build_training_example(
    payment: Payment,
    attempt: RecoveryAttempt,
) -> TrainingExample:
    """
    Convert a payment/recovery-attempt pair into a training example.

    Only completed recovery outcomes are valid training labels.
    """

    if attempt.recovered is None:
        raise ValueError(
            "Recovery attempt must have a completed recovery outcome."
        )

    features = PaymentFeatures(
        amount=float(payment.amount),
        currency_inr=int(payment.currency.upper() == "INR"),
        payment_status_created=int(payment.status.lower() == "created"),
        payment_status_paid=int(payment.status.lower() == "paid"),
        payment_status_captured=int(payment.status.lower() == "captured"),
        payment_status_failed=int(payment.status.lower() == "failed"),
        has_receipt=int(bool(payment.receipt)),
        payment_age_seconds=max(
            0.0,
            (attempt.created_at - payment.created_at).total_seconds(),
        ),
    )

    return TrainingExample(
        features=features,
        label=int(attempt.recovered),
    )