from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.agents.recovery_agent import RecoveryAgent
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
    Coordinates recovery decisions, safety checks, execution,
    and persistence of recovery attempts.

    Transaction ownership belongs to the caller. This service uses
    flush() to synchronize pending changes without committing the
    surrounding database transaction.

    Recovery rules:
    - A payment can have at most MAX_RECOVERY_ATTEMPTS recovery attempts.
    - Once a payment is successfully recovered, no further recovery
      action is allowed.
    - Guardrails can block an otherwise valid recovery action.
    """

    MAX_RECOVERY_ATTEMPTS = 3

    def __init__(
        self,
        db: Session,
        *,
        agent: RecoveryAgent | None = None,
        executor: RecoveryExecutor | None = None,
    ) -> None:
        self.db = db
        self.agent = agent or RecoveryAgent()
        self.executor = executor

    def evaluate_and_record(
        self,
        payment: Payment,
    ) -> RecoveryAttempt:
        """
        Evaluate a payment and persist the resulting recovery attempt.

        This method records the recovery decision without executing
        an external recovery operation.

        The caller is responsible for committing or rolling back
        the database transaction.
        """

        decision = self.agent.evaluate(payment)

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action=decision.action,
            attempt_number=self._next_attempt_number(
                payment.id
            ),
        )

        self.db.add(attempt)
        self.db.flush()
        self.db.refresh(attempt)

        return attempt

    def evaluate_and_execute(
        self,
        payment: Payment,
    ) -> tuple[
        RecoveryAttempt,
        RecoveryDecision,
        GuardrailResult,
        RecoveryExecutionResult,
    ]:
        """
        Evaluate, guard, execute, and persist a recovery attempt.

        Recovery execution stops when:
        - the payment has already been successfully recovered, or
        - the maximum recovery attempt limit has been reached.

        The caller owns the transaction and is responsible for the
        final commit or rollback.
        """

        if self.executor is None:
            raise RuntimeError(
                "RecoveryExecutor is required for execution."
            )

        # ---------------------------------------------------------
        # 1. Stop if payment was already successfully recovered
        # ---------------------------------------------------------

        successful_attempt = self._successful_recovery_attempt(
            payment.id
        )

        if successful_attempt is not None:
            return self._create_already_recovered_result(
                payment=payment,
                successful_attempt=successful_attempt,
            )

        # ---------------------------------------------------------
        # 2. Check recovery attempt limit
        # ---------------------------------------------------------

        existing_attempts = self._attempt_count(
            payment.id
        )

        if existing_attempts >= self.MAX_RECOVERY_ATTEMPTS:
            return self._create_max_attempts_blocked_result(
                payment=payment,
            )

        # ---------------------------------------------------------
        # 3. Ask agent for decision and guardrail result
        # ---------------------------------------------------------

        (
            decision,
            guardrail_result,
        ) = self.agent.evaluate_with_guardrails(
            payment
        )

        # ---------------------------------------------------------
        # 4. Persist recovery attempt as pending
        # ---------------------------------------------------------

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action=decision.action,
            attempt_number=self._next_attempt_number(
                payment.id
            ),
            status="pending",
        )

        self.db.add(attempt)
        self.db.flush()
        self.db.refresh(attempt)

        # ---------------------------------------------------------
        # 5. Stop if guardrails reject the action
        # ---------------------------------------------------------

        if not guardrail_result.allowed:
            attempt.status = "blocked"
            attempt.recovered = False
            attempt.error_message = guardrail_result.reason
            attempt.completed_at = datetime.now(UTC)

            self.db.flush()
            self.db.refresh(attempt)

            execution_result = RecoveryExecutionResult(
                executed=False,
                action=decision.action,
                status="blocked",
                reference_id=None,
                reason=guardrail_result.reason,
            )

            return (
                attempt,
                decision,
                guardrail_result,
                execution_result,
            )

        # ---------------------------------------------------------
        # 6. Mark attempt as executing
        # ---------------------------------------------------------

        attempt.status = "executing"
        self.db.flush()

        # ---------------------------------------------------------
        # 7. Execute approved recovery action
        # ---------------------------------------------------------

        try:
            execution_result = self.executor.execute(
                payment=payment,
                decision=decision,
                guardrail_result=guardrail_result,
            )

            if execution_result.executed:
                attempt.provider_reference_id = (
                    execution_result.reference_id
                )
                attempt.error_message = None

                # Creating a recovery order does NOT mean the
                # original payment has been recovered.
                if decision.action == "retry":
                    attempt.status = "awaiting_payment"
                    attempt.recovered = None
                    attempt.completed_at = None

                elif decision.action == "wait_and_retry":
                    attempt.status = "scheduled"
                    attempt.recovered = None
                    attempt.completed_at = None

                else:
                    attempt.status = (
                        execution_result.status
                    )
                    attempt.recovered = False

            else:
                attempt.status = execution_result.status
                attempt.recovered = False

                attempt.provider_reference_id = (
                    execution_result.reference_id
                )

                attempt.error_message = (
                    execution_result.reason
                )

        except Exception as exc:
            attempt.status = "failed"
            attempt.recovered = False
            attempt.provider_reference_id = None
            attempt.error_message = str(exc)

            execution_result = RecoveryExecutionResult(
                executed=False,
                action=decision.action,
                status="failed",
                reference_id=None,
                reason=str(exc),
            )

        # ---------------------------------------------------------
        # 8. Mark completion only for terminal states
        # ---------------------------------------------------------

        terminal_statuses = {
            "blocked",
            "failed",
            "completed",
        }

        if attempt.status in terminal_statuses:
            attempt.completed_at = datetime.now(UTC)

        self.db.flush()
        self.db.refresh(attempt)

        return (
            attempt,
            decision,
            guardrail_result,
            execution_result,
        )

    def _create_already_recovered_result(
        self,
        payment: Payment,
        successful_attempt: RecoveryAttempt,
    ) -> tuple[
        RecoveryAttempt,
        RecoveryDecision,
        GuardrailResult,
        RecoveryExecutionResult,
    ]:
        """
        Return a blocked result when this payment has already been
        successfully recovered.

        No new RecoveryAttempt is created because recovery has
        already succeeded and creating additional attempts would
        incorrectly inflate recovery metrics.
        """

        reason = (
            "Payment has already been successfully recovered. "
            "No further recovery action will be executed."
        )

        decision = RecoveryDecision(
            action="no_action",
            reason=reason,
        )

        guardrail_result = GuardrailResult(
            allowed=False,
            reason=reason,
        )

        execution_result = RecoveryExecutionResult(
            executed=False,
            action="no_action",
            status="blocked",
            reference_id=(
                successful_attempt.provider_reference_id
            ),
            reason=reason,
        )

        return (
            successful_attempt,
            decision,
            guardrail_result,
            execution_result,
        )

    def _create_max_attempts_blocked_result(
        self,
        payment: Payment,
    ) -> tuple[
        RecoveryAttempt,
        RecoveryDecision,
        GuardrailResult,
        RecoveryExecutionResult,
    ]:
        """
        Return a blocked result when the maximum number of recovery
        attempts has already been reached.

        No new attempt is created. Otherwise repeated webhook
        deliveries could create attempt #4, #5, #6, etc. despite
        the configured maximum being 3.
        """

        reason = (
            f"Maximum recovery attempts "
            f"({self.MAX_RECOVERY_ATTEMPTS}) reached."
        )

        latest_attempt = self._latest_attempt(
            payment.id
        )

        if latest_attempt is None:
            raise RuntimeError(
                "Unable to find latest recovery attempt."
            )

        decision = RecoveryDecision(
            action="no_action",
            reason=reason,
        )

        guardrail_result = GuardrailResult(
            allowed=False,
            reason=reason,
        )

        execution_result = RecoveryExecutionResult(
            executed=False,
            action="no_action",
            status="blocked",
            reference_id=None,
            reason=reason,
        )

        return (
            latest_attempt,
            decision,
            guardrail_result,
            execution_result,
        )

    def _successful_recovery_attempt(
        self,
        payment_id: int,
    ) -> RecoveryAttempt | None:
        """
        Return a successful recovery attempt if this payment has
        already been recovered.
        """

        return (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment_id,
                RecoveryAttempt.recovered.is_(True),
            )
            .order_by(
                RecoveryAttempt.completed_at.desc()
            )
            .first()
        )

    def _attempt_count(
        self,
        payment_id: int,
    ) -> int:
        """
        Return the total number of recovery attempts for a payment.
        """

        return (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment_id,
            )
            .count()
        )

    def _latest_attempt(
        self,
        payment_id: int,
    ) -> RecoveryAttempt | None:
        """
        Return the latest recovery attempt for a payment.
        """

        return (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment_id,
            )
            .order_by(
                RecoveryAttempt.attempt_number.desc()
            )
            .first()
        )

    def _next_attempt_number(
        self,
        payment_id: int,
    ) -> int:
        """
        Return the next recovery attempt number for a payment.
        """

        latest_attempt = self._latest_attempt(
            payment_id
        )

        if latest_attempt is None:
            return 1

        return latest_attempt.attempt_number + 1
    