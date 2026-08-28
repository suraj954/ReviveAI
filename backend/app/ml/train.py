from __future__ import annotations

from dataclasses import dataclass

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.training_dataset import TrainingDataset


@dataclass(frozen=True)
class TrainedRecoveryModel:
    """
    Trained ML model for predicting recovery success.

    The model outputs the probability that a recovery attempt
    will successfully recover the payment.
    """

    pipeline: Pipeline

    def predict_probability(
        self,
        features: list[float],
    ) -> float:
        """
        Return the predicted probability of recovery success.
        """

        probability = self.pipeline.predict_proba([features])[0][1]

        return float(probability)


def train_recovery_model(
    dataset: TrainingDataset,
) -> TrainedRecoveryModel:
    """
    Train a supervised recovery-success model.

    The training dataset must contain both successful and
    unsuccessful recovery outcomes.
    """

    if not dataset.X:
        raise ValueError(
            "Training dataset cannot be empty."
        )

    if len(dataset.X) != len(dataset.y):
        raise ValueError(
            "Feature and label counts must match."
        )

    unique_labels = set(dataset.y)

    if not unique_labels.issubset({0, 1}):
        raise ValueError(
            "Training labels must be binary: 0 or 1."
        )

    if len(unique_labels) < 2:
        raise ValueError(
            "Training dataset must contain both successful "
            "and unsuccessful recovery outcomes."
        )

    pipeline = Pipeline(
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

    pipeline.fit(
        dataset.X,
        dataset.y,
    )

    return TrainedRecoveryModel(
        pipeline=pipeline,
    )