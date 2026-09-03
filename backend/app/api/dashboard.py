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


# =============================================================
# HELPERS
# =============================================================


def format_amount(amount: int | None) -> float:
    """
    Convert an amount stored in the smallest currency unit
    (paise for INR) into major currency units.
    """

    return round((amount or 0) / 100, 2)


def serialize_datetime(value):
    """
    Safely serialize optional datetime values.
    """

    if value is None:
        return None

    return value.isoformat()


def get_latest_attempt_for_payment(
    db: Session,
    payment_id: int,
) -> RecoveryAttempt | None:
    """
    Return the most recent recovery attempt for a payment.
    """

    return (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.payment_id == payment_id
        )
        .order_by(
            RecoveryAttempt.attempt_number.desc(),
            RecoveryAttempt.id.desc(),
        )
        .first()
    )


# =============================================================
# DASHBOARD SUMMARY
# =============================================================


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
):
    """
    Return high-level revenue recovery metrics.

    The dashboard reflects the actual ReviveAI recovery lifecycle:

        Payment Failure
                ↓
        Revenue At Risk
                ↓
        AI Decision
                ↓
        Guardrail Approval
                ↓
        Recovery Attempt
                ↓
        scheduled / executing / awaiting_payment
                ↓
        Verified Webhook Confirmation
                ↓
        completed
    """

    # ---------------------------------------------------------
    # PAYMENT METRICS
    # ---------------------------------------------------------

    payments = db.query(Payment).all()

    total_payments = len(payments)

    failed_payments = [
        payment
        for payment in payments
        if payment.status == "failed"
    ]

    successful_payments = [
        payment
        for payment in payments
        if payment.status in {
            "paid",
            "captured",
            "success",
            "succeeded",
        }
    ]

    total_payment_amount = sum(
        payment.amount or 0
        for payment in payments
    )

    revenue_at_risk = sum(
        payment.amount or 0
        for payment in failed_payments
    )

    # ---------------------------------------------------------
    # RECOVERY ATTEMPTS
    # ---------------------------------------------------------

    attempts = (
        db.query(RecoveryAttempt)
        .order_by(
            RecoveryAttempt.created_at.desc()
        )
        .all()
    )

    total_recovery_attempts = len(attempts)

    # ---------------------------------------------------------
    # SUCCESSFUL RECOVERIES
    # ---------------------------------------------------------

    successful_attempts = [
        attempt
        for attempt in attempts
        if (
            attempt.status
            == RecoveryStatus.COMPLETED.value
            or attempt.recovered is True
        )
    ]

    # ---------------------------------------------------------
    # ACTIVE RECOVERIES
    # ---------------------------------------------------------

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
        if attempt.status in active_statuses
    ]

    # ---------------------------------------------------------
    # INDIVIDUAL LIFECYCLE COUNTS
    # ---------------------------------------------------------

    scheduled_attempts = [
        attempt
        for attempt in attempts
        if attempt.status
        == RecoveryStatus.SCHEDULED.value
    ]

    executing_attempts = [
        attempt
        for attempt in attempts
        if attempt.status
        == RecoveryStatus.EXECUTING.value
    ]

    awaiting_payment_attempts = [
        attempt
        for attempt in attempts
        if attempt.status
        == RecoveryStatus.AWAITING_PAYMENT.value
    ]

    failed_attempts = [
        attempt
        for attempt in attempts
        if attempt.status
        == RecoveryStatus.FAILED.value
    ]

    blocked_attempts = [
        attempt
        for attempt in attempts
        if attempt.status
        == RecoveryStatus.BLOCKED.value
    ]

    cancelled_attempts = [
        attempt
        for attempt in attempts
        if attempt.status
        == RecoveryStatus.CANCELLED.value
    ]

    exhausted_attempts = [
        attempt
        for attempt in attempts
        if attempt.status
        == RecoveryStatus.EXHAUSTED.value
    ]

    # ---------------------------------------------------------
    # RECOVERED REVENUE
    # ---------------------------------------------------------

    revenue_recovered = sum(
        attempt.recovered_amount or 0
        for attempt in successful_attempts
    )

    # ---------------------------------------------------------
    # ACTIVE RECOVERY VALUE
    # ---------------------------------------------------------

    active_payment_ids = {
        attempt.payment_id
        for attempt in active_attempts
    }

    active_recovery_value = sum(
        payment.amount or 0
        for payment in payments
        if payment.id in active_payment_ids
    )

    # ---------------------------------------------------------
    # TOTAL REVENUE THAT ENTERED RECOVERY
    # ---------------------------------------------------------

    recovery_payment_ids = {
        attempt.payment_id
        for attempt in attempts
    }

    total_amount_entered_recovery = sum(
        payment.amount or 0
        for payment in payments
        if payment.id in recovery_payment_ids
    )

    # ---------------------------------------------------------
    # RECOVERY RATE
    # ---------------------------------------------------------

    if total_amount_entered_recovery > 0:
        recovery_rate = round(
            (
                revenue_recovered
                / total_amount_entered_recovery
            )
            * 100,
            2,
        )
    else:
        recovery_rate = 0.0

    # ---------------------------------------------------------
    # WEBHOOK METRICS
    # ---------------------------------------------------------

    webhook_events = (
        db.query(WebhookEvent)
        .count()
    )

    # ---------------------------------------------------------
    # RETURN
    # ---------------------------------------------------------

    return {
        # =====================================================
        # PAYMENT OVERVIEW
        # =====================================================

        "total_payments": total_payments,

        "failed_payments": len(
            failed_payments
        ),

        "successful_payments": len(
            successful_payments
        ),

        "total_payment_amount": format_amount(
            total_payment_amount
        ),

        # =====================================================
        # REVENUE RECOVERY
        # =====================================================

        "revenue_at_risk": format_amount(
            revenue_at_risk
        ),

        "revenue_recovered": format_amount(
            revenue_recovered
        ),

        "active_recovery_value": format_amount(
            active_recovery_value
        ),

        "recovery_rate": recovery_rate,

        # =====================================================
        # RECOVERY PIPELINE
        # =====================================================

        "total_recovery_attempts": (
            total_recovery_attempts
        ),

        "active_recoveries": len(
            active_attempts
        ),

        "scheduled_recoveries": len(
            scheduled_attempts
        ),

        "executing_recoveries": len(
            executing_attempts
        ),

        "awaiting_payment_recoveries": len(
            awaiting_payment_attempts
        ),

        "successful_recoveries": len(
            successful_attempts
        ),

        "failed_recoveries": len(
            failed_attempts
        ),

        "blocked_recoveries": len(
            blocked_attempts
        ),

        "cancelled_recoveries": len(
            cancelled_attempts
        ),

        "exhausted_recoveries": len(
            exhausted_attempts
        ),

        # =====================================================
        # SYSTEM OBSERVABILITY
        # =====================================================

        "webhook_events": webhook_events,
    }


