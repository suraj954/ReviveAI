from __future__ import annotations

from datetime import datetime

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

    Responsibilities are deliberately separated:

        RecoveryAgent
            -> decides the recovery action

        Guardrails
            -> determine whether execution is allowed

        RecoveryExecutor
            -> executes an approved recovery action

        RecoveryAttempt
            -> persists the recovery result
    """

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

        This method only records the recovery decision.
        It does not execute an external recovery operation.
        """

        decision = self.agent.evaluate(payment)

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action=decision.action,
            attempt_number=self._next_attempt_number(payment.id),
        )

        self.db.add(attempt)
        self.db.commit()
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

        The full Payment object is passed to RecoveryExecutor so that
        the provider gateway has access to the payment's status,
        amount, Razorpay order ID, and other required information.
        """

        # ---------------------------------------------------------
        # 1. Executor must be explicitly provided
        # ---------------------------------------------------------

        if self.executor is None:
            raise RuntimeError(
                "RecoveryExecutor is required for execution."
            )

        # ---------------------------------------------------------
        # 2. Ask the agent for a decision and guardrail result
        # ---------------------------------------------------------

        decision, guardrail_result = (
            self.agent.evaluate_with_guardrails(payment)
        )

        # ---------------------------------------------------------
        # 3. Persist the recovery attempt as pending
        # ---------------------------------------------------------

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action=decision.action,
            attempt_number=self._next_attempt_number(payment.id),
            status="pending",
        )

        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)

        # ---------------------------------------------------------
        # 4. Stop immediately if guardrails reject the action
        # ---------------------------------------------------------

        if not guardrail_result.allowed:
            attempt.status = "blocked"
            attempt.recovered = False
            attempt.error_message = guardrail_result.reason
            attempt.completed_at = datetime.utcnow()

            self.db.commit()
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
        # 5. Mark attempt as executing
        # ---------------------------------------------------------

        attempt.status = "executing"
        self.db.commit()

        # ---------------------------------------------------------
        # 6. Execute through RecoveryExecutor
        #
        # IMPORTANT:
        # Pass the complete Payment object, NOT payment.id.
        # ---------------------------------------------------------

        try:
            execution_result = self.executor.execute(
                payment=payment,
                decision=decision,
                guardrail_result=guardrail_result,
            )

            # -----------------------------------------------------
            # 7. Persist execution result
            # -----------------------------------------------------

            if execution_result.executed:
                attempt.status = "completed"
                attempt.recovered = True
                attempt.error_message = None
            else:
                attempt.status = execution_result.status
                attempt.recovered = False
                attempt.error_message = execution_result.reason

        except Exception as exc:
            # -----------------------------------------------------
            # 8. Persist unexpected gateway/executor failures
            # -----------------------------------------------------

            attempt.status = "failed"
            attempt.recovered = False
            attempt.error_message = str(exc)

            execution_result = RecoveryExecutionResult(
                executed=False,
                action=decision.action,
                status="failed",
                reference_id=None,
                reason=str(exc),
            )

        # ---------------------------------------------------------
        # 9. Mark completion time
        # ---------------------------------------------------------

        attempt.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(attempt)

        return (
            attempt,
            decision,
            guardrail_result,
            execution_result,
        )

    def _next_attempt_number(
        self,
        payment_id: int,
    ) -> int:
        """
        Return the next recovery attempt number for a payment.
        """

        latest_attempt = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment_id,
            )
            .order_by(
                RecoveryAttempt.attempt_number.desc()
            )
            .first()
        )

        if latest_attempt is None:
            return 1

        return latest_attempt.attempt_number + 1

