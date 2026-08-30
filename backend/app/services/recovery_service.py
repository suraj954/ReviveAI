from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.services.recovery_executor import (
    RecoveryExecutionResult,
    RecoveryExecutor,
)


class RecoveryService:
    """
    Coordinates recovery decision-making, attempt persistence,
    and optional recovery execution.
    """

    MAX_RECOVERY_ATTEMPTS = 3
    WAIT_RETRY_DELAY_MINUTES = 15

    def __init__(
        self,
        db,
        agent,
        executor: Optional[RecoveryExecutor] = None,
    ) -> None:
        self.db = db
        self.agent = agent
        self.executor = executor

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _no_action_result(
        self,
        reason: str,
    ) -> tuple[RecoveryDecision, GuardrailResult]:
        decision = RecoveryDecision(
            action="no_action",
            reason=reason,
            recovery_probability=0.0,
        )

        guardrail = GuardrailResult(
            allowed=False,
            reason=reason,
        )

        return decision, guardrail

    def _execution_result(
        self,
        *,
        action: str,
        status: str,
        reason: str,
        executed: bool = False,
        reference_id: str | None = None,
    ) -> RecoveryExecutionResult:
        return RecoveryExecutionResult(
            executed=executed,
            action=action,
            status=status,
            reference_id=reference_id,
            reason=reason,
        )

    def _is_terminal_payment(self, payment: Payment) -> bool:
        return str(payment.status).lower() in {
            "captured",
            "paid",
            "success",
            "succeeded",
        }

    def _get_attempts(self, payment_id: int):
        """
        Fetch attempts for a payment.

        Works with both SQLAlchemy sessions and the lightweight FakeSession
        used by the test suite.
        """
        query = self.db.query(RecoveryAttempt).filter(
            RecoveryAttempt.payment_id == payment_id
        )

        # FakeQuery does not implement all(), so use its items directly.
        if hasattr(query, "items"):
            return [
                attempt
                for attempt in query.items
                if getattr(attempt, "payment_id", None) == payment_id
            ]

        return query.all()

    def _already_recovered(self, payment_id: int) -> bool:
        attempts = self._get_attempts(payment_id)

        return any(
            getattr(attempt, "recovered", None) is True
            for attempt in attempts
        )

    def _attempt_count(self, payment_id: int) -> int:
        return len(self._get_attempts(payment_id))

    def _next_attempt_number(self, payment_id: int) -> int:
        attempts = self._get_attempts(payment_id)

        if not attempts:
            return 1

        return max(
            getattr(attempt, "attempt_number", 0) or 0
            for attempt in attempts
        ) + 1

    def evaluate_and_record(
        self,
        payment: Payment,
    ) -> tuple[
        RecoveryAttempt | None,
        RecoveryDecision,
        GuardrailResult,
    ]:
        """
        Evaluate a payment for recovery and persist a recovery attempt
        when an action should be considered.
        """

        # Never recover already successful payments.
        if self._is_terminal_payment(payment):
            decision, guardrail = self._no_action_result(
                "Payment is already completed."
            )
            return None, decision, guardrail

        # Never retry a payment already successfully recovered.
        if self._already_recovered(payment.id):
            decision, guardrail = self._no_action_result(
                "Payment has already been recovered."
            )
            return None, decision, guardrail

        # Stop after the configured maximum number of attempts.
        if self._attempt_count(payment.id) >= self.MAX_RECOVERY_ATTEMPTS:
            decision, guardrail = self._no_action_result(
                "Maximum recovery limit reached."
            )
            return None, decision, guardrail

        # Ask the recovery agent for a decision.
        decision, guardrail = self.agent.evaluate_with_guardrails(
            payment
        )

        # Explicit no-action decisions do not create attempts.
        if decision.action == "no_action":
            return None, decision, guardrail

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action=decision.action,
            attempt_number=self._next_attempt_number(payment.id),
        )

        # Store optional decision metadata only if the model supports it.
        # This avoids passing invalid constructor kwargs to SQLAlchemy.
        if hasattr(attempt, "reason"):
            attempt.reason = decision.reason

        if hasattr(attempt, "recovery_probability"):
            attempt.recovery_probability = decision.recovery_probability

        if guardrail.allowed:
            attempt.status = "approved"
        else:
            attempt.status = "blocked"
            attempt.recovered = False
            attempt.error_message = guardrail.reason
            attempt.completed_at = self._now()

        self.db.add(attempt)
        self.db.flush()

        return attempt, decision, guardrail

    def evaluate_and_execute(
        self,
        payment: Payment,
    ) -> tuple[
        RecoveryAttempt | None,
        RecoveryDecision,
        GuardrailResult,
        RecoveryExecutionResult,
    ]:
        """
        Evaluate a payment and execute the approved recovery action.
        """

        attempt, decision, guardrail = self.evaluate_and_record(
            payment
        )

        # No recovery attempt was needed.
        if attempt is None:
            execution = self._execution_result(
                action="no_action",
                status="no_action",
                reason=decision.reason,
            )

            return (
                None,
                decision,
                guardrail,
                execution,
            )

        # Guardrails blocked execution.
        if not guardrail.allowed:
            execution = self._execution_result(
                action=decision.action,
                status="blocked",
                reason=guardrail.reason,
            )

            return (
                attempt,
                decision,
                guardrail,
                execution,
            )

        # Delayed retries are scheduled rather than immediately executed.
        if decision.action == "wait_and_retry":
            attempt.status = "scheduled"
            attempt.scheduled_for = (
                self._now()
                + timedelta(
                    minutes=self.WAIT_RETRY_DELAY_MINUTES
                )
            )

            execution = self._execution_result(
                action=decision.action,
                status="scheduled",
                reason=decision.reason,
            )

            self.db.flush()

            return (
                attempt,
                decision,
                guardrail,
                execution,
            )

        # An executor is required for immediate execution.
        if self.executor is None:
            raise RuntimeError(
                "RecoveryExecutor is required for recovery execution."
            )

        try:
            execution = self.executor.execute(
                payment,
                decision,
                guardrail,
            )

        except Exception as exc:
            attempt.status = "failed"
            attempt.recovered = False
            attempt.error_message = str(exc)
            attempt.provider_reference_id = None
            attempt.completed_at = self._now()

            self.db.flush()

            raise

        # Executor successfully initiated recovery.
        if execution.executed:
            attempt.status = execution.status
            attempt.recovered = None
            attempt.provider_reference_id = execution.reference_id
            attempt.error_message = None
            attempt.completed_at = None

        # Executor returned a non-executed result.
        else:
            attempt.status = "failed"
            attempt.recovered = False
            attempt.provider_reference_id = execution.reference_id
            attempt.error_message = execution.reason
            attempt.completed_at = self._now()

        self.db.flush()

        return (
            attempt,
            decision,
            guardrail,
            execution,
        )