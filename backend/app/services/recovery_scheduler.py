from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.enums import (
    RecoveryAction,
    RecoveryStatus,
)
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.razorpay.recovery_gateway import (
    RazorpayRecoveryGateway,
)
from app.services.recovery_executor import (
    RecoveryExecutor,
)
from app.services.recovery_service import (
    RecoveryService,
)


logger = logging.getLogger(__name__)


class RecoveryScheduler:
    """
    Database-backed scheduler for delayed recovery attempts.

    Lifecycle:

        scheduled
            ->
        executing
            ->
        awaiting_payment
            ->
        completed / failed

    A fresh database session should be supplied for every polling
    cycle.
    """

    def __init__(
        self,
        db: Session,
        *,
        executor: RecoveryExecutor | None = None,
    ) -> None:
        self.db = db

        self.executor = (
            executor
            or RecoveryExecutor(
                RazorpayRecoveryGateway()
            )
        )

        # Scheduler does not make new AI decisions.
        # It only performs lifecycle transitions.
        self.service = RecoveryService(
            db=db,
            agent=None,
            executor=self.executor,
        )

    def process_due_attempts(
        self,
        *,
        limit: int = 50,
    ) -> int:
        """
        Process scheduled attempts whose execution time has arrived.

        Returns the number of attempts successfully claimed.

        Each attempt is committed independently so one failure does
        not roll back unrelated scheduled attempts.
        """

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        now = datetime.now(UTC)

        due_attempts = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.status
                == RecoveryStatus.SCHEDULED.value,
                RecoveryAttempt.scheduled_for.is_not(None),
                RecoveryAttempt.scheduled_for <= now,
            )
            .order_by(
                RecoveryAttempt.scheduled_for.asc()
            )
            .limit(limit)
            .all()
        )

        processed_count = 0

        for attempt in due_attempts:
            try:
                self._process_attempt(attempt)

                self.db.commit()

                processed_count += 1

            except Exception:
                self.db.rollback()

                logger.exception(
                    "Failed to process scheduled recovery "
                    "attempt %s",
                    attempt.id,
                )

                self._mark_attempt_failed_after_rollback(
                    attempt_id=attempt.id,
                    reason=(
                        "Scheduled recovery execution failed "
                        "due to an internal processing error."
                    ),
                )

        return processed_count

    def _process_attempt(
        self,
        attempt: RecoveryAttempt,
    ) -> None:
        """
        Process one scheduled recovery attempt.
        """

        # ---------------------------------------------------------
        # Reload current state
        # ---------------------------------------------------------

        current_attempt = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.id == attempt.id
            )
            .first()
        )

        if current_attempt is None:
            raise RuntimeError(
                "Scheduled recovery attempt no longer exists."
            )

        # Another workflow may have already cancelled/completed it.
        if (
            current_attempt.status
            != RecoveryStatus.SCHEDULED.value
        ):
            return

        # ---------------------------------------------------------
        # Load original payment
        # ---------------------------------------------------------

        payment = (
            self.db.query(Payment)
            .filter(
                Payment.id
                == current_attempt.payment_id
            )
            .first()
        )

        if payment is None:
            raise RuntimeError(
                "Payment for recovery attempt was not found."
            )

        # ---------------------------------------------------------
        # Re-check payment state
        # ---------------------------------------------------------

        if payment.status in {
            "paid",
            "captured",
            "success",
            "succeeded",
        }:
            self.service.mark_cancelled(
                current_attempt,
                reason=(
                    "Scheduled recovery cancelled because the "
                    "original payment is already successful."
                ),
            )

            return

        # ---------------------------------------------------------
        # Claim attempt
        # ---------------------------------------------------------

        self.service.claim_scheduled_attempt(
            current_attempt
        )

        # ---------------------------------------------------------
        # Execute delayed retry
        #
        # WAIT_AND_RETRY means:
        #
        # failed -> scheduled -> wait -> retry
        # ---------------------------------------------------------

        execution_decision = RecoveryDecision(
            action=RecoveryAction.RETRY.value,
            reason=(
                "Scheduled delay elapsed; executing approved "
                "recovery retry."
            ),
            recovery_probability=(
                current_attempt.recovery_probability
            ),
        )

        guardrail_result = GuardrailResult(
            allowed=True,
            reason=(
                "Recovery action was previously approved "
                "before scheduling."
            ),
        )

        result = self.executor.execute(
            payment=payment,
            decision=execution_decision,
            guardrail_result=guardrail_result,
        )

        # ---------------------------------------------------------
        # Provider checkout created
        # ---------------------------------------------------------

        if result.executed:
            if not result.reference_id:
                raise RuntimeError(
                    "Provider execution succeeded without a "
                    "reference ID."
                )

            self.service.mark_awaiting_payment(
                current_attempt,
                provider_reference_id=(
                    result.reference_id
                ),
            )

            return

        # ---------------------------------------------------------
        # Execution failure
        # ---------------------------------------------------------

        self.service.mark_execution_failed(
            current_attempt,
            reason=result.reason,
        )

    def _mark_attempt_failed_after_rollback(
        self,
        *,
        attempt_id: int,
        reason: str,
    ) -> None:
        """
        Persist a durable failure state after the main processing
        transaction has been rolled back.
        """

        try:
            attempt = (
                self.db.query(RecoveryAttempt)
                .filter(
                    RecoveryAttempt.id == attempt_id
                )
                .first()
            )

            if attempt is None:
                return

            # Do not overwrite terminal states.
            if attempt.status in {
                RecoveryStatus.COMPLETED.value,
                RecoveryStatus.CANCELLED.value,
                RecoveryStatus.BLOCKED.value,
                RecoveryStatus.FAILED.value,
            }:
                return

            self.service.mark_execution_failed(
                attempt,
                reason=reason,
            )

            self.db.commit()

        except Exception:
            self.db.rollback()

            logger.exception(
                "Unable to persist failure state for "
                "recovery attempt %s",
                attempt_id,
            )