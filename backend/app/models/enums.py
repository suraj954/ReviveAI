from enum import Enum


class PaymentStatus(str, Enum):
    CREATED = "created"
    FAILED = "failed"
    CAPTURED = "captured"
    PAID = "paid"


class RecoveryStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    AWAITING_PAYMENT = "awaiting_payment"

    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXHAUSTED = "exhausted"


class RecoveryAction(str, Enum):
    RETRY = "retry"
    WAIT_AND_RETRY = "wait_and_retry"
    NO_ACTION = "no_action"


class RecoveryEventType(str, Enum):
    """
    Immutable audit events emitted throughout the recovery lifecycle.
    """

    ATTEMPT_CREATED = "attempt_created"
    DECISION_MADE = "decision_made"
    GUARDRAIL_APPROVED = "guardrail_approved"
    GUARDRAIL_BLOCKED = "guardrail_blocked"

    SCHEDULED = "scheduled"
    EXECUTION_STARTED = "execution_started"
    AWAITING_PAYMENT = "awaiting_payment"

    RECOVERED = "recovered"
    CANCELLED = "cancelled"
    EXECUTION_FAILED = "execution_failed"


class WebhookStatus(str, Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"