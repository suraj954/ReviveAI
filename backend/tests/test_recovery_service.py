from datetime import datetime, timezone

import pytest

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.services.recovery_executor import RecoveryExecutionResult
from app.services.recovery_service import RecoveryService


class FakeQuery:
    def __init__(self, items):
        self.items = items

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        if not self.items:
            return None
        return self.items[-1]

    def scalar(self):
        return len(self.items)


class FakeSession:
    def __init__(self):
        self.attempts = []
        self.added = []

    def query(self, model):
        return FakeQuery(self.attempts)

    def add(self, obj):
        self.added.append(obj)
        self.attempts.append(obj)

    def flush(self):
        pass

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

    def evaluate_with_guardrails(self, payment):
        return self.decision, self.guardrail


class FakeExecutor:
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
        created_at=datetime.now(timezone.utc),
    )

    payment.id = payment_id
    return payment


def make_agent(
    action: str = "retry",
    allowed: bool = True,
) -> FakeAgent:
    return FakeAgent(
        RecoveryDecision(
            action=action,
            reason="Test recovery decision.",
            recovery_probability=0.8,
        ),
        GuardrailResult(
            allowed=allowed,
            reason="Test guardrail result.",
        ),
    )


def test_failed_payment_creates_retry_attempt() -> None:
    db = FakeSession()

    service = RecoveryService(
        db,
        agent=make_agent(),
    )

    (
        attempt,
        decision,
        guardrail,
    ) = service.evaluate_and_record(
        make_payment("failed"),
    )

    assert attempt is not None
    assert attempt.payment_id == 1
    assert attempt.action == "retry"
    assert attempt.attempt_number == 1
    assert attempt.status == "approved"

    assert decision.action == "retry"
    assert guardrail.allowed is True
    assert len(db.added) == 1


def test_second_attempt_increments_attempt_number() -> None:
    db = FakeSession()

    existing = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=1,
    )

    db.attempts.append(existing)

    service = RecoveryService(
        db,
        agent=make_agent(),
    )

    (
        attempt,
        _,
        _,
    ) = service.evaluate_and_record(
        make_payment("failed"),
    )

    assert attempt is not None
    assert attempt.attempt_number == 2
    assert attempt.action == "retry"


def test_captured_payment_creates_no_attempt() -> None:
    db = FakeSession()

    service = RecoveryService(
        db,
        agent=make_agent(),
    )

    (
        attempt,
        decision,
        guardrail,
    ) = service.evaluate_and_record(
        make_payment("captured"),
    )

    assert attempt is None
    assert decision.action == "no_action"
    assert guardrail.allowed is False
    assert len(db.added) == 0


def test_paid_payment_creates_no_attempt() -> None:
    db = FakeSession()

    service = RecoveryService(
        db,
        agent=make_agent(),
    )

    (
        attempt,
        decision,
        guardrail,
    ) = service.evaluate_and_record(
        make_payment("paid"),
    )

    assert attempt is None
    assert decision.action == "no_action"
    assert guardrail.allowed is False


def test_no_action_decision_creates_no_attempt() -> None:
    db = FakeSession()

    service = RecoveryService(
        db,
        agent=make_agent(
            action="no_action",
            allowed=False,
        ),
    )

    (
        attempt,
        decision,
        guardrail,
    ) = service.evaluate_and_record(
        make_payment("failed"),
    )

    assert attempt is None
    assert decision.action == "no_action"
    assert guardrail.allowed is False
    assert len(db.added) == 0


def test_execution_requires_executor() -> None:
    db = FakeSession()

    service = RecoveryService(
        db,
        agent=make_agent(),
    )

    with pytest.raises(
        RuntimeError,
        match="RecoveryExecutor is required",
    ):
        service.evaluate_and_execute(
            make_payment("failed"),
        )


def test_successful_recovery_execution_is_persisted() -> None:
    db = FakeSession()
    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
        recovery_probability=0.9,
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    execution = RecoveryExecutionResult(
        executed=True,
        action="retry",
        status="awaiting_payment",
        reference_id="retry_1",
        reason=(
            "Recovery checkout created successfully. "
            "Awaiting verified payment completion."
        ),
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
    ) = service.evaluate_and_execute(payment)

    assert attempt is not None
    assert returned_decision == decision
    assert returned_guardrail == guardrail
    assert returned_execution == execution

    assert attempt.action == "retry"
    assert attempt.status == "awaiting_payment"
    assert attempt.recovered is None
    assert attempt.provider_reference_id == "retry_1"
    assert attempt.error_message is None
    assert attempt.completed_at is None

    assert executor.calls == [
        (payment, "retry", True),
    ]


