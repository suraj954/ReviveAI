from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.enums import (
    RecoveryAction,
    RecoveryEventType,
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
from app.services.recovery_factory import (
    get_recovery_service,
)
from app.services.recovery_service import (
    RecoveryService,
)


logger = logging.getLogger(__name__)


class RecoveryScheduler:
    """
    Database-backed scheduler for controlled recovery workflows.

    Responsibilities:

    1. Execute delayed WAIT_AND_RETRY attempts.
    2. Re-evaluate failed recovery attempts after cooldown.
    3. Ensure each failed attempt is consumed only once for retry.
    4. Enforce the global maximum recovery attempt limit.
    """

    FAILED_RECOVERY_COOLDOWN_SECONDS = 30

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

        self.service = RecoveryService(
            db=db,
            agent=None,
            executor=self.executor,
        )

    # =========================================================
    # PUBLIC ENTRYPOINT
    # =========================================================

    def process_due_attempts(
        self,
        *,
        limit: int = 50,
    ) -> int:
        """
        Process scheduled recovery work.

        Workflows:

        1. Execute due delayed attempts.
        2. Re-evaluate eligible failed attempts.
        """

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        processed_count = 0

        processed_count += (
            self._process_scheduled_attempts(
                limit=limit
            )
        )

        remaining_limit = max(
            0,
            limit - processed_count,
        )

        if remaining_limit > 0:
            processed_count += (
                self._process_failed_attempts_for_retry(
                    limit=remaining_limit
                )
            )

        return processed_count

    # =========================================================
    # SCHEDULED ATTEMPTS
    # =========================================================

    def _process_scheduled_attempts(
        self,
        *,
        limit: int,
    ) -> int:
        """
        Execute delayed recovery attempts whose scheduled time
        has arrived.
        """

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

        if (
            current_attempt.status
            != RecoveryStatus.SCHEDULED.value
        ):
            return

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

        if payment.status in {
            "paid",
            "captured",
            "success",
            "succeeded",
        }:
            self.service.mark_cancelled(
                current_attempt,
                reason=(
                    "Scheduled recovery cancelled because "
                    "the original payment is already successful."
                ),
            )
            return

        # Claim scheduled attempt.
        self.service.claim_scheduled_attempt(
            current_attempt
        )

        # Waiting has elapsed.
        # Execute a real provider retry now.
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

        self.service.mark_execution_failed(
            current_attempt,
            reason=result.reason,
        )

    # =========================================================
    # FAILED ATTEMPT RE-EVALUATION
    # =========================================================

    def _process_failed_attempts_for_retry(
        self,
        *,
        limit: int,
    ) -> int:
        """
        Find failed attempts whose cooldown has elapsed.

        Each failed attempt is eligible for exactly one
        scheduler-driven re-evaluation.

        retry_evaluated_at prevents old failed attempts from being
        selected forever in every scheduler polling cycle.
        """

        cooldown_cutoff = (
            datetime.now(UTC)
            - timedelta(
                seconds=(
                    self.FAILED_RECOVERY_COOLDOWN_SECONDS
                )
            )
        )

        failed_attempts = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.status
                == RecoveryStatus.FAILED.value,
                RecoveryAttempt.completed_at.is_not(None),
                RecoveryAttempt.completed_at
                <= cooldown_cutoff,
                RecoveryAttempt.retry_evaluated_at.is_(None),
            )
            .order_by(
                RecoveryAttempt.completed_at.asc()
            )
            .limit(limit)
            .all()
        )

        processed_count = 0

        for attempt in failed_attempts:

            try:
                if self._reevaluate_failed_attempt(
                    attempt
                ):
                    processed_count += 1

                self.db.commit()

            except Exception:
                self.db.rollback()

                logger.exception(
                    "Failed to re-evaluate recovery attempt %s",
                    attempt.id,
                )

        return processed_count

    def _reevaluate_failed_attempt(
        self,
        attempt: RecoveryAttempt,
    ) -> bool:
        """
        Re-evaluate a payment after one recovery attempt failed.

        Returns True when the failed attempt was consumed for
        scheduler processing.
        """

        current_attempt = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.id == attempt.id
            )
            .first()
        )

        if current_attempt is None:
            return False

        if (
            current_attempt.status
            != RecoveryStatus.FAILED.value
        ):
            return False

        if (
            current_attempt.retry_evaluated_at
            is not None
        ):
            return False

        payment = (
            self.db.query(Payment)
            .filter(
                Payment.id
                == current_attempt.payment_id
            )
            .first()
        )

        if payment is None:

            logger.warning(
                "Payment %s for failed recovery attempt %s "
                "was not found.",
                current_attempt.payment_id,
                current_attempt.id,
            )

            # Consume this attempt so it cannot loop forever.
            current_attempt.retry_evaluated_at = (
                datetime.now(UTC)
            )

            return True

        # -----------------------------------------------------
        # ORIGINAL PAYMENT ALREADY SUCCEEDED
        # -----------------------------------------------------

        if payment.status in {
            "paid",
            "captured",
            "success",
            "succeeded",
        }:
            current_attempt.retry_evaluated_at = (
                datetime.now(UTC)
            )

            return True

        # -----------------------------------------------------
        # PREVENT DUPLICATE ACTIVE ATTEMPTS
        # -----------------------------------------------------

        active_attempt = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id
                == payment.id,
                RecoveryAttempt.status.in_(
                    [
                        RecoveryStatus.PENDING.value,
                        RecoveryStatus.APPROVED.value,
                        RecoveryStatus.SCHEDULED.value,
                        RecoveryStatus.EXECUTING.value,
                        RecoveryStatus.AWAITING_PAYMENT.value,
                    ]
                ),
            )
            .first()
        )

        if active_attempt:
            return False

        # -----------------------------------------------------
        # CONSUME FAILED ATTEMPT
        # -----------------------------------------------------

        # Mark before new evaluation so this specific failed
        # attempt cannot trigger repeated scheduler loops.
        current_attempt.retry_evaluated_at = (
            datetime.now(UTC)
        )

        self.service._record_event(
            current_attempt,
            event_type=(
                RecoveryEventType.RETRY_EVALUATED.value
            ),
            description=(
                "Failed recovery attempt entered bounded "
                "post-cooldown re-evaluation."
            ),
        )

        # -----------------------------------------------------
        # MAXIMUM ATTEMPT LIMIT
        # -----------------------------------------------------

        attempt_count = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id
                == payment.id
            )
            .count()
        )

        if (
            attempt_count
            >= RecoveryService.MAX_RECOVERY_ATTEMPTS
        ):
            self._mark_attempt_exhausted(
                current_attempt
            )

            logger.info(
                "Payment %s reached maximum recovery "
                "attempt limit (%s).",
                payment.id,
                RecoveryService.MAX_RECOVERY_ATTEMPTS,
            )

            return True

        # -----------------------------------------------------
        # FRESH AI + GUARDRAIL EVALUATION
        # -----------------------------------------------------

        recovery_service = get_recovery_service(
            self.db
        )

        (
            new_attempt,
            decision,
            guardrail,
            execution,
        ) = recovery_service.evaluate_and_execute(
            payment
        )

        logger.info(
            "Re-evaluated payment %s after failed recovery "
            "attempt %s: action=%s, allowed=%s, "
            "new_attempt=%s",
            payment.id,
            current_attempt.id,
            decision.action,
            guardrail.allowed,
            (
                new_attempt.attempt_number
                if new_attempt
                else None
            ),
        )

        return True

    # =========================================================
    # EXHAUSTION
    # =========================================================

    def _mark_attempt_exhausted(
        self,
        attempt: RecoveryAttempt,
    ) -> None:
        """
        Mark the final failed recovery attempt as exhausted.

        This represents a bounded recovery workflow that has reached
        its configured intervention limit.
        """

        if (
            attempt.status
            == RecoveryStatus.EXHAUSTED.value
        ):
            return

        previous_status = attempt.status

        attempt.status = (
            RecoveryStatus.EXHAUSTED.value
        )
        attempt.executed = True
        attempt.recovered = False
        attempt.error_message = (
            "Maximum recovery attempt limit reached."
        )
        attempt.completed_at = datetime.now(UTC)

        self.db.flush()

        self.service._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.EXHAUSTED.value,
            description=(
                "Recovery workflow exhausted its maximum "
                "allowed attempts."
            ),
        )

        self.service._record_event(
            attempt,
            event_type=RecoveryEventType.EXHAUSTED.value,
            description=(
                "Maximum recovery attempt limit reached."
            ),
        )

    # =========================================================
    # FAILURE FALLBACK
    # =========================================================

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

            if attempt.status in {
                RecoveryStatus.COMPLETED.value,
                RecoveryStatus.CANCELLED.value,
                RecoveryStatus.BLOCKED.value,
                RecoveryStatus.FAILED.value,
                RecoveryStatus.EXHAUSTED.value,
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