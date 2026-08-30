from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.enums import (
    RecoveryAction,
    RecoveryEventType,
    RecoveryStatus,
)
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.services.recovery_audit_service import RecoveryAuditService
from app.services.recovery_executor import (
    RecoveryExecutionResult,
    RecoveryExecutor,
)


class RecoveryService:
    """
    Coordinates the complete recovery lifecycle.

    Responsibilities:

    1. Prevent invalid recovery attempts.
    2. Ask the AI recovery agent for a decision.
    3. Apply guardrail results.
    4. Persist recovery attempts.
    5. Execute immediate recovery actions.
    6. Schedule delayed recovery actions.
    7. Record immutable audit events.
    8. Provide lifecycle transition helpers for the scheduler.

    This service does NOT declare revenue recovered.

    Recovery is successful only when a verified provider webhook
    confirms payment success.
    """

    MAX_RECOVERY_ATTEMPTS = 3
    WAIT_RETRY_DELAY_MINUTES = 15

    def __init__(
        self,
        db,
        agent=None,
        executor: Optional[RecoveryExecutor] = None,
    ) -> None:
        self.db = db
        self.agent = agent
        self.executor = executor
        self.audit = RecoveryAuditService(db)

    # ============================================================
    # TIME
    # ============================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # ============================================================
    # AUDIT HELPERS
    # ============================================================

    def _record_event(
        self,
        attempt: RecoveryAttempt,
        *,
        event_type: str,
        description: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Record an audit event when the attempt has a persisted ID.

        The ID check keeps lightweight unit-test FakeSession objects
        compatible while production SQLAlchemy sessions persist the
        complete audit trail.
        """

        if getattr(attempt, "id", None) is None:
            return

        self.audit.record(
            attempt,
            event_type=event_type,
            description=description,
            metadata=metadata,
        )

    def _record_transition(
        self,
        attempt: RecoveryAttempt,
        *,
        from_status: str | None,
        to_status: str,
        description: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Record a standardized lifecycle transition audit event.
        """

        if getattr(attempt, "id", None) is None:
            return

        self.audit.record_transition(
            attempt,
            from_status=from_status,
            to_status=to_status,
            description=description,
            metadata=metadata,
        )

    # ============================================================
    # RESULT HELPERS
    # ============================================================

    def _no_action_result(
        self,
        reason: str,
    ) -> tuple[
        RecoveryDecision,
        GuardrailResult,
    ]:
        decision = RecoveryDecision(
            action=RecoveryAction.NO_ACTION.value,
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

    # ============================================================
    # PAYMENT STATE
    # ============================================================

    def _is_terminal_payment(
        self,
        payment: Payment,
    ) -> bool:
        return str(payment.status).lower() in {
            "captured",
            "paid",
            "success",
            "succeeded",
        }

    # ============================================================
    # ATTEMPT QUERIES
    # ============================================================

    def _get_attempts(
        self,
        payment_id: int,
    ) -> list[RecoveryAttempt]:
        """
        Fetch recovery attempts for a payment.

        Supports both SQLAlchemy and lightweight FakeSession objects
        used by the test suite.
        """

        query = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment_id
            )
        )

        if hasattr(query, "items"):
            return [
                attempt
                for attempt in query.items
                if (
                    getattr(
                        attempt,
                        "payment_id",
                        None,
                    )
                    == payment_id
                )
            ]

        return query.all()

    def _already_recovered(
        self,
        payment_id: int,
    ) -> bool:
        attempts = self._get_attempts(
            payment_id
        )

        return any(
            getattr(
                attempt,
                "recovered",
                None,
            )
            is True
            for attempt in attempts
        )

    def _attempt_count(
        self,
        payment_id: int,
    ) -> int:
        return len(
            self._get_attempts(payment_id)
        )

    def _next_attempt_number(
        self,
        payment_id: int,
    ) -> int:
        attempts = self._get_attempts(
            payment_id
        )

        if not attempts:
            return 1

        return (
            max(
                (
                    getattr(
                        attempt,
                        "attempt_number",
                        0,
                    )
                    or 0
                )
                for attempt in attempts
            )
            + 1
        )

    # ============================================================
    # LIFECYCLE TRANSITIONS
    # ============================================================

    def claim_scheduled_attempt(
        self,
        attempt: RecoveryAttempt,
    ) -> None:
        """
        Atomically transition:

            scheduled -> executing
        """

        if (
            attempt.status
            != RecoveryStatus.SCHEDULED.value
        ):
            raise RuntimeError(
                "Only scheduled recovery attempts can be claimed."
            )

        previous_status = attempt.status

        attempt.status = (
            RecoveryStatus.EXECUTING.value
        )
        attempt.executed = False
        attempt.updated_at = self._now()

        self.db.flush()

        self._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.EXECUTING.value,
            description=(
                "Scheduled recovery attempt was claimed for "
                "provider execution."
            ),
        )

        self._record_event(
            attempt,
            event_type=RecoveryEventType.EXECUTION_STARTED.value,
            description=(
                "Recovery provider execution started."
            ),
            metadata={
                "action": attempt.action,
                "attempt_number": attempt.attempt_number,
            },
        )

    def mark_awaiting_payment(
        self,
        attempt: RecoveryAttempt,
        *,
        provider_reference_id: str,
    ) -> None:
        """
        Transition:

            executing -> awaiting_payment
        """

        if not provider_reference_id:
            raise ValueError(
                "Provider reference ID is required."
            )

        previous_status = attempt.status

        attempt.status = (
            RecoveryStatus.AWAITING_PAYMENT.value
        )
        attempt.executed = True
        attempt.recovered = None
        attempt.provider_reference_id = (
            provider_reference_id
        )
        attempt.error_message = None
        attempt.executed_at = self._now()
        attempt.completed_at = None

        self.db.flush()

        self._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.AWAITING_PAYMENT.value,
            description=(
                "Recovery checkout was created and is awaiting "
                "verified payment confirmation."
            ),
            metadata={
                "provider_reference_id": provider_reference_id,
            },
        )

        self._record_event(
            attempt,
            event_type=RecoveryEventType.AWAITING_PAYMENT.value,
            description=(
                "Recovery provider order was created and payment "
                "confirmation is pending."
            ),
            metadata={
                "provider_reference_id": provider_reference_id,
            },
        )

    def mark_execution_failed(
        self,
        attempt: RecoveryAttempt,
        *,
        reason: str,
    ) -> None:
        """
        Transition an active recovery attempt to failed.
        """

        previous_status = attempt.status

        attempt.status = (
            RecoveryStatus.FAILED.value
        )
        attempt.executed = False
        attempt.recovered = False
        attempt.error_message = reason
        attempt.completed_at = self._now()

        self.db.flush()

        self._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.FAILED.value,
            description=(
                "Recovery execution failed."
            ),
            metadata={
                "reason": reason,
            },
        )

        self._record_event(
            attempt,
            event_type=RecoveryEventType.EXECUTION_FAILED.value,
            description=reason,
        )

    def mark_completed(
        self,
        attempt: RecoveryAttempt,
        *,
        recovery_payment_id: str | None = None,
        recovered_amount: int | None = None,
    ) -> None:
        """
        Mark a recovery attempt as successfully completed.

        This method should only be called after a verified provider
        success event.
        """

        previous_status = attempt.status

        attempt.status = (
            RecoveryStatus.COMPLETED.value
        )
        attempt.executed = True
        attempt.recovered = True
        attempt.recovery_payment_id = (
            recovery_payment_id
        )
        attempt.recovered_amount = (
            recovered_amount
        )
        attempt.error_message = None
        attempt.completed_at = self._now()

        self.db.flush()

        self._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.COMPLETED.value,
            description=(
                "Recovery payment was successfully confirmed."
            ),
            metadata={
                "recovery_payment_id": recovery_payment_id,
                "recovered_amount": recovered_amount,
            },
        )

        self._record_event(
            attempt,
            event_type=RecoveryEventType.RECOVERED.value,
            description=(
                "Recovery was confirmed by a verified provider "
                "payment success event."
            ),
            metadata={
                "recovery_payment_id": recovery_payment_id,
                "recovered_amount": recovered_amount,
            },
        )

    def mark_cancelled(
        self,
        attempt: RecoveryAttempt,
        *,
        reason: str,
    ) -> None:
        """
        Cancel an active recovery attempt.
        """

        previous_status = attempt.status

        attempt.status = (
            RecoveryStatus.CANCELLED.value
        )
        attempt.recovered = False
        attempt.error_message = reason
        attempt.completed_at = self._now()

        self.db.flush()

        self._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.CANCELLED.value,
            description=(
                "Recovery attempt was cancelled."
            ),
            metadata={
                "reason": reason,
            },
        )

        self._record_event(
            attempt,
            event_type=RecoveryEventType.CANCELLED.value,
            description=reason,
        )

    # ============================================================
    # DECISION + RECORDING
    # ============================================================

    def evaluate_and_record(
        self,
        payment: Payment,
    ) -> tuple[
        RecoveryAttempt | None,
        RecoveryDecision,
        GuardrailResult,
    ]:
        """
        Evaluate a payment for recovery and persist an attempt when
        an executable recovery action is selected.
        """

        if self._is_terminal_payment(payment):
            decision, guardrail = (
                self._no_action_result(
                    "Payment is already completed."
                )
            )

            return None, decision, guardrail

        if self._already_recovered(payment.id):
            decision, guardrail = (
                self._no_action_result(
                    "Payment has already been recovered."
                )
            )

            return None, decision, guardrail

        if (
            self._attempt_count(payment.id)
            >= self.MAX_RECOVERY_ATTEMPTS
        ):
            decision, guardrail = (
                self._no_action_result(
                    "Maximum recovery limit reached."
                )
            )

            return None, decision, guardrail

        if self.agent is None:
            raise RuntimeError(
                "Recovery agent is required for evaluation."
            )

        decision, guardrail = (
            self.agent.evaluate_with_guardrails(
                payment
            )
        )

        if (
            decision.action
            == RecoveryAction.NO_ACTION.value
        ):
            return None, decision, guardrail

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action=decision.action,
            attempt_number=(
                self._next_attempt_number(
                    payment.id
                )
            ),
            recovery_probability=(
                decision.recovery_probability
            ),
            decision_reason=decision.reason,
            guardrail_reason=guardrail.reason,
        )

        if guardrail.allowed:
            attempt.status = (
                RecoveryStatus.APPROVED.value
            )
        else:
            attempt.status = (
                RecoveryStatus.BLOCKED.value
            )
            attempt.recovered = False
            attempt.error_message = (
                guardrail.reason
            )
            attempt.completed_at = self._now()

        self.db.add(attempt)
        self.db.flush()

        # --------------------------------------------------------
        # AUDIT: Attempt created
        # --------------------------------------------------------

        self._record_event(
            attempt,
            event_type=RecoveryEventType.ATTEMPT_CREATED.value,
            description=(
                "Recovery attempt was created after payment "
                "failure evaluation."
            ),
            metadata={
                "action": decision.action,
                "attempt_number": attempt.attempt_number,
                "recovery_probability": (
                    decision.recovery_probability
                ),
            },
        )

        # --------------------------------------------------------
        # AUDIT: AI decision
        # --------------------------------------------------------

        self._record_event(
            attempt,
            event_type=RecoveryEventType.DECISION_MADE.value,
            description=decision.reason,
            metadata={
                "action": decision.action,
                "recovery_probability": (
                    decision.recovery_probability
                ),
            },
        )

        # --------------------------------------------------------
        # AUDIT: Guardrail result
        # --------------------------------------------------------

        if guardrail.allowed:
            self._record_event(
                attempt,
                event_type=(
                    RecoveryEventType
                    .GUARDRAIL_APPROVED
                    .value
                ),
                description=guardrail.reason,
                metadata={
                    "action": decision.action,
                },
            )
        else:
            self._record_event(
                attempt,
                event_type=(
                    RecoveryEventType
                    .GUARDRAIL_BLOCKED
                    .value
                ),
                description=guardrail.reason,
                metadata={
                    "action": decision.action,
                },
            )

        return (
            attempt,
            decision,
            guardrail,
        )

    # ============================================================
    # DECISION + EXECUTION
    # ============================================================

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
        Evaluate a payment and execute or schedule the approved
        recovery intervention.
        """

        (
            attempt,
            decision,
            guardrail,
        ) = self.evaluate_and_record(
            payment
        )

        if attempt is None:
            execution = self._execution_result(
                action=RecoveryAction.NO_ACTION.value,
                status="no_action",
                reason=decision.reason,
            )

            return (
                None,
                decision,
                guardrail,
                execution,
            )

        if not guardrail.allowed:
            execution = self._execution_result(
                action=decision.action,
                status=RecoveryStatus.BLOCKED.value,
                reason=guardrail.reason,
            )

            return (
                attempt,
                decision,
                guardrail,
                execution,
            )

        # --------------------------------------------------------
        # Delayed recovery
        # --------------------------------------------------------

        if (
            decision.action
            == RecoveryAction.WAIT_AND_RETRY.value
        ):
            previous_status = attempt.status

            attempt.status = (
                RecoveryStatus.SCHEDULED.value
            )
            attempt.executed = False
            attempt.scheduled_for = (
                self._now()
                + timedelta(
                    minutes=(
                        self.WAIT_RETRY_DELAY_MINUTES
                    )
                )
            )

            self.db.flush()

            self._record_transition(
                attempt,
                from_status=previous_status,
                to_status=RecoveryStatus.SCHEDULED.value,
                description=(
                    "Recovery retry was scheduled for delayed "
                    "execution."
                ),
                metadata={
                    "scheduled_for": (
                        attempt.scheduled_for
                    ),
                },
            )

            self._record_event(
                attempt,
                event_type=RecoveryEventType.SCHEDULED.value,
                description=(
                    "Recovery retry was approved and scheduled "
                    "for delayed execution."
                ),
                metadata={
                    "scheduled_for": (
                        attempt.scheduled_for
                    ),
                },
            )

            execution = self._execution_result(
                action=decision.action,
                status=RecoveryStatus.SCHEDULED.value,
                reason=(
                    "Recovery retry scheduled for delayed "
                    "execution."
                ),
                executed=False,
                reference_id=None,
            )

            return (
                attempt,
                decision,
                guardrail,
                execution,
            )

        # --------------------------------------------------------
        # Immediate recovery
        # --------------------------------------------------------

        if self.executor is None:
            raise RuntimeError(
                "RecoveryExecutor is required for immediate "
                "recovery execution."
            )

        try:
            execution = self.executor.execute(
                payment,
                decision,
                guardrail,
            )

        except Exception as exc:
            self.mark_execution_failed(
                attempt,
                reason=str(exc),
            )
            raise

        if execution.executed:
            if not execution.reference_id:
                self.mark_execution_failed(
                    attempt,
                    reason=(
                        "Recovery execution returned no provider "
                        "reference ID."
                    ),
                )

                raise RuntimeError(
                    "Provider reference ID is required after "
                    "successful recovery execution."
                )

            self.mark_awaiting_payment(
                attempt,
                provider_reference_id=(
                    execution.reference_id
                ),
            )

        else:
            self.mark_execution_failed(
                attempt,
                reason=execution.reason,
            )

        return (
            attempt,
            decision,
            guardrail,
            execution,
        )