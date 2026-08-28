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


def test_train_recovery_model() -> None:
    dataset = make_dataset()

    model = train_recovery_model(dataset)

    assert model is not None
    assert model.pipeline is not None


def test_model_returns_probability() -> None:
    dataset = make_dataset()

    model = train_recovery_model(dataset)

    probability = model.predict_probability(
        dataset.X[0]
    )

    assert 0.0 <= probability <= 1.0


def test_empty_dataset_is_rejected() -> None:
    dataset = TrainingDataset(
        X=[],
        y=[],
    )

    try:
        train_recovery_model(dataset)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "empty" in str(exc).lower()


def test_mismatched_dataset_is_rejected() -> None:
    dataset = TrainingDataset(
        X=[
            [50000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 10.0],
        ],
        y=[],
    )

    try:
        train_recovery_model(dataset)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "counts must match" in str(exc)


def test_single_class_dataset_is_rejected() -> None:
    dataset = TrainingDataset(
        X=[
            [50000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 10.0],
            [100000.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 20.0],
        ],
        y=[1, 1],
    )

    try:
        train_recovery_model(dataset)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "both successful" in str(exc)