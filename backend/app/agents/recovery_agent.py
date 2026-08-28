from app.decisions.guardrails import GuardrailResult, apply_guardrails
from app.decisions.policy import RecoveryDecision, decide_recovery
from app.ml.features import build_payment_features
from app.ml.recovery_model import RecoveryModel
from app.models.payment import Payment


class RecoveryAgent:
    """
    Orchestrates payment feature extraction, recovery prediction,
    deterministic policy decisions, and safety guardrails.

    The ML model provides a recovery probability, but the policy
    and guardrails remain responsible for determining whether an
    action is safe.
    """

    def __init__(
        self,
        model: RecoveryModel | None = None,
    ) -> None:
        self.model = model

    def evaluate(
        self,
        payment: Payment,
    ) -> RecoveryDecision:
        """
        Evaluate a payment using the deterministic recovery policy.

        This preserves the existing baseline behavior.
        """

        features = build_payment_features(payment)

        return decide_recovery(features)

    def evaluate_with_guardrails(
        self,
        payment: Payment,
    ) -> tuple[RecoveryDecision, GuardrailResult]:
        """
        Evaluate a payment and apply safety guardrails.

        If a trained ML model is available, its recovery probability
        is passed to the guardrail layer. Otherwise the deterministic
        policy is evaluated without ML probability.
        """

        features = build_payment_features(payment)
        decision = decide_recovery(features)

        recovery_probability: float | None = None

        if self.model is not None and self.model.is_trained:
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
            recovery_probability = prediction.recovery_probability

        guardrail_result = apply_guardrails(
            decision,
            recovery_probability=recovery_probability,
        )

        return decision, guardrail_result