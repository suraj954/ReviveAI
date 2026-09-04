from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import RecoveryStatus
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.models.webhook_event import WebhookEvent


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


def format_amount(amount: int | None) -> float:
    """Convert smallest currency units into major currency units."""
    return round((amount or 0) / 100, 2)


def serialize_datetime(value):
    return value.isoformat() if value is not None else None


def get_latest_attempt_for_payment(
    db: Session,
    payment_id: int,
) -> RecoveryAttempt | None:
    return (
        db.query(RecoveryAttempt)
        .filter(RecoveryAttempt.payment_id == payment_id)
        .order_by(
            RecoveryAttempt.attempt_number.desc(),
            RecoveryAttempt.id.desc(),
        )
        .first()
    )


def is_successful_attempt(attempt: RecoveryAttempt) -> bool:
    return (
        attempt.status == RecoveryStatus.COMPLETED.value
        or attempt.recovered is True
    )


def build_recovery_indexes(attempts: list[RecoveryAttempt]):
    """Build payment-level recovery state without double counting."""
    recovered_payment_ids = {
        attempt.payment_id
        for attempt in attempts
        if is_successful_attempt(attempt)
    }

    successful_attempt_by_payment = {}
    for attempt in attempts:
        if is_successful_attempt(attempt):
            successful_attempt_by_payment[attempt.payment_id] = attempt

    return recovered_payment_ids, successful_attempt_by_payment


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
):
    """
    Return payment-level revenue recovery metrics.

    Revenue at risk, recovered revenue, and active recovery value are
    calculated per original payment, not per recovery attempt.
    """

    payments = db.query(Payment).all()

    attempts = (
        db.query(RecoveryAttempt)
        .order_by(
            RecoveryAttempt.created_at.desc(),
            RecoveryAttempt.id.desc(),
        )
        .all()
    )

    (
        recovered_payment_ids,
        successful_attempt_by_payment,
    ) = build_recovery_indexes(attempts)

    unresolved_failed_payments = [
        payment
        for payment in payments
        if (
            payment.status == "failed"
            and payment.id not in recovered_payment_ids
        )
    ]

    original_successful_payments = [
        payment
        for payment in payments
        if payment.status in {
            "paid",
            "captured",
            "success",
            "succeeded",
        }
    ]

    active_statuses = {
        RecoveryStatus.PENDING.value,
        RecoveryStatus.APPROVED.value,
        RecoveryStatus.SCHEDULED.value,
        RecoveryStatus.EXECUTING.value,
        RecoveryStatus.AWAITING_PAYMENT.value,
    }

    active_attempts = [
        attempt
        for attempt in attempts
        if (
            attempt.status in active_statuses
            and attempt.payment_id not in recovered_payment_ids
        )
    ]

    successful_recovery_payment_ids = recovered_payment_ids

    revenue_at_risk = sum(
        payment.amount or 0
        for payment in unresolved_failed_payments
    )

    # Count at most one recovered amount per original payment.
    revenue_recovered = 0
    for payment in payments:
        attempt = successful_attempt_by_payment.get(payment.id)
        if attempt is None:
            continue

        revenue_recovered += (
            attempt.recovered_amount
            if attempt.recovered_amount is not None
            else payment.amount
        )

    active_payment_ids = {
        attempt.payment_id
        for attempt in active_attempts
    }

    active_recovery_value = sum(
        payment.amount or 0
        for payment in payments
        if payment.id in active_payment_ids
    )

    recovery_payment_ids = {
        attempt.payment_id
        for attempt in attempts
    }

    total_amount_entered_recovery = sum(
        payment.amount or 0
        for payment in payments
        if payment.id in recovery_payment_ids
    )

    recovery_rate = (
        round(
            revenue_recovered
            / total_amount_entered_recovery
            * 100,
            2,
        )
        if total_amount_entered_recovery > 0
        else 0.0
    )

    status_counts = {
        lifecycle_status: sum(
            1
            for attempt in attempts
            if attempt.status == lifecycle_status
        )
        for lifecycle_status in RecoveryStatus
    }

    webhook_events = db.query(WebhookEvent).count()

    return {
        "total_payments": len(payments),
        "failed_payments": len(unresolved_failed_payments),
        "successful_payments": len(original_successful_payments),
        "total_payment_amount": format_amount(
            sum(payment.amount or 0 for payment in payments)
        ),
        "revenue_at_risk": format_amount(revenue_at_risk),
        "revenue_recovered": format_amount(revenue_recovered),
        "active_recovery_value": format_amount(active_recovery_value),
        "recovery_rate": recovery_rate,
        "total_recovery_attempts": len(attempts),
        "active_recoveries": len(active_attempts),
        "scheduled_recoveries": status_counts[RecoveryStatus.SCHEDULED],
        "executing_recoveries": status_counts[RecoveryStatus.EXECUTING],
        "awaiting_payment_recoveries": status_counts[
            RecoveryStatus.AWAITING_PAYMENT
        ],
        "successful_recoveries": len(successful_recovery_payment_ids),
        "failed_recoveries": status_counts[RecoveryStatus.FAILED],
        "blocked_recoveries": status_counts[RecoveryStatus.BLOCKED],
        "cancelled_recoveries": status_counts[RecoveryStatus.CANCELLED],
        "exhausted_recoveries": status_counts[RecoveryStatus.EXHAUSTED],
        "webhook_events": webhook_events,
    }


