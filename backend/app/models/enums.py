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


class WebhookStatus(str, Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"