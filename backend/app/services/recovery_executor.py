from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.decisions.guardrails import GuardrailResult
from app.decisions.policy import RecoveryDecision
from app.models.payment import Payment


class RecoveryGateway(Protocol):
    """
    Provider abstraction for executing recovery actions.

    A concrete Razorpay implementation can be plugged in later
    without coupling the recovery engine to the Razorpay SDK.
    """

    def execute_retry(self, payment: Payment) -> str:
        """
        Execute the provider-specific recovery mechanism.

        Returns a provider/reference identifier for the recovery
        operation.
        """
        ...

    def execute_wait_and_retry(self, payment: Payment) -> str:
        """
        Execute or schedule the provider-specific delayed recovery
        mechanism.
        """
        ...


@dataclass(frozen=True)
class RecoveryExecutionResult:
    """
    Result of a recovery execution attempt.
    """

    executed: bool
    action: str
    status: str
    reference_id: str | None
    reason: str


class RecoveryExecutor:
    """
    Executes only recovery decisions that have passed guardrails.

    The executor does not make recovery decisions itself.
    It is deliberately separated from the agent and policy layers.
    """

    def __init__(self, gateway: RecoveryGateway) -> None:
        self.gateway = gateway

    def execute(
        self,
        payment: Payment,
        decision: RecoveryDecision,
        guardrail_result: GuardrailResult,
    ) -> RecoveryExecutionResult:
        """
        Execute an approved recovery decision.

        Guardrails are mandatory. A decision that has not been
        explicitly approved is never sent to the payment gateway.
        """

        if not guardrail_result.allowed:
            return RecoveryExecutionResult(
                executed=False,
                action=decision.action,
                status="blocked",
                reference_id=None,
                reason=guardrail_result.reason,
            )

        if decision.action == "retry":
            reference_id = self.gateway.execute_retry(payment)

            return RecoveryExecutionResult(
                executed=True,
                action=decision.action,
                status="executed",
                reference_id=reference_id,
                reason="Recovery retry was executed successfully.",
            )

        if decision.action == "wait_and_retry":
            reference_id = self.gateway.execute_wait_and_retry(
                payment
            )

            return RecoveryExecutionResult(
                executed=True,
                action=decision.action,
                status="scheduled",
                reference_id=reference_id,
                reason="Recovery retry was scheduled successfully.",
            )

        return RecoveryExecutionResult(
            executed=False,
            action=decision.action,
            status="blocked",
            reference_id=None,
            reason="Recovery action is not supported by the executor.",
        )