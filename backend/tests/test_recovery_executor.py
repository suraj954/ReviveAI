from datetime import datetime, timezone

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.payment import Payment
from app.services.recovery_executor import RecoveryExecutor


class FakeRecoveryGateway:
    def __init__(self) -> None:
        self.retry_calls: list[int] = []
        self.wait_and_retry_calls: list[int] = []

    def execute_retry(self, payment: Payment) -> str:
        self.retry_calls.append(payment.id)
        return f"retry_{payment.id}"

    def execute_wait_and_retry(self, payment: Payment) -> str:
        self.wait_and_retry_calls.append(payment.id)
        return f"scheduled_{payment.id}"


def make_payment(payment_id: int) -> Payment:
    payment = Payment(
        razorpay_order_id=f"order_{payment_id}",
        amount=50000,
        currency="INR",
        status="failed",
        receipt="test_receipt",
        created_at=datetime.now(timezone.utc),
    )

    payment.id = payment_id

    return payment


def test_approved_retry_is_executed() -> None:
    gateway = FakeRecoveryGateway()
    executor = RecoveryExecutor(gateway)

    payment = make_payment(101)

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    result = executor.execute(
        payment=payment,
        decision=decision,
        guardrail_result=guardrail,
    )

    assert result.executed is True
    assert result.action == "retry"
    assert result.status == "executed"
    assert result.reference_id == "retry_101"
    assert gateway.retry_calls == [101]


def test_approved_wait_and_retry_is_scheduled() -> None:
    gateway = FakeRecoveryGateway()
    executor = RecoveryExecutor(gateway)

    payment = make_payment(202)
    payment.status = "created"

    decision = RecoveryDecision(
        action="wait_and_retry",
        reason="Payment is still pending.",
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    result = executor.execute(
        payment=payment,
        decision=decision,
        guardrail_result=guardrail,
    )

    assert result.executed is True
    assert result.action == "wait_and_retry"
    assert result.status == "scheduled"
    assert result.reference_id == "scheduled_202"
    assert gateway.wait_and_retry_calls == [202]


def test_blocked_decision_is_never_sent_to_gateway() -> None:
    gateway = FakeRecoveryGateway()
    executor = RecoveryExecutor(gateway)

    payment = make_payment(303)

    decision = RecoveryDecision(
        action="retry",
        reason="Payment failed.",
    )

    guardrail = GuardrailResult(
        allowed=False,
        reason="Recovery probability is below the execution threshold.",
    )

    result = executor.execute(
        payment=payment,
        decision=decision,
        guardrail_result=guardrail,
    )

    assert result.executed is False
    assert result.status == "blocked"
    assert result.reference_id is None
    assert gateway.retry_calls == []


def test_no_action_cannot_be_executed() -> None:
    gateway = FakeRecoveryGateway()
    executor = RecoveryExecutor(gateway)

    payment = make_payment(404)
    payment.status = "captured"

    decision = RecoveryDecision(
        action="no_action",
        reason="Payment has already been captured.",
    )

    guardrail = GuardrailResult(
        allowed=False,
        reason="No recovery action was recommended.",
    )

    result = executor.execute(
        payment=payment,
        decision=decision,
        guardrail_result=guardrail,
    )

    assert result.executed is False
    assert result.status == "blocked"
    assert gateway.retry_calls == []
    assert gateway.wait_and_retry_calls == []


def test_unsupported_action_is_not_executed() -> None:
    gateway = FakeRecoveryGateway()
    executor = RecoveryExecutor(gateway)

    payment = make_payment(505)

    decision = RecoveryDecision(
        action="cancel_payment",
        reason="Unsupported action.",
    )

    guardrail = GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )

    result = executor.execute(
        payment=payment,
        decision=decision,
        guardrail_result=guardrail,
    )

    assert result.executed is False
    assert result.status == "blocked"
    assert result.reference_id is None
    assert gateway.retry_calls == []
    assert gateway.wait_and_retry_calls == []

