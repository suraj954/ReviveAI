from __future__ import annotations

from dataclasses import dataclass

from sklearn.linear_model import LogisticRegression

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
    Supervised ML model for payment recovery.

    The model learns whether a recovery attempt is likely
    to succeed based on the payment feature vector.

    LogisticRegression is intentionally used as the first model
    because its output is probabilistic and explainable.
    """

    def __init__(self) -> None:
        self._model = LogisticRegression(
            max_iter=1000,
        )
        self._trained = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def train(self, dataset: TrainingDataset) -> None:
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

        if len(set(dataset.y)) < 2:
            raise ValueError(
                "Recovery model requires at least two outcome classes."
            )

        self._model.fit(dataset.X, dataset.y)
        self._trained = True

    def predict(self, features: list[float]) -> RecoveryPrediction:
        """
        Predict recovery probability for one payment.
        """

        if not self._trained:
            raise RuntimeError(
                "Recovery model has not been trained."
            )

        probability = float(
            self._model.predict_proba([features])[0][1]
        )

        return RecoveryPrediction(
            recovery_probability=probability,
            recommended_retry=probability >= 0.5,
        )