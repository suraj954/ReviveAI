from __future__ import annotations

from dataclasses import dataclass

from app.ml.dataset import TrainingExample
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt


@dataclass(frozen=True)
class TrainingDataset:
    """
    ML-ready supervised learning dataset.

    X contains the numerical feature vectors.
    y contains the corresponding recovery outcomes.
    """

    X: list[list[float]]
    y: list[int]


def _features_to_vector(example: TrainingExample) -> list[float]:
    """
    Convert PaymentFeatures into a numerical ML vector.
    """

    features = example.features

    return [
        features.amount,
        float(features.currency_inr),
        float(features.payment_status_created),
        float(features.payment_status_paid),
        float(features.payment_status_captured),
        float(features.payment_status_failed),
        float(features.has_receipt),
        features.payment_age_seconds,
    ]


def build_training_dataset(
    examples: list[TrainingExample],
) -> TrainingDataset:
    """
    Assemble validated training examples into X and y.
    """

    X = [_features_to_vector(example) for example in examples]
    y = [example.label for example in examples]

    return TrainingDataset(
        X=X,
        y=y,
    )


def build_training_dataset_from_records(
    records: list[tuple[Payment, RecoveryAttempt]],
) -> TrainingDataset:
    """
    Build a training dataset directly from payment/recovery records.

    Records with incomplete recovery outcomes are rejected by
    build_training_example().
    """

    from app.ml.dataset import build_training_example

    examples = [
        build_training_example(payment, attempt)
        for payment, attempt in records
    ]

    return build_training_dataset(examples)