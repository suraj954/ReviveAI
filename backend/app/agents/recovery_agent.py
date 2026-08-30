from app.decisions.guardrails import (
    GuardrailResult,
    apply_guardrails,
)
from app.decisions.policy import (
    RecoveryDecision,
    decide_recovery,
)
from app.ml.features import build_payment_features
from app.ml.recovery_model import RecoveryModel
from app.models.payment import Payment


class RecoveryAgent:
    """
    ReviveAI recovery intelligence orchestrator.

    Pipeline:

        Payment
          ↓
        Feature extraction
          ↓
        ML recovery probability (when trained model exists)
          ↓
        Explainable intervention policy
          ↓
        Guardrails
    """

    def __init__(
        self,
        model: RecoveryModel | None = None,
    ) -> None:
        self.model = model

    def _predict_recovery_probability(
        self,
        payment: Payment,
    ) -> float | None:
        """
        Return ML recovery probability when a trained model is
        available.

        Returns None when the system is operating in deterministic
        fallback mode.
        """

        if (
            self.model is None
            or not self.model.is_trained
        ):
            return None

        features = build_payment_features(payment)

        feature_vector = [
            features.amount,
            float(features.currency_inr),
            float(features.payment_status_created),
            float(features.payment_status_paid),
            float(features.payment_status_captured),
            float(features.payment_status_failed),
            float(features.has_receipt),
            features.payment_age_seconds,
        ]

        prediction = self.model.predict(feature_vector)

        return prediction.recovery_probability

    def evaluate(
        self,
        payment: Payment,
    ) -> RecoveryDecision:
        """
        Evaluate payment and select an explainable intervention.
        """

        features = build_payment_features(payment)

        recovery_probability = (
            self._predict_recovery_probability(payment)
        )

        return decide_recovery(
            features,
            recovery_probability=recovery_probability,
        )

    def evaluate_with_guardrails(
        self,
        payment: Payment,
    ) -> tuple[
        RecoveryDecision,
        GuardrailResult,
    ]:
        """
        Evaluate intervention and apply mandatory guardrails.
        """

        decision = self.evaluate(payment)

        guardrail_result = apply_guardrails(
            decision,
            recovery_probability=(
                decision.recovery_probability
            ),
        )

        return decision, guardrail_result