# =============================================================
# PAYMENTS
# =============================================================


@router.get("/payments")
def get_payments(
    db: Session = Depends(get_db),
):
    """
    Return all payments with their latest recovery attempt.

    This endpoint is optimized for dashboard tables and allows
    the frontend to visualize the current recovery lifecycle
    of every monitored payment.
    """

    payments = (
        db.query(Payment)
        .order_by(
            Payment.created_at.desc()
        )
        .all()
    )

    results = []

    for payment in payments:

        latest_attempt = (
            get_latest_attempt_for_payment(
                db,
                payment.id,
            )
        )

        recovery = None

        if latest_attempt:

            recovery = {
                "attempt_id": latest_attempt.id,

                "attempt_number": (
                    latest_attempt.attempt_number
                ),

                # AI decision
                "action": latest_attempt.action,

                "recovery_probability": (
                    latest_attempt.recovery_probability
                ),

                "decision_reason": (
                    latest_attempt.decision_reason
                ),

                # Guardrail
                "guardrail_reason": (
                    latest_attempt.guardrail_reason
                ),

                # Lifecycle
                "status": latest_attempt.status,

                "executed": latest_attempt.executed,

                "recovered": latest_attempt.recovered,

                # Provider references
                "provider_reference_id": (
                    latest_attempt.provider_reference_id
                ),

                "recovery_payment_id": (
                    latest_attempt.recovery_payment_id
                ),

                # Financial result
                "recovered_amount": format_amount(
                    latest_attempt.recovered_amount
                ),

                # Failure information
                "error_message": (
                    latest_attempt.error_message
                ),

                # Timestamps
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
                    latest_attempt.completed_at
                ),

                "updated_at": serialize_datetime(
                    latest_attempt.updated_at
                ),
            }

        results.append(
            {
                # ------------------------------------------------
                # PAYMENT IDENTITY
                # ------------------------------------------------

                "id": payment.id,

                "order_id": (
                    payment.razorpay_order_id
                ),

                "payment_id": (
                    payment.razorpay_payment_id
                ),

                # ------------------------------------------------
                # PAYMENT VALUE
                # ------------------------------------------------

                "amount": format_amount(
                    payment.amount
                ),

                "currency": payment.currency,

                # ------------------------------------------------
                # PAYMENT STATUS
                # ------------------------------------------------

                "status": payment.status,

                "receipt": payment.receipt,

                # ------------------------------------------------
                # FAILURE INTELLIGENCE
                # ------------------------------------------------

                "failure_code": (
                    payment.failure_code
                ),

                "failure_reason": (
                    payment.failure_reason
                ),

                "failure_description": (
                    payment.failure_description
                ),

                # ------------------------------------------------
                # TIMESTAMPS
                # ------------------------------------------------

                "created_at": serialize_datetime(
                    payment.created_at
                ),

                "updated_at": serialize_datetime(
                    payment.updated_at
                ),

                # ------------------------------------------------
                # LATEST RECOVERY STATE
                # ------------------------------------------------

                "recovery": recovery,
            }
        )

    return {
        "count": len(results),
        "payments": results,
    }


