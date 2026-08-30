from __future__ import annotations

from dataclasses import dataclass

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.training_dataset import TrainingDataset


@dataclass(frozen=True)
class RecoveryPrediction:
    """
    Prediction produced by the recovery ML model.
    """

    recovery_probability: float
    recommended_retry: bool


class RecoveryModel:
    """
    Canonical supervised ML model for payment recovery prediction.

    Feature contract:

        0. amount
        1. currency_inr
        2. payment_status_created
        3. payment_status_paid
        4. payment_status_captured
        5. payment_status_failed
        6. has_receipt
        7. payment_age_seconds

    The model estimates the probability that a failed payment can
    be successfully recovered.
    """

    FEATURE_COUNT = 8
    RETRY_THRESHOLD = 0.55

    def __init__(self) -> None:
        self.pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
                        random_state=42,
                    ),
                ),
            ]
        )

        self._trained = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def train(
        self,
        dataset: TrainingDataset,
    ) -> None:
        """
        Train using a validated binary classification dataset.
        """

        if not dataset.X:
            raise ValueError(
                "Cannot train recovery model with an empty dataset."
            )

        if len(dataset.X) != len(dataset.y):
            raise ValueError(
                "Feature and label counts must match."
            )

        for index, row in enumerate(dataset.X):
            if len(row) != self.FEATURE_COUNT:
                raise ValueError(
                    f"Feature row {index} has {len(row)} features; "
                    f"expected {self.FEATURE_COUNT}."
                )

        unique_labels = set(dataset.y)

        if not unique_labels.issubset({0, 1}):
            raise ValueError(
                "Recovery model labels must be binary: 0 or 1."
            )

        if len(unique_labels) < 2:
            raise ValueError(
                "Recovery model requires at least two outcome classes."
            )

        self.pipeline.fit(dataset.X, dataset.y)
        self._trained = True

    def predict_probability(
        self,
        features: list[float],
    ) -> float:
        """
        Predict probability of successful payment recovery.
        """

        if not self._trained:
            raise RuntimeError(
                "Recovery model has not been trained."
            )

        self._validate_features(features)

        probability = self.pipeline.predict_proba(
            [features]
        )[0][1]

        return float(probability)

    def predict(
        self,
        features: list[float],
    ) -> RecoveryPrediction:
        """
        Predict recovery probability and recommendation.
        """

        probability = self.predict_probability(features)

        return RecoveryPrediction(
            recovery_probability=probability,
            recommended_retry=(
                probability >= self.RETRY_THRESHOLD
            ),
        )

    def _validate_features(
        self,
        features: list[float],
    ) -> None:
        if len(features) != self.FEATURE_COUNT:
            raise ValueError(
                f"Expected {self.FEATURE_COUNT} features, "
                f"received {len(features)}."
            )