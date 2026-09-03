from __future__ import annotations

from typing import Protocol

from app.decisions.guardrails import (
    GuardrailResult,
    apply_guardrails,
)
from app.decisions.policy import (
    RecoveryDecision,
    decide_recovery,
)
from app.ml.features import build_payment_features
from app.models.payment import Payment


class RecoveryPredictor(Protocol):
    """
    Minimal contract required by the recovery agent.

    Any trained ML model used in production must implement
    predict_probability(feature_vector).
    """

    def predict_probability(
        self,
        features: list[float],
    ) -> float:
        ...


class RecoveryAgent:
    """
    ReviveAI recovery intelligence orchestrator.

    Pipeline:

        Payment
          ↓
        Feature extraction
          ↓
        ML recovery probability
          ↓
        Explainable intervention policy
          ↓
        Guardrails

    If no trained model is available, the system intentionally
    falls back to deterministic policy logic.
    """

    def __init__(
        self,
        model: RecoveryPredictor | None = None,
    ) -> None:
        self.model = model

    def _predict_recovery_probability(
        self,
        payment: Payment,
    ) -> float | None:
        """
        Return an ML-generated recovery probability when a trained
        model is available.

        Returns None only when the model artifact is unavailable and
        the system intentionally operates in deterministic fallback
        mode.
        """

        if self.model is None:
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

        probability = self.model.predict_probability(
            feature_vector
        )

        # Defensive normalization for model implementations.
        probability = float(probability)

        return max(
            0.0,
            min(1.0, probability),
        )

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