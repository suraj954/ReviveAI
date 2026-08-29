from datetime import datetime

import pytest

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.services.recovery_executor import RecoveryExecutionResult
from app.services.recovery_service import RecoveryService


class FakeQuery:
    def __init__(self, attempts):
        self.attempts = attempts

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.attempts[-1] if self.attempts else None


class FakeSession:
    def __init__(self):
        self.attempts = []
        self.added = []

    def query(self, model):
        return FakeQuery(self.attempts)

    def add(self, obj):
        self.added.append(obj)
        self.attempts.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


class FakeAgent:
    def __init__(
        self,
        decision: RecoveryDecision,
        guardrail: GuardrailResult,
    ):
        self.decision = decision
        self.guardrail = guardrail

    def evaluate(self, payment):
        return self.decision

    def evaluate_with_guardrails(self, payment):
        return self.decision, self.guardrail


class FakeExecutor:
    """
    Test double for RecoveryExecutor.

    The fake follows the same contract as the real executor:
    it receives the complete Payment object rather than only
    payment.id.
    """

    def __init__(
        self,
        result: RecoveryExecutionResult | None = None,
        error: Exception | None = None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def execute(
        self,
        payment,
        decision,
        guardrail_result,
    ):
        self.calls.append(
            (
                payment,
                decision.action,
                guardrail_result.allowed,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result


def make_payment(
    status: str,
    payment_id: int = 1,
) -> Payment:
    payment = Payment(
        razorpay_order_id=f"order_{payment_id}",
        amount=50000,
        currency="INR",
        status=status,
        receipt="test_receipt",
        created_at=datetime.utcnow(),
    )

    payment.id = payment_id

    return payment


def test_failed_payment_creates_retry_attempt() -> None:
    db = FakeSession()
    service = RecoveryService(db)

    attempt = service.evaluate_and_record(
        make_payment("failed"),
    )

    assert attempt.payment_id == 1
    assert attempt.action == "retry"
    assert attempt.attempt_number == 1
    assert attempt.status == "pending"

    assert len(db.added) == 1


def test_second_attempt_increments_attempt_number() -> None:
    db = FakeSession()

    existing = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=1,
    )

    db.attempts.append(existing)

    service = RecoveryService(db)

    attempt = service.evaluate_and_record(
        make_payment("failed"),
    )

    assert attempt.attempt_number == 2
    assert attempt.action == "retry"


def test_captured_payment_creates_no_action_attempt() -> None:
    db = FakeSession()
    service = RecoveryService(db)

    attempt = service.evaluate_and_record(
        make_payment("captured"),
    )

    assert attempt.payment_id == 1
    assert attempt.action == "no_action"
    assert attempt.attempt_number == 1


def test_execution_requires_executor() -> None:
    db = FakeSession()
    service = RecoveryService(db)

    with pytest.raises(
        RuntimeError,
        match="RecoveryExecutor is required",
    ):
        service.evaluate_and_execute(
            make_payment("failed"),
        )


def test_successful_recovery_is_persisted() -> None:
    db = FakeSession()

    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    execution = RecoveryExecutionResult(
        executed=True,
        action="retry",
        status="executed",
        reference_id="retry_1",
        reason="Recovery retry was executed successfully.",
    )

    agent = FakeAgent(
        decision,
        guardrail,
    )

    executor = FakeExecutor(
        result=execution,
    )

    service = RecoveryService(
        db,
        agent=agent,
        executor=executor,
    )

    (
        attempt,
        returned_decision,
        returned_guardrail,
        returned_execution,
    ) = service.evaluate_and_execute(
        payment,
    )

    assert returned_decision == decision
    assert returned_guardrail == guardrail
    assert returned_execution == execution

    assert attempt.action == "retry"
    assert attempt.status == "completed"
    assert attempt.recovered is True
    assert attempt.provider_reference_id == "retry_1"
    assert attempt.error_message is None
    assert attempt.completed_at is not None

    assert executor.calls == [
        (payment, "retry", True),
    ]


def test_blocked_recovery_is_not_executed() -> None:
    db = FakeSession()

    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    guardrail = GuardrailResult(
        allowed=False,
        reason="Recovery probability is below the execution threshold.",
    )

    agent = FakeAgent(
        decision,
        guardrail,
    )

    executor = FakeExecutor()

    service = RecoveryService(
        db,
        agent=agent,
        executor=executor,
    )

    (
        attempt,
        _,
        _,
        execution,
    ) = service.evaluate_and_execute(
        payment,
    )

    assert attempt.status == "blocked"
    assert attempt.recovered is False
    assert attempt.error_message == guardrail.reason
    assert attempt.completed_at is not None

    assert execution.executed is False
    assert execution.status == "blocked"
    assert attempt.provider_reference_id is None

    # Guardrails must prevent the executor from being called.
    assert executor.calls == []


def test_failed_execution_is_persisted() -> None:
    db = FakeSession()

    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    agent = FakeAgent(
        decision,
        guardrail,
    )

    executor = FakeExecutor(
        error=RuntimeError("Gateway unavailable"),
    )

    service = RecoveryService(
        db,
        agent=agent,
        executor=executor,
    )

    (
        attempt,
        _,
        _,
        execution,
    ) = service.evaluate_and_execute(
        payment,
    )

    assert attempt.status == "failed"
    assert attempt.recovered is False
    assert attempt.error_message == "Gateway unavailable"
    assert attempt.provider_reference_id is None
    assert attempt.completed_at is not None

    assert execution.executed is False
    assert execution.status == "failed"

    assert executor.calls == [
        (payment, "retry", True),
    ]


def test_executor_returning_blocked_result_is_persisted() -> None:
    db = FakeSession()

    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    execution = RecoveryExecutionResult(
        executed=False,
        action="retry",
        status="blocked",
        reference_id=None,
        reason="Gateway rejected the recovery request.",
    )

    agent = FakeAgent(
        decision,
        guardrail,
    )

    executor = FakeExecutor(
        result=execution,
    )

    service = RecoveryService(
        db,
        agent=agent,
        executor=executor,
    )

    (
        attempt,
        _,
        _,
        returned_execution,
    ) = service.evaluate_and_execute(
        payment,
    )

    assert returned_execution == execution
    assert attempt.status == "blocked"
    assert attempt.recovered is False
    assert attempt.error_message == execution.reason
    assert attempt.provider_reference_id is None

    assert executor.calls == [
        (payment, "retry", True),
    ]

