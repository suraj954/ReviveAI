from dataclasses import dataclass

from app.ml.features import PaymentFeatures


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str


def decide_recovery(features: PaymentFeatures) -> RecoveryDecision:
    """
    Deterministic baseline recovery policy.

    This is intentionally rule-based. The ML model will later
    learn to improve or replace these decisions.
    """

    if features.payment_status_captured == 1:
        return RecoveryDecision(
            action="no_action",
            reason="Payment has already been captured.",
        )

    if features.payment_status_paid == 1:
        return RecoveryDecision(
            action="no_action",
            reason="Payment is already marked as paid.",
        )

    if features.payment_status_failed == 1:
        return RecoveryDecision(
            action="retry",
            reason="Payment failed and is eligible for recovery.",
        )

    if features.payment_status_created == 1:
        return RecoveryDecision(
            action="wait_and_retry",
            reason="Payment is still in the created state.",
        )

    return RecoveryDecision(
        action="no_action",
        reason="Payment state is not eligible for a recovery action.",
    )