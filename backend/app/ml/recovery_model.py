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

    The model estimates the probability that a failed payment can
    be successfully recovered.

    A StandardScaler + LogisticRegression pipeline is used because
    it provides probabilistic, explainable, and lightweight predictions.
    """

    def __init__(self) -> None:
        self.pipeline = Pipeline(
            [
                (
                    "scaler",
                    StandardScaler(),
                ),
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
        """
        Return whether the model has been successfully trained.
        """

        return self._trained

    def train(
        self,
        dataset: TrainingDataset,
    ) -> None:
        """
        Train the recovery model using a validated dataset.
        """

        if not dataset.X:
            raise ValueError(
                "Cannot train recovery model with an empty dataset."
            )

        if len(dataset.X) != len(dataset.y):
            raise ValueError(
                "Feature and label counts must match."
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

        self.pipeline.fit(
            dataset.X,
            dataset.y,
        )

        self._trained = True

    def predict_probability(
        self,
        features: list[float],
    ) -> float:
        """
        Predict the probability of successful payment recovery.
        """

        if not self._trained:
            raise RuntimeError(
                "Recovery model has not been trained."
            )

        probability = self.pipeline.predict_proba(
            [features]
        )[0][1]

        return float(probability)

    def predict(
        self,
        features: list[float],
    ) -> RecoveryPrediction:
        """
        Predict recovery probability and retry recommendation.
        """

        probability = self.predict_probability(features)

        return RecoveryPrediction(
            recovery_probability=probability,
            recommended_retry=probability >= 0.5,
        )