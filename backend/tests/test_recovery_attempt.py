from datetime import UTC, datetime

from app.models.recovery_attempt import RecoveryAttempt


def test_recovery_attempt_model_defaults() -> None:
    attempt = RecoveryAttempt(
        payment_id=1,
        action="retry",
    )

    assert attempt.payment_id == 1
    assert attempt.action == "retry"
    assert attempt.attempt_number == 1
    assert attempt.status == "pending"
    assert attempt.recovered is None
    assert attempt.error_message is None
    assert attempt.completed_at is None


def test_recovery_attempt_can_store_success() -> None:
    now = datetime.now(UTC)

    attempt = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=2,
        status="success",
        recovered=True,
        created_at=now,
        completed_at=now,
    )

    assert attempt.payment_id == 1
    assert attempt.action == "retry"
    assert attempt.attempt_number == 2
    assert attempt.status == "success"
    assert attempt.recovered is True
    assert attempt.created_at == now
    assert attempt.completed_at == now