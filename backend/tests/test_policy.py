from app.decisions.policy import RecoveryDecision, decide_recovery
from app.ml.features import PaymentFeatures


def make_features(**overrides) -> PaymentFeatures:
    values = {
        "amount": 50000.0,
        "currency_inr": 1,
        "payment_status_created": 0,
        "payment_status_paid": 0,
        "payment_status_captured": 0,
        "payment_status_failed": 0,
        "has_receipt": 1,
        "payment_age_seconds": 10.0,
    }

    values.update(overrides)
    return PaymentFeatures(**values)


def test_captured_payment_requires_no_action() -> None:
    features = make_features(payment_status_captured=1)

    decision = decide_recovery(features)

    assert isinstance(decision, RecoveryDecision)
    assert decision.action == "no_action"
    assert "captured" in decision.reason.lower()


def test_paid_payment_requires_no_action() -> None:
    features = make_features(payment_status_paid=1)

    decision = decide_recovery(features)

    assert decision.action == "no_action"
    assert "paid" in decision.reason.lower()


def test_failed_payment_should_retry() -> None:
    features = make_features(payment_status_failed=1)

    decision = decide_recovery(features)

    assert decision.action == "retry"
    assert "failed" in decision.reason.lower()


def test_created_payment_should_wait_and_retry() -> None:
    features = make_features(payment_status_created=1)

    decision = decide_recovery(features)

    assert decision.action == "wait_and_retry"
    assert "created" in decision.reason.lower()


def test_unknown_payment_state_requires_no_action() -> None:
    features = make_features()

    decision = decide_recovery(features)

    assert decision.action == "no_action"
    assert "not eligible" in decision.reason.lower()