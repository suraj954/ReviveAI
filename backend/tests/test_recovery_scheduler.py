from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.models.enums import (
    RecoveryAction,
    RecoveryStatus,
)
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.services.recovery_executor import (
    RecoveryExecutionResult,
)
from app.services.recovery_scheduler import (
    RecoveryScheduler,
)


class FakeQuery:
    """
    Lightweight in-memory SQLAlchemy-like query implementation.

    Supports the subset of query operations used by
    RecoveryScheduler unit tests.
    """

    def __init__(self, items):
        self.items = list(items)

    def filter(self, *conditions):
        """
        Apply SQLAlchemy binary filter expressions to in-memory items.

        Supports:
        - equality
        - less-than-or-equal comparisons
        - is_not(None)
        """

        filtered_items = self.items

        for condition in conditions:
            if condition is None:
                continue

            try:
                left = condition.left
                right = condition.right
                operator_name = condition.operator.__name__

                attribute_name = left.name

                if hasattr(right, "value"):
                    comparison_value = right.value
                else:
                    comparison_value = right

                if operator_name == "eq":
                    filtered_items = [
                        item
                        for item in filtered_items
                        if getattr(
                            item,
                            attribute_name,
                            None,
                        )
                        == comparison_value
                    ]

                elif operator_name == "le":
                    filtered_items = [
                        item
                        for item in filtered_items
                        if getattr(
                            item,
                            attribute_name,
                            None,
                        )
                        is not None
                        and getattr(
                            item,
                            attribute_name,
                        )
                        <= comparison_value
                    ]

                elif operator_name == "is_not":
                    filtered_items = [
                        item
                        for item in filtered_items
                        if getattr(
                            item,
                            attribute_name,
                            None,
                        )
                        is not None
                    ]

            except AttributeError:
                # If a condition cannot be interpreted by the fake,
                # leave the current result set unchanged.
                continue

        self.items = filtered_items

        return self

    def order_by(self, *args):
        """
        Ordering is unnecessary for most tests, but scheduled
        attempts should be processed chronologically.
        """

        try:
            self.items.sort(
                key=lambda item: getattr(
                    item,
                    "scheduled_for",
                    datetime.max.replace(tzinfo=UTC),
                )
            )
        except (TypeError, AttributeError):
            pass

        return self

    def limit(self, value):
        self.items = self.items[:value]
        return self

    def all(self):
        return list(self.items)

    def first(self):
        if not self.items:
            return None

        return self.items[0]


class FakeSession:
    """
    Lightweight database session for scheduler unit tests.

    Implements the minimum Session interface required by:
    - RecoveryScheduler
    - RecoveryService
    - RecoveryAuditService
    """

    def __init__(
        self,
        attempts=None,
        payments=None,
    ) -> None:
        self.attempts = attempts or []
        self.payments = payments or []
        self.added_objects = []

        self.commit = MagicMock()
        self.rollback = MagicMock()
        self.flush = MagicMock()

    def add(self, obj):
        """
        Store objects added by RecoveryAuditService.
        """
        self.added_objects.append(obj)

    def query(self, model):
        if model is RecoveryAttempt:
            return FakeQuery(self.attempts)

        if model is Payment:
            return FakeQuery(self.payments)

        return FakeQuery([])


class FakeExecutor:
    """
    Configurable fake recovery executor.
    """

    def __init__(
        self,
        result=None,
        error=None,
    ) -> None:
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
            {
                "payment": payment,
                "decision": decision,
                "guardrail_result": guardrail_result,
            }
        )

        if self.error is not None:
            raise self.error

        return self.result


def make_payment(
    *,
    payment_id: int = 1,
    status: str = "failed",
):
    """
    Create a lightweight mock Payment.
    """

    payment = MagicMock(spec=Payment)

    payment.id = payment_id
    payment.status = status
    payment.amount = 10000
    payment.currency = "INR"

    return payment


