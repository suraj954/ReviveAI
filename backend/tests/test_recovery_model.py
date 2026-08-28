from app.ml.recovery_model import RecoveryModel
from app.ml.training_dataset import TrainingDataset


def make_dataset() -> TrainingDataset:
    return TrainingDataset(
        X=[
            [50000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 10.0],
            [60000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 20.0],
            [10000.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 5.0],
            [15000.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 15.0],
        ],
        y=[1, 1, 0, 0],
    )


def test_model_starts_untrained() -> None:
    model = RecoveryModel()

    assert model.is_trained is False


def test_model_can_train() -> None:
    model = RecoveryModel()

    model.train(make_dataset())

    assert model.is_trained is True


def test_model_requires_training_before_prediction() -> None:
    model = RecoveryModel()

    try:
        model.predict(
            [50000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 10.0]
        )
    except RuntimeError as exc:
        assert "not been trained" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_model_produces_probability() -> None:
    model = RecoveryModel()
    model.train(make_dataset())

    prediction = model.predict(
        [50000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 10.0]
    )

    assert 0.0 <= prediction.recovery_probability <= 1.0
    assert isinstance(prediction.recommended_retry, bool)


def test_empty_dataset_is_rejected() -> None:
    model = RecoveryModel()

    try:
        model.train(
            TrainingDataset(
                X=[],
                y=[],
            )
        )
    except ValueError as exc:
        assert "empty dataset" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_single_class_dataset_is_rejected() -> None:
    model = RecoveryModel()

    try:
        model.train(
            TrainingDataset(
                X=[
                    [50000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 10.0],
                    [60000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 20.0],
                ],
                y=[1, 1],
            )
        )
    except ValueError as exc:
        assert "two outcome classes" in str(exc)
    else:
        raise AssertionError("Expected ValueError")