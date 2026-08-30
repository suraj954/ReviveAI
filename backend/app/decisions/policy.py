from dataclasses import dataclass

from app.ml.features import PaymentFeatures
from app.models.enums import RecoveryAction


@dataclass(frozen=True)
class RecoveryDecision:
    """
    Explainable recovery intervention selected for a payment.
    """

    action: str
    reason: str
    recovery_probability: float | None = None


# Conservative threshold for attempting an automated recovery.
RECOVERY_PROBABILITY_THRESHOLD = 0.55


def decide_recovery(
    features: PaymentFeatures,
    recovery_probability: float | None = None,
) -> RecoveryDecision:
    """
    Select a bounded recovery intervention.

    Rules:
    - Captured and paid payments are never recovered.
    - Failed payments may receive an immediate retry.
    - Created payments may receive a delayed retry.
    - ML probability influences failed-payment recovery decisions.
    """

    # ---------------------------------------------------------
    # Successful payment states
    # ---------------------------------------------------------

    if features.payment_status_captured == 1:
        return RecoveryDecision(
            action=RecoveryAction.NO_ACTION.value,
            reason=(
                "Payment is already captured successfully."
            ),
            recovery_probability=recovery_probability,
        )

    if features.payment_status_paid == 1:
        return RecoveryDecision(
            action=RecoveryAction.NO_ACTION.value,
            reason=(
                "Payment is already paid successfully."
            ),
            recovery_probability=recovery_probability,
        )

    # ---------------------------------------------------------
    # Failed payment → immediate recovery retry
    # ---------------------------------------------------------

    if features.payment_status_failed == 1:

        if recovery_probability is not None:
            if (
                recovery_probability
                >= RECOVERY_PROBABILITY_THRESHOLD
            ):
                return RecoveryDecision(
                    action=RecoveryAction.RETRY.value,
                    reason=(
                        "Payment failed and AI recovery score "
                        f"({recovery_probability:.2f}) exceeds "
                        "the intervention threshold."
                    ),
                    recovery_probability=recovery_probability,
                )

            return RecoveryDecision(
                action=RecoveryAction.NO_ACTION.value,
                reason=(
                    "Payment failed, but AI recovery score "
                    f"({recovery_probability:.2f}) is below "
                    "the intervention threshold."
                ),
                recovery_probability=recovery_probability,
            )

        return RecoveryDecision(
            action=RecoveryAction.RETRY.value,
            reason=(
                "Payment failed and is eligible for a bounded "
                "recovery retry."
            ),
            recovery_probability=None,
        )

    # ---------------------------------------------------------
    # Created payment → delayed retry
    # ---------------------------------------------------------

    if features.payment_status_created == 1:
        return RecoveryDecision(
            action=RecoveryAction.WAIT_AND_RETRY.value,
            reason=(
                "Payment is still created/pending and should "
                "wait before retrying."
            ),
            recovery_probability=recovery_probability,
        )

    # ---------------------------------------------------------
    # Unknown / unsupported state
    # ---------------------------------------------------------

    return RecoveryDecision(
        action=RecoveryAction.NO_ACTION.value,
        reason=(
            "Payment state is not eligible for automated recovery."
        ),
        recovery_probability=recovery_probability,
    )