from dataclasses import dataclass

from app.decisions.policy import RecoveryDecision


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str


def apply_guardrails(
    decision: RecoveryDecision,
    *,
    recovery_probability: float | None = None,
) -> GuardrailResult:
    """
    Safety layer between recovery recommendations and execution.

    The ML model may recommend an action, but guardrails determine
    whether that recommendation is safe to execute.
    """

    if decision.action == "no_action":
        return GuardrailResult(
            allowed=False,
            reason="No recovery action was recommended.",
        )

    if recovery_probability is not None:
        if not 0.0 <= recovery_probability <= 1.0:
            raise ValueError(
                "recovery_probability must be between 0.0 and 1.0."
            )

        if recovery_probability < 0.50:
            return GuardrailResult(
                allowed=False,
                reason="Recovery probability is below the execution threshold.",
            )

    if decision.action not in {
        "retry",
        "wait_and_retry",
    }:
        return GuardrailResult(
            allowed=False,
            reason="Recovery action is not permitted by guardrails.",
        )

    return GuardrailResult(
        allowed=True,
        reason="Recovery action passed all guardrails.",
    )