# =============================================================
# RECOVERY ATTEMPTS
# =============================================================


@router.get("/recovery-attempts")
def get_recovery_attempts(
    db: Session = Depends(get_db),
):
    """
    Return all recovery attempts with their associated payment data.

    Includes:
    - AI recovery decision
    - recovery probability
    - guardrail reasoning
    - lifecycle state
    - provider references
    - verified recovery outcome
    """

    attempts = (
        db.query(
            RecoveryAttempt,
            Payment,
        )
        .join(
            Payment,
            RecoveryAttempt.payment_id
            == Payment.id,
        )
        .order_by(
            RecoveryAttempt.created_at.desc()
        )
        .all()
    )

    results = []

    for attempt, payment in attempts:

        results.append(
            {
                # =================================================
                # ATTEMPT IDENTITY
                # =================================================

                "id": attempt.id,

                "payment_id": payment.id,

                "attempt_number": (
                    attempt.attempt_number
                ),

                # =================================================
                # ORIGINAL PAYMENT
                # =================================================

                "razorpay_order_id": (
                    payment.razorpay_order_id
                ),

                "razorpay_payment_id": (
                    payment.razorpay_payment_id
                ),

                "amount": format_amount(
                    payment.amount
                ),

                "currency": payment.currency,

                "payment_status": payment.status,

                # =================================================
                # FAILURE CONTEXT
                # =================================================

                "failure_code": (
                    payment.failure_code
                ),

                "failure_reason": (
                    payment.failure_reason
                ),

                "failure_description": (
                    payment.failure_description
                ),

                # =================================================
                # AI DECISION
                # =================================================

                "action": attempt.action,

                "recovery_probability": (
                    attempt.recovery_probability
                ),

                "decision_reason": (
                    attempt.decision_reason
                ),

                # =================================================
                # GUARDRAIL
                # =================================================

                "guardrail_reason": (
                    attempt.guardrail_reason
                ),

                # =================================================
                # LIFECYCLE
                # =================================================

                "status": attempt.status,

                "executed": attempt.executed,

                "recovered": attempt.recovered,

                # =================================================
                # PROVIDER EXECUTION
                # =================================================

                "provider_reference_id": (
                    attempt.provider_reference_id
                ),

                "recovery_payment_id": (
                    attempt.recovery_payment_id
                ),

                # =================================================
                # RECOVERY OUTCOME
                # =================================================

                "recovered_amount": format_amount(
                    attempt.recovered_amount
                ),

                "error_message": (
                    attempt.error_message
                ),

                # =================================================
                # TIMESTAMPS
                # =================================================

                "created_at": serialize_datetime(
                    attempt.created_at
                ),

                "scheduled_for": serialize_datetime(
                    attempt.scheduled_for
                ),

                "executed_at": serialize_datetime(
                    attempt.executed_at
                ),

                "completed_at": serialize_datetime(
                    attempt.completed_at
                ),

                "updated_at": serialize_datetime(
                    attempt.updated_at
                ),
            }
        )

    return {
        "count": len(results),
        "recovery_attempts": results,
    }


# =============================================================
# RECOVERY PIPELINE BREAKDOWN
# =============================================================


@router.get("/recovery-pipeline")
def get_recovery_pipeline(
    db: Session = Depends(get_db),
):
    """
    Return recovery attempts grouped by lifecycle state.

    Useful for pipeline/funnel visualizations in the frontend.
    """

    statuses = [
        RecoveryStatus.PENDING.value,
        RecoveryStatus.APPROVED.value,
        RecoveryStatus.SCHEDULED.value,
        RecoveryStatus.EXECUTING.value,
        RecoveryStatus.AWAITING_PAYMENT.value,
        RecoveryStatus.COMPLETED.value,
        RecoveryStatus.FAILED.value,
        RecoveryStatus.BLOCKED.value,
        RecoveryStatus.CANCELLED.value,
        RecoveryStatus.EXHAUSTED.value,
    ]

    attempts = db.query(RecoveryAttempt).all()

    pipeline = {}

    for lifecycle_status in statuses:

        matching_attempts = [
            attempt
            for attempt in attempts
            if attempt.status == lifecycle_status
        ]

        pipeline[lifecycle_status] = {
            "count": len(matching_attempts),
            "value": format_amount(
                sum(
                    (
                        attempt.payment.amount
                        if attempt.payment
                        else 0
                    )
                    for attempt in matching_attempts
                )
            ),
        }

    return {
        "pipeline": pipeline,
        "total_attempts": len(attempts),
    }