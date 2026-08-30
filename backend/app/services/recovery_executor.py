from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.enums import RecoveryAction
from app.models.payment import Payment


class RecoveryGateway(Protocol):
    """
    Provider abstraction for recovery execution.

    The recovery engine depends on this interface rather than a
    specific payment provider implementation.
    """

    def execute_retry(
        self,
        payment: Payment,
    ) -> str:
        """
        Execute an immediate recovery retry.

        Returns the provider recovery reference/order ID.
        """
        ...

    def execute_wait_and_retry(
        self,
        payment: Payment,
    ) -> str:
        """
        Schedule a delayed recovery retry.

        Returns the scheduling reference ID.
        """
        ...


@dataclass(frozen=True)
class RecoveryExecutionResult:
    """
    Result of attempting to execute a recovery intervention.
    """

    executed: bool
    action: str
    status: str
    reference_id: str | None
    reason: str


class RecoveryExecutor:
    """
    Executes recovery actions only after explicit guardrail approval.

    This layer performs provider side effects but does not:
    - make AI decisions
    - bypass guardrails
    - declare revenue recovered

    Revenue recovery is confirmed only by a verified provider
    payment success event.
    """

    def __init__(
        self,
        gateway: RecoveryGateway,
    ) -> None:
        self.gateway = gateway

    def execute(
        self,
        payment: Payment,
        decision: RecoveryDecision,
        guardrail_result: GuardrailResult,
    ) -> RecoveryExecutionResult:
        """
        Execute an approved recovery decision.
        """

        # Safety boundary: execution is impossible without explicit
        # guardrail approval.
        if not guardrail_result.allowed:
            return RecoveryExecutionResult(
                executed=False,
                action=decision.action,
                status="blocked",
                reference_id=None,
                reason=guardrail_result.reason,
            )

        # Immediate retry.
        if decision.action == RecoveryAction.RETRY.value:
            reference_id = self.gateway.execute_retry(payment)

            return RecoveryExecutionResult(
                executed=True,
                action=decision.action,
                status="executed",
                reference_id=reference_id,
                reason=(
                    "Recovery retry was executed successfully."
                ),
            )

        # Delayed retry scheduling.
        if (
            decision.action
            == RecoveryAction.WAIT_AND_RETRY.value
        ):
            reference_id = (
                self.gateway.execute_wait_and_retry(payment)
            )

            return RecoveryExecutionResult(
                executed=True,
                action=decision.action,
                status="scheduled",
                reference_id=reference_id,
                reason=(
                    "Recovery retry was scheduled successfully."
                ),
            )

        # Explicit no-action / unsupported action.
        return RecoveryExecutionResult(
            executed=False,
            action=decision.action,
            status="blocked",
            reference_id=None,
            reason=(
                "No supported executable recovery action was "
                "selected."
            ),
        )