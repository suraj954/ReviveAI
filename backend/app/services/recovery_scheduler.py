from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.enums import RecoveryAction, RecoveryStatus
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.razorpay.recovery_gateway import RazorpayRecoveryGateway
from app.services.recovery_executor import RecoveryExecutor
from app.services.recovery_service import RecoveryService


logger = logging.getLogger(__name__)


class RecoveryScheduler:
    """
    Database-backed scheduler for delayed recovery interventions.

    The scheduler periodically finds recovery attempts that are:

        - scheduled
        - due for execution

    It then claims the attempt, executes the provider action, and
    updates the recovery lifecycle.

    A fresh database session must be supplied for every scheduler
    polling cycle.
    """

    def __init__(
        self,
        db: Session,
        *,
        executor: RecoveryExecutor | None = None,
    ) -> None:
        self.db = db

        self.executor = executor or RecoveryExecutor(
            RazorpayRecoveryGateway()
        )

        self.service = RecoveryService(db)

    def process_due_attempts(
        self,
        *,
        limit: int = 50,
    ) -> int:
        """
        Process scheduled recovery attempts whose execution time
        has arrived.

        Returns:
            Number of attempts successfully claimed for processing.

        Each attempt is committed independently so one provider
        failure does not roll back unrelated scheduled attempts.
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
        Process one due recovery attempt.

        The attempt must be claimed before provider execution.
        """

        # Reload current state inside the active transaction.
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

        # Another workflow may have cancelled or completed it.
        if (
            current_attempt.status
            != RecoveryStatus.SCHEDULED.value
        ):
            return

        payment = (
            self.db.query(Payment)
            .filter(
                Payment.id == current_attempt.payment_id
            )
            .first()
        )

        if payment is None:
            raise RuntimeError(
                "Payment for recovery attempt was not found."
            )

        # ---------------------------------------------------------
        # Re-check stopping conditions immediately before execution.
        # Payment state may have changed while waiting.
        # ---------------------------------------------------------
        if payment.status in {"paid", "captured"}:
            current_attempt.status = (
                RecoveryStatus.CANCELLED.value
            )
            current_attempt.recovered = False
            current_attempt.error_message = (
                "Scheduled recovery cancelled because the "
                "original payment is already successful."
            )
            current_attempt.completed_at = datetime.now(UTC)
            self.db.flush()
            return

        # ---------------------------------------------------------
        # Claim attempt: scheduled -> executing
        # ---------------------------------------------------------
        self.service.claim_scheduled_attempt(
            current_attempt
        )

        # ---------------------------------------------------------
        # Execute the delayed recovery checkout.
        #
        # We intentionally execute a RETRY action here because
        # WAIT_AND_RETRY means "wait first, then retry".
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
                "Recovery action was previously approved and "
                "scheduled."
            ),
        )

        result = self.executor.execute(
            payment=payment,
            decision=execution_decision,
            guardrail_result=guardrail_result,
        )

        if result.executed:
            if not result.reference_id:
                raise RuntimeError(
                    "Provider execution succeeded without a "
                    "reference ID."
                )

            self.service.mark_awaiting_payment(
                current_attempt,
                provider_reference_id=result.reference_id,
            )

            return

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
        Persist a failure after the main processing transaction
        has been rolled back.

        This gives the scheduler a durable failure state instead
        of silently retrying a permanently broken attempt forever.
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

            # Do not overwrite a concurrent terminal transition.
            if (
                attempt.status
                != RecoveryStatus.SCHEDULED.value
                and attempt.status
                != RecoveryStatus.EXECUTING.value
            ):
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