import pytest

from app.decisions.guardrails import apply_guardrails
from app.decisions.policy import RecoveryDecision


def test_no_action_is_blocked() -> None:
    decision = RecoveryDecision(
        action="no_action",
        reason="Payment already captured.",
    )

    result = apply_guardrails(decision)

    assert result.allowed is False
    assert "No recovery action" in result.reason


def test_retry_is_allowed_without_probability() -> None:
    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    result = apply_guardrails(decision)

    assert result.allowed is True


def test_retry_is_allowed_with_high_probability() -> None:
    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    result = apply_guardrails(
        decision,
        recovery_probability=0.85,
    )

    assert result.allowed is True


def test_retry_is_blocked_with_low_probability() -> None:
    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    result = apply_guardrails(
        decision,
        recovery_probability=0.30,
    )

    assert result.allowed is False
    assert "below the execution threshold" in result.reason


def test_boundary_probability_is_allowed() -> None:
    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    result = apply_guardrails(
        decision,
        recovery_probability=0.50,
    )

    assert result.allowed is True


def test_invalid_probability_is_rejected() -> None:
    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    with pytest.raises(
        ValueError,
        match="between 0.0 and 1.0",
    ):
        apply_guardrails(
            decision,
            recovery_probability=1.5,
        )


def test_unsupported_action_is_blocked() -> None:
    decision = RecoveryDecision(
        action="refund",
        reason="Unsupported action.",
    )

    result = apply_guardrails(decision)

    assert result.allowed is False
    assert "not permitted" in result.reason