def test_blocked_recovery_is_not_executed() -> None:
    db = FakeSession()
    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
        recovery_probability=0.2,
    )

    guardrail = GuardrailResult(
        allowed=False,
        reason="Recovery probability is below the execution threshold.",
    )

    executor = FakeExecutor()

    service = RecoveryService(
        db,
        agent=FakeAgent(decision, guardrail),
        executor=executor,
    )

    (
        attempt,
        _,
        _,
        execution,
    ) = service.evaluate_and_execute(payment)

    assert attempt is not None
    assert attempt.status == "blocked"
    assert attempt.recovered is False
    assert attempt.error_message == guardrail.reason
    assert attempt.completed_at is not None

    assert execution.executed is False
    assert execution.status == "blocked"
    assert attempt.provider_reference_id is None
    assert executor.calls == []


def test_failed_execution_is_persisted_and_reraised() -> None:
    db = FakeSession()
    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
        recovery_probability=0.9,
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    executor = FakeExecutor(
        error=RuntimeError("Gateway unavailable"),
    )

    service = RecoveryService(
        db,
        agent=FakeAgent(decision, guardrail),
        executor=executor,
    )

    with pytest.raises(
        RuntimeError,
        match="Gateway unavailable",
    ):
        service.evaluate_and_execute(payment)

    assert len(db.attempts) == 1

    attempt = db.attempts[0]

    assert attempt.status == "failed"
    assert attempt.recovered is False
    assert "Gateway unavailable" in attempt.error_message
    assert attempt.provider_reference_id is None
    assert attempt.completed_at is not None

    assert executor.calls == [
        (payment, "retry", True),
    ]


def test_executor_returning_blocked_result_is_persisted() -> None:
    db = FakeSession()
    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
        recovery_probability=0.9,
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

    executor = FakeExecutor(
        result=execution,
    )

    service = RecoveryService(
        db,
        agent=FakeAgent(decision, guardrail),
        executor=executor,
    )

    (
        attempt,
        _,
        _,
        returned_execution,
    ) = service.evaluate_and_execute(payment)

    assert attempt is not None
    assert returned_execution == execution
    assert attempt.status == "failed"
    assert attempt.recovered is False
    assert attempt.error_message == execution.reason
    assert attempt.provider_reference_id is None

    assert executor.calls == [
        (payment, "retry", True),
    ]


def test_already_recovered_payment_is_not_retried() -> None:
    db = FakeSession()
    payment = make_payment("failed")

    existing = RecoveryAttempt(
        payment_id=payment.id,
        action="retry",
        attempt_number=1,
        status="completed",
        recovered=True,
    )

    db.attempts.append(existing)

    executor = FakeExecutor()

    service = RecoveryService(
        db,
        agent=make_agent(),
        executor=executor,
    )

    (
        attempt,
        decision,
        guardrail,
        execution,
    ) = service.evaluate_and_execute(payment)

    assert attempt is None
    assert decision.action == "no_action"
    assert guardrail.allowed is False
    assert execution.executed is False
    assert execution.status == "no_action"
    assert executor.calls == []


def test_maximum_recovery_attempts_stops_new_attempt() -> None:
    db = FakeSession()
    payment = make_payment("failed")

    for number in range(1, 4):
        db.attempts.append(
            RecoveryAttempt(
                payment_id=payment.id,
                action="retry",
                attempt_number=number,
                status="failed",
                recovered=False,
            )
        )

    service = RecoveryService(
        db,
        agent=make_agent(),
    )

    (
        attempt,
        decision,
        guardrail,
    ) = service.evaluate_and_record(payment)

    assert attempt is None
    assert decision.action == "no_action"
    assert guardrail.allowed is False
    assert "Maximum recovery limit" in decision.reason


def test_wait_and_retry_is_scheduled() -> None:
    db = FakeSession()
    payment = make_payment("failed")

    decision = RecoveryDecision(
        action="wait_and_retry",
        reason="Temporary failure detected.",
        recovery_probability=0.8,
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Delayed retry approved.",
    )

    service = RecoveryService(
        db,
        agent=FakeAgent(decision, guardrail),
    )

    (
        attempt,
        _,
        _,
        execution,
    ) = service.evaluate_and_execute(payment)

    assert attempt is not None
    assert attempt.status == "scheduled"
    assert attempt.scheduled_for is not None
    assert execution.executed is False
    assert execution.status == "scheduled"