@router.get("/payments")
def get_payments(
    db: Session = Depends(get_db),
):
    """
    Return payments with payment-level recovery state.

    `is_recovered` is authoritative for UI filtering. The original
    payment may remain historically `failed` even after a separate
    recovery order successfully recovers the revenue.
    """

    payments = (
        db.query(Payment)
        .order_by(Payment.created_at.desc())
        .all()
    )

    all_attempts = db.query(RecoveryAttempt).all()

    attempts_by_payment: dict[int, list[RecoveryAttempt]] = {}
    for attempt in all_attempts:
        attempts_by_payment.setdefault(
            attempt.payment_id,
            [],
        ).append(attempt)

    results = []

    for payment in payments:
        payment_attempts = attempts_by_payment.get(payment.id, [])
        payment_attempts.sort(
            key=lambda attempt: (
                attempt.attempt_number,
                attempt.id,
            )
        )

        latest_attempt = (
            payment_attempts[-1]
            if payment_attempts
            else None
        )

        successful_attempts = [
            attempt
            for attempt in payment_attempts
            if is_successful_attempt(attempt)
        ]

        is_recovered = bool(successful_attempts)

        recovery = None
        if latest_attempt:
            recovery = {
                "attempt_id": latest_attempt.id,
                "attempt_number": latest_attempt.attempt_number,
                "action": latest_attempt.action,
                "recovery_probability": (
                    latest_attempt.recovery_probability
                ),
                "decision_reason": latest_attempt.decision_reason,
                "guardrail_reason": latest_attempt.guardrail_reason,
                "status": (
                    RecoveryStatus.COMPLETED.value
                    if is_recovered
                    else latest_attempt.status
                ),
                "executed": latest_attempt.executed,
                "recovered": is_recovered,
                "provider_reference_id": (
                    latest_attempt.provider_reference_id
                ),
                "recovery_payment_id": (
                    successful_attempts[-1].recovery_payment_id
                    if successful_attempts
                    else latest_attempt.recovery_payment_id
                ),
                "recovered_amount": format_amount(
                    successful_attempts[-1].recovered_amount
                    if successful_attempts
                    else latest_attempt.recovered_amount
                ),
                "error_message": latest_attempt.error_message,
                "created_at": serialize_datetime(
                    latest_attempt.created_at
                ),
                "scheduled_for": serialize_datetime(
                    latest_attempt.scheduled_for
                ),
                "executed_at": serialize_datetime(
                    latest_attempt.executed_at
                ),
                "completed_at": serialize_datetime(
                    (
                        successful_attempts[-1].completed_at
                        if successful_attempts
                        else latest_attempt.completed_at
                    )
                ),
                "updated_at": serialize_datetime(
                    latest_attempt.updated_at
                ),
            }

        results.append(
            {
                "id": payment.id,
                "order_id": payment.razorpay_order_id,
                "payment_id": payment.razorpay_payment_id,
                "amount": format_amount(payment.amount),
                "currency": payment.currency,
                "status": payment.status,
                "receipt": payment.receipt,
                "failure_code": payment.failure_code,
                "failure_reason": payment.failure_reason,
                "failure_description": payment.failure_description,
                "created_at": serialize_datetime(payment.created_at),
                "updated_at": serialize_datetime(payment.updated_at),
                "is_recovered": is_recovered,
                "recovery": recovery,
            }
        )

    return {
        "count": len(results),
        "payments": results,
    }


@router.get("/recovery-attempts")
def get_recovery_attempts(
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(RecoveryAttempt, Payment)
        .join(
            Payment,
            RecoveryAttempt.payment_id == Payment.id,
        )
        .order_by(
            RecoveryAttempt.created_at.desc(),
            RecoveryAttempt.id.desc(),
        )
        .all()
    )

    results = []

    for attempt, payment in attempts:
        results.append(
            {
                "id": attempt.id,
                "payment_id": payment.id,
                "attempt_number": attempt.attempt_number,
                "razorpay_order_id": payment.razorpay_order_id,
                "razorpay_payment_id": payment.razorpay_payment_id,
                "amount": format_amount(payment.amount),
                "currency": payment.currency,
                "payment_status": payment.status,
                "failure_code": payment.failure_code,
                "failure_reason": payment.failure_reason,
                "failure_description": payment.failure_description,
                "action": attempt.action,
                "recovery_probability": attempt.recovery_probability,
                "decision_reason": attempt.decision_reason,
                "guardrail_reason": attempt.guardrail_reason,
                "status": attempt.status,
                "executed": attempt.executed,
                "recovered": attempt.recovered,
                "provider_reference_id": attempt.provider_reference_id,
                "recovery_payment_id": attempt.recovery_payment_id,
                "recovered_amount": format_amount(
                    attempt.recovered_amount
                ),
                "error_message": attempt.error_message,
                "created_at": serialize_datetime(attempt.created_at),
                "scheduled_for": serialize_datetime(
                    attempt.scheduled_for
                ),
                "executed_at": serialize_datetime(
                    attempt.executed_at
                ),
                "completed_at": serialize_datetime(
                    attempt.completed_at
                ),
                "updated_at": serialize_datetime(attempt.updated_at),
            }
        )

    return {
        "count": len(results),
        "recovery_attempts": results,
    }


@router.get("/recovery-pipeline")
def get_recovery_pipeline(
    db: Session = Depends(get_db),
):
    attempts = db.query(RecoveryAttempt).all()

    pipeline = {}

    for lifecycle_status in RecoveryStatus:
        matching_attempts = [
            attempt
            for attempt in attempts
            if attempt.status == lifecycle_status.value
        ]

        pipeline[lifecycle_status.value] = {
            "count": len(matching_attempts),
            "value": format_amount(
                sum(
                    attempt.payment.amount
                    if attempt.payment
                    else 0
                    for attempt in matching_attempts
                )
            ),
        }

    return {
        "pipeline": pipeline,
        "total_attempts": len(attempts),
    }
