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
    Coordinates the complete payment recovery lifecycle.

    Responsibilities:

    1. Prevent invalid recovery attempts.
    2. Ask the AI recovery agent for a recovery decision.
    3. Apply guardrail results.
    4. Persist recovery attempts.
    5. Execute immediate recovery actions.
    6. Schedule delayed recovery actions.
    7. Record immutable audit events.
    8. Provide centralized lifecycle transition helpers.

    Important:
    A recovery attempt being executed does NOT mean revenue has
    been recovered.

    Recovery is considered successful only after a verified provider
    webhook confirms successful payment completion.
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
    # TIME HELPERS
    # ============================================================

    @staticmethod
    def _now() -> datetime:
        """Return the current UTC timestamp."""
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
        Record an immutable audit event.

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
        """Record a standardized lifecycle state transition."""

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
        """Build a standardized no-action decision."""

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
        """Build a standardized execution result."""

        return RecoveryExecutionResult(
            executed=executed,
            action=action,
            status=status,
            reference_id=reference_id,
            reason=reason,
        )

    # ============================================================
    # PAYMENT STATE HELPERS
    # ============================================================

    def _is_terminal_payment(
        self,
        payment: Payment,
    ) -> bool:
        """
        Return True when the original payment is already successful.
        """

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
        Fetch all recovery attempts for a payment.

        Supports both real SQLAlchemy sessions and lightweight
        FakeSession objects used in tests.
        """

        query = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment_id
            )
        )

        # Support lightweight test doubles.
        if hasattr(query, "items"):
            return [
                attempt
                for attempt in query.items
                if getattr(
                    attempt,
                    "payment_id",
                    None,
                )
                == payment_id
            ]

        return query.all()

    def _already_recovered(
        self,
        payment_id: int,
    ) -> bool:
        """Check whether any previous recovery attempt succeeded."""

        attempts = self._get_attempts(payment_id)

        return any(
            (
                getattr(
                    attempt,
                    "recovered",
                    None,
                )
                is True
            )
            or (
                getattr(
                    attempt,
                    "status",
                    None,
                )
                == RecoveryStatus.COMPLETED.value
            )
            for attempt in attempts
        )

    def _attempt_count(
        self,
        payment_id: int,
    ) -> int:
        """Count all recovery attempts for a payment."""

        return len(
            self._get_attempts(payment_id)
        )

    def _next_attempt_number(
        self,
        payment_id: int,
    ) -> int:
        """Calculate the next sequential recovery attempt number."""

        attempts = self._get_attempts(payment_id)

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
    # ACTIVE ATTEMPT HELPERS
    # ============================================================

    @staticmethod
    def _active_statuses() -> tuple[str, ...]:
        """Statuses representing an unfinished recovery workflow."""

        return (
            RecoveryStatus.PENDING.value,
            RecoveryStatus.APPROVED.value,
            RecoveryStatus.EXECUTING.value,
            RecoveryStatus.AWAITING_PAYMENT.value,
            RecoveryStatus.SCHEDULED.value,
        )

    # ============================================================
    # LIFECYCLE TRANSITIONS
    # ============================================================

    def claim_scheduled_attempt(
        self,
        attempt: RecoveryAttempt,
    ) -> None:
        """
        Transition:

            scheduled -> executing

        Called by the recovery scheduler before provider execution.
        """

        if (
            attempt.status
            != RecoveryStatus.SCHEDULED.value
        ):
            raise RuntimeError(
                "Only scheduled recovery attempts can be claimed."
            )

        previous_status = attempt.status

        attempt.status = RecoveryStatus.EXECUTING.value
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
        Transition an executed recovery attempt to awaiting_payment.

        This means the provider-side recovery checkout/order was
        successfully created, but payment success has not yet been
        verified.
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
        attempt.provider_reference_id = provider_reference_id
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
        """Transition an active recovery attempt to failed."""

        previous_status = attempt.status

        attempt.status = RecoveryStatus.FAILED.value
        attempt.executed = False
        attempt.recovered = False
        attempt.error_message = reason
        attempt.completed_at = self._now()

        self.db.flush()

        self._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.FAILED.value,
            description="Recovery execution failed.",
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
        success webhook confirms the recovery payment.
        """

        previous_status = attempt.status

        attempt.status = RecoveryStatus.COMPLETED.value
        attempt.executed = True
        attempt.recovered = True
        attempt.recovery_payment_id = recovery_payment_id
        attempt.recovered_amount = recovered_amount
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
        """Cancel an active recovery attempt."""

        # A completed recovery is terminal and must never be cancelled.
        if (
            attempt.status
            == RecoveryStatus.COMPLETED.value
        ):
            return

        previous_status = attempt.status

        attempt.status = RecoveryStatus.CANCELLED.value
        attempt.executed = False
        attempt.recovered = False
        attempt.error_message = reason
        attempt.completed_at = self._now()

        self.db.flush()

        self._record_transition(
            attempt,
            from_status=previous_status,
            to_status=RecoveryStatus.CANCELLED.value,
            description="Recovery attempt was cancelled.",
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
    # PAYMENT-LEVEL CANCELLATION
    # ============================================================

    def cancel_active_attempts_for_payment(
        self,
        payment: Payment,
        *,
        reason: str = (
            "Original payment succeeded before recovery "
            "was completed."
        ),
        exclude_attempt_id: int | None = None,
    ) -> int:
        """
        Cancel all active recovery attempts for a payment.

        exclude_attempt_id is important when one recovery attempt has
        just succeeded. The successful attempt must remain COMPLETED,
        while only sibling active attempts are cancelled.

        The method intentionally operates only on active statuses.
        Failed and completed attempts are historical records and must
        remain untouched.
        """

        active_statuses = self._active_statuses()

        query = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment.id,
                RecoveryAttempt.status.in_(active_statuses),
            )
        )

        # Support lightweight test doubles.
        if hasattr(query, "items"):
            attempts = [
                candidate
                for candidate in query.items
                if (
                    getattr(
                        candidate,
                        "payment_id",
                        None,
                    )
                    == payment.id
                    and getattr(
                        candidate,
                        "status",
                        None,
                    )
                    in active_statuses
                    and (
                        exclude_attempt_id is None
                        or getattr(
                            candidate,
                            "id",
                            None,
                        )
                        != exclude_attempt_id
                    )
                )
            ]
        else:
            attempts = query.all()

            if exclude_attempt_id is not None:
                attempts = [
                    candidate
                    for candidate in attempts
                    if candidate.id != exclude_attempt_id
                ]

        cancelled_count = 0

        for candidate in attempts:
            self.mark_cancelled(
                candidate,
                reason=reason,
            )
            cancelled_count += 1

        return cancelled_count

    # ============================================================
    # PROVIDER WEBHOOK COMPLETION
    # ============================================================

    def complete_from_provider_webhook(
        self,
        attempt: RecoveryAttempt,
        *,
        recovery_payment_id: str | None,
        recovered_amount: int | None,
    ) -> None:
        """
        Complete a recovery attempt after a verified provider webhook.

        Idempotent because payment providers may send duplicate
        payment.captured and order.paid events.

        After one recovery attempt succeeds:

        1. That exact attempt remains COMPLETED.
        2. Every other active attempt for the same payment is cancelled.
        3. No stale checkout should remain awaiting_payment.
        """

        # Duplicate webhook for an already completed attempt.
        if (
            attempt.status
            == RecoveryStatus.COMPLETED.value
            and getattr(
                attempt,
                "recovered",
                None,
            )
            is True
        ):
            return

        self.mark_completed(
            attempt,
            recovery_payment_id=recovery_payment_id,
            recovered_amount=recovered_amount,
        )

        # Fake objects used by isolated unit tests may not expose the
        # SQLAlchemy relationship. In production, payment is normally
        # available through attempt.payment.
        payment = getattr(
            attempt,
            "payment",
            None,
        )

        if payment is None:
            return

        # Cancel only sibling active attempts.
        # Never cancel the attempt that was just completed.
        self.cancel_active_attempts_for_payment(
            payment,
            reason=(
                "Another recovery attempt successfully recovered "
                "the payment."
            ),
            exclude_attempt_id=getattr(
                attempt,
                "id",
                None,
            ),
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
        Evaluate a failed payment and persist a recovery attempt when
        an executable recovery action is selected.
        """

        # --------------------------------------------------------
        # Original payment already succeeded
        # --------------------------------------------------------

        if self._is_terminal_payment(payment):
            decision, guardrail = self._no_action_result(
                "Payment is already completed."
            )

            return None, decision, guardrail

        # --------------------------------------------------------
        # Recovery already succeeded
        # --------------------------------------------------------

        if self._already_recovered(payment.id):
            decision, guardrail = self._no_action_result(
                "Payment has already been recovered."
            )

            return None, decision, guardrail

        # --------------------------------------------------------
        # Maximum retry limit
        # --------------------------------------------------------

        if (
            self._attempt_count(payment.id)
            >= self.MAX_RECOVERY_ATTEMPTS
        ):
            decision, guardrail = self._no_action_result(
                "Maximum recovery limit reached."
            )

            return None, decision, guardrail

        # --------------------------------------------------------
        # AI evaluation
        # --------------------------------------------------------

        if self.agent is None:
            raise RuntimeError(
                "Recovery agent is required for evaluation."
            )

        decision, guardrail = (
            self.agent.evaluate_with_guardrails(
                payment
            )
        )

        # --------------------------------------------------------
        # No action
        # --------------------------------------------------------

        if (
            decision.action
            == RecoveryAction.NO_ACTION.value
        ):
            return None, decision, guardrail

        # --------------------------------------------------------
        # Create recovery attempt
        # --------------------------------------------------------

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
            attempt.error_message = guardrail.reason
            attempt.completed_at = self._now()

        self.db.add(attempt)
        self.db.flush()

        # --------------------------------------------------------
        # AUDIT: ATTEMPT CREATED
        # --------------------------------------------------------

        self._record_event(
            attempt,
            event_type=(
                RecoveryEventType.ATTEMPT_CREATED.value
            ),
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
        # AUDIT: AI DECISION
        # --------------------------------------------------------

        self._record_event(
            attempt,
            event_type=(
                RecoveryEventType.DECISION_MADE.value
            ),
            description=decision.reason,
            metadata={
                "action": decision.action,
                "recovery_probability": (
                    decision.recovery_probability
                ),
            },
        )

        # --------------------------------------------------------
        # AUDIT: GUARDRAIL RESULT
        # --------------------------------------------------------

        if guardrail.allowed:
            self._record_event(
                attempt,
                event_type=(
                    RecoveryEventType.GUARDRAIL_APPROVED.value
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
                    RecoveryEventType.GUARDRAIL_BLOCKED.value
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
        ) = self.evaluate_and_record(payment)

        # --------------------------------------------------------
        # No recovery attempt
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Guardrail blocked
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Provider execution succeeded
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Provider execution failed
        # --------------------------------------------------------

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