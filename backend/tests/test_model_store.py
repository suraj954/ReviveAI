from pathlib import Path

import pytest

from app.ml.model_store import (
    load_recovery_model,
    save_recovery_model,
)
from app.ml.train import train_recovery_model
from app.ml.training_dataset import TrainingDataset


def make_dataset() -> TrainingDataset:
    return TrainingDataset(
        X=[
            [50000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 10.0],
            [100000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 20.0],
            [5000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 100.0],
            [75000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 200.0],
        ],
        y=[1, 1, 0, 0],
    )


def test_save_model_creates_artifact(tmp_path: Path) -> None:
    model = train_recovery_model(make_dataset())

    artifact_path = tmp_path / "recovery_model.joblib"

    saved_path = save_recovery_model(
        model,
        artifact_path,
    )

    assert saved_path == artifact_path
    assert artifact_path.exists()
    assert artifact_path.is_file()


def test_load_model_returns_trained_model(tmp_path: Path) -> None:
    model = train_recovery_model(make_dataset())

    artifact_path = tmp_path / "recovery_model.joblib"

    save_recovery_model(
        model,
        artifact_path,
    )

    loaded_model = load_recovery_model(
        artifact_path,
    )

    probability = loaded_model.predict_probability(
        make_dataset().X[0]
    )

    assert 0.0 <= probability <= 1.0


def test_loaded_model_preserves_prediction(
    tmp_path: Path,
) -> None:
    model = train_recovery_model(make_dataset())

    features = make_dataset().X[0]

    original_probability = model.predict_probability(
        features
    )

    artifact_path = tmp_path / "recovery_model.joblib"

    save_recovery_model(
        model,
        artifact_path,
    )

    loaded_model = load_recovery_model(
        artifact_path,
    )

    loaded_probability = loaded_model.predict_probability(
        features
    )

    assert loaded_probability == pytest.approx(
        original_probability,
    )


def test_missing_model_artifact_is_rejected(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "missing.joblib"

    with pytest.raises(
        FileNotFoundError,
        match="artifact not found",
    ):
        load_recovery_model(
            artifact_path,
        )


def test_invalid_model_type_is_rejected(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "invalid.joblib"

    import joblib

    joblib.dump(
        {"not": "a recovery model"},
        artifact_path,
    )

    with pytest.raises(
        TypeError,
        match="not a TrainedRecoveryModel",
    ):
        load_recovery_model(
            artifact_path,
        )