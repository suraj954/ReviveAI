from __future__ import annotations

import random

from app.ml.model_store import save_recovery_model
from app.ml.train import train_recovery_model
from app.ml.training_dataset import TrainingDataset


def build_bootstrap_dataset(
    *,
    samples: int = 1000,
    seed: int = 42,
) -> TrainingDataset:
    """
    Build a deterministic synthetic bootstrap dataset.

    This dataset represents historical failed-payment recovery
    outcomes for development/demo purposes. In production, this
    should be replaced with real labeled recovery outcomes.

    Feature contract:
        0. amount
        1. currency_inr
        2. payment_status_created
        3. payment_status_paid
        4. payment_status_captured
        5. payment_status_failed
        6. has_receipt
        7. payment_age_seconds
    """

    rng = random.Random(seed)

    X: list[list[float]] = []
    y: list[int] = []

    for _ in range(samples):

        amount = rng.choice(
            [
                9900,
                19900,
                49900,
                99900,
                149900,
                249900,
                499900,
            ]
        )

        has_receipt = rng.choice([0, 1])

        # Historical failed payments are the relevant training
        # population for the recovery model.
        payment_age_seconds = rng.uniform(
            60,
            7 * 24 * 60 * 60,
        )

        # Synthetic recovery likelihood rule used only to generate
        # bootstrap labels with controlled variation.
        score = 0.55

        if amount <= 149900:
            score += 0.12
        elif amount >= 499900:
            score -= 0.12

        if has_receipt:
            score += 0.08

        if payment_age_seconds <= 24 * 60 * 60:
            score += 0.12
        elif payment_age_seconds >= 5 * 24 * 60 * 60:
            score -= 0.15

        score += rng.uniform(-0.25, 0.25)

        probability = max(
            0.05,
            min(0.95, score),
        )

        label = int(
            rng.random() < probability
        )

        features = [
            float(amount),
            1.0,  # INR
            0.0,  # created
            0.0,  # paid
            0.0,  # captured
            1.0,  # failed
            float(has_receipt),
            float(payment_age_seconds),
        ]

        X.append(features)
        y.append(label)

    return TrainingDataset(
        X=X,
        y=y,
    )


def main() -> None:
    """
    Train and persist the bootstrap recovery model.
    """

    dataset = build_bootstrap_dataset()

    model = train_recovery_model(
        dataset
    )

    path = save_recovery_model(model)

    positive_rate = sum(dataset.y) / len(dataset.y)

    print("Recovery ML model trained successfully.")
    print(f"Samples: {len(dataset.X)}")
    print(
        f"Positive recovery rate: "
        f"{positive_rate:.2%}"
    )
    print(f"Model artifact: {path}")


if __name__ == "__main__":
    main()