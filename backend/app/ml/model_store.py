from __future__ import annotations

from pathlib import Path

import joblib

from app.ml.train import TrainedRecoveryModel


DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent / "artifacts" / "recovery_model.joblib"
)


def save_recovery_model(
    model: TrainedRecoveryModel,
    path: str | Path = DEFAULT_MODEL_PATH,
) -> Path:
    """
    Persist a trained recovery model to disk.
    """

    if not isinstance(model, TrainedRecoveryModel):
        raise TypeError(
            "model must be a TrainedRecoveryModel."
        )

    target = Path(path)
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(model, target)

    return target


def load_recovery_model(
    path: str | Path = DEFAULT_MODEL_PATH,
) -> TrainedRecoveryModel:
    """
    Load a persisted recovery model from disk.
    """

    target = Path(path)

    if not target.exists():
        raise FileNotFoundError(
            f"Recovery model artifact not found: {target}"
        )

    model = joblib.load(target)

    if not isinstance(model, TrainedRecoveryModel):
        raise TypeError(
            "Persisted artifact is not a TrainedRecoveryModel."
        )

    return model