def make_attempt(
    *,
    attempt_id: int = 1,
    payment_id: int = 1,
    status: str = RecoveryStatus.SCHEDULED.value,
):
    """
    Create a lightweight mock RecoveryAttempt.
    """

    attempt = MagicMock(spec=RecoveryAttempt)

    attempt.id = attempt_id
    attempt.payment_id = payment_id
    attempt.status = status

    attempt.scheduled_for = (
        datetime.now(UTC)
        - timedelta(minutes=1)
    )

    attempt.recovery_probability = 0.8
    attempt.executed = False
    attempt.recovered = None
    attempt.provider_reference_id = None
    attempt.error_message = None
    attempt.completed_at = None
    attempt.executed_at = None
    attempt.updated_at = None

    return attempt


def successful_execution(
    reference_id: str = "order_recovery_123",
):
    """
    Create a successful recovery execution result.
    """

    return RecoveryExecutionResult(
        executed=True,
        action=RecoveryAction.RETRY.value,
        status="executed",
        reference_id=reference_id,
        reason="Recovery checkout created.",
    )


def failed_execution():
    """
    Create a failed recovery execution result.
    """

    return RecoveryExecutionResult(
        executed=False,
        action=RecoveryAction.RETRY.value,
        status="failed",
        reference_id=None,
        reason="Provider rejected recovery execution.",
    )


# ============================================================
# VALIDATION
# ============================================================


def test_process_due_attempts_rejects_invalid_limit():
    db = FakeSession()

    scheduler = RecoveryScheduler(
        db,
        executor=FakeExecutor(),
    )

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        scheduler.process_due_attempts(limit=0)


# ============================================================
# NO DUE ATTEMPTS
# ============================================================


def test_process_due_attempts_returns_zero_when_empty():
    db = FakeSession()

    scheduler = RecoveryScheduler(
        db,
        executor=FakeExecutor(),
    )

    processed = scheduler.process_due_attempts()

    assert processed == 0

    db.commit.assert_not_called()


# ============================================================
# SUCCESSFUL ORIGINAL PAYMENT
# ============================================================


def test_successful_original_payment_cancels_recovery():
    payment = make_payment(
        status="paid",
    )

    attempt = make_attempt()

    db = FakeSession(
        attempts=[attempt],
        payments=[payment],
    )

    executor = FakeExecutor(
        result=successful_execution(),
    )

    scheduler = RecoveryScheduler(
        db,
        executor=executor,
    )

    processed = scheduler.process_due_attempts()

    assert processed == 1
    assert executor.calls == []

    assert (
        attempt.status
        == RecoveryStatus.CANCELLED.value
    )

    assert attempt.recovered is False

    db.commit.assert_called_once()


# ============================================================
# SUCCESSFUL EXECUTION
# ============================================================


def test_due_attempt_executes_and_awaits_payment():
    payment = make_payment()

    attempt = make_attempt()

    executor = FakeExecutor(
        result=successful_execution(),
    )

    db = FakeSession(
        attempts=[attempt],
        payments=[payment],
    )

    scheduler = RecoveryScheduler(
        db,
        executor=executor,
    )

    processed = scheduler.process_due_attempts()

    assert processed == 1

    assert len(executor.calls) == 1

    assert (
        attempt.status
        == RecoveryStatus.AWAITING_PAYMENT.value
    )

    assert attempt.executed is True

    assert (
        attempt.provider_reference_id
        == "order_recovery_123"
    )

    assert attempt.recovered is None

    db.commit.assert_called_once()


def test_scheduled_retry_uses_retry_action():
    payment = make_payment()

    attempt = make_attempt()

    executor = FakeExecutor(
        result=successful_execution(),
    )

    db = FakeSession(
        attempts=[attempt],
        payments=[payment],
    )

    scheduler = RecoveryScheduler(
        db,
        executor=executor,
    )

    scheduler.process_due_attempts()

    assert len(executor.calls) == 1

    decision = executor.calls[0]["decision"]

    assert (
        decision.action
        == RecoveryAction.RETRY.value
    )


# ============================================================
# FAILED EXECUTION
# ============================================================


def test_failed_execution_marks_attempt_failed():
    payment = make_payment()

    attempt = make_attempt()

    executor = FakeExecutor(
        result=failed_execution(),
    )

    db = FakeSession(
        attempts=[attempt],
        payments=[payment],
    )

    scheduler = RecoveryScheduler(
        db,
        executor=executor,
    )

    processed = scheduler.process_due_attempts()

    assert processed == 1

    assert (
        attempt.status
        == RecoveryStatus.FAILED.value
    )

    assert attempt.executed is False
    assert attempt.recovered is False

    assert (
        attempt.error_message
        == "Provider rejected recovery execution."
    )


# ============================================================
# PROVIDER REFERENCE VALIDATION
# ============================================================


def test_successful_execution_without_reference_is_failed():
    payment = make_payment()

    attempt = make_attempt()

    invalid_result = RecoveryExecutionResult(
        executed=True,
        action=RecoveryAction.RETRY.value,
        status="executed",
        reference_id=None,
        reason="Execution reported success.",
    )

    executor = FakeExecutor(
        result=invalid_result,
    )

    db = FakeSession(
        attempts=[attempt],
        payments=[payment],
    )

    scheduler = RecoveryScheduler(
        db,
        executor=executor,
    )

    processed = scheduler.process_due_attempts()

    assert processed == 0

    assert (
        attempt.status
        == RecoveryStatus.FAILED.value
    )

    assert db.rollback.called


# ============================================================
# ERROR ISOLATION
# ============================================================


def test_exception_does_not_stop_other_attempts():
    payment_one = make_payment(
        payment_id=1,
    )

    payment_two = make_payment(
        payment_id=2,
    )

    attempt_one = make_attempt(
        attempt_id=1,
        payment_id=1,
    )

    attempt_two = make_attempt(
        attempt_id=2,
        payment_id=2,
    )

    class MixedExecutor:
        def __init__(self):
            self.calls = 0

        def execute(
            self,
            payment,
            decision,
            guardrail_result,
        ):
            self.calls += 1

            if self.calls == 1:
                raise RuntimeError(
                    "Provider temporarily unavailable."
                )

            return successful_execution(
                reference_id=(
                    "order_recovery_success"
                )
            )

    executor = MixedExecutor()

    db = FakeSession(
        attempts=[
            attempt_one,
            attempt_two,
        ],
        payments=[
            payment_one,
            payment_two,
        ],
    )

    scheduler = RecoveryScheduler(
        db,
        executor=executor,
    )

    processed = scheduler.process_due_attempts()

    assert processed == 1

    assert (
        attempt_one.status
        == RecoveryStatus.FAILED.value
    )

    assert (
        attempt_two.status
        == RecoveryStatus.AWAITING_PAYMENT.value
    )

    assert executor.calls == 2


# ============================================================
# PROCESSING LIMIT
# ============================================================


def test_scheduler_respects_processing_limit():
    payments = [
        make_payment(payment_id=1),
        make_payment(payment_id=2),
        make_payment(payment_id=3),
    ]

    attempts = [
        make_attempt(
            attempt_id=1,
            payment_id=1,
        ),
        make_attempt(
            attempt_id=2,
            payment_id=2,
        ),
        make_attempt(
            attempt_id=3,
            payment_id=3,
        ),
    ]

    executor = FakeExecutor(
        result=successful_execution(),
    )

    db = FakeSession(
        attempts=attempts,
        payments=payments,
    )

    scheduler = RecoveryScheduler(
        db,
        executor=executor,
    )

    processed = scheduler.process_due_attempts(
        limit=2,
    )

    assert processed == 2

    assert len(executor.calls) == 2

    assert (
        attempts[0].status
        == RecoveryStatus.AWAITING_PAYMENT.value
    )

    assert (
        attempts[1].status
        == RecoveryStatus.AWAITING_PAYMENT.value
    )

    assert (
        attempts[2].status
        == RecoveryStatus.SCHEDULED.value
    )