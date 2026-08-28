from app.decisions.policy import RecoveryDecision, decide_recovery
from app.ml.features import build_payment_features
from app.models.payment import Payment


class RecoveryAgent:
    """
    Orchestrates payment feature extraction and recovery decisions.

    The agent currently uses the deterministic baseline policy.
    A trained ML model can be introduced behind this interface later.
    """

    def evaluate(
        self,
        payment: Payment,
    ) -> RecoveryDecision:
        """
        Evaluate a payment and return the recommended recovery action.
        """

        features = build_payment_features(payment)

        return decide_recovery(features)