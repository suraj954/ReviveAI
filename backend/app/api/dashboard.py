from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.models.webhook_event import WebhookEvent


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
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

    All monetary values are stored internally in paise and converted
    to rupees before being returned to the dashboard.

    Core metrics are designed around the AI Revenue Recovery lifecycle:

        Payment Failure
            ->
        Revenue At Risk
            ->
        Recovery Attempt
            ->
        Recovery Execution
            ->
        Verified Recovery
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
        if payment.status in ["paid", "captured"]
    ]

    total_payment_amount = sum(
        payment.amount
        for payment in payments
    )

    revenue_at_risk = sum(
        payment.amount
        for payment in failed_payments
    )

    # ---------------------------------------------------------
    # RECOVERY ATTEMPT METRICS
    # ---------------------------------------------------------

    attempts = (
        db.query(RecoveryAttempt)
        .order_by(
            RecoveryAttempt.created_at.desc()
        )
        .all()
    )

    total_recovery_attempts = len(attempts)

    successful_attempts = [
        attempt
        for attempt in attempts
        if attempt.recovered is True
    ]

    active_attempts = [
        attempt
        for attempt in attempts
        if attempt.status in [
            "pending",
            "executed",
            "scheduled",
            "awaiting_payment",
        ]
    ]

    blocked_attempts = [
        attempt
        for attempt in attempts
        if attempt.status == "blocked"
    ]

    cancelled_attempts = [
        attempt
        for attempt in attempts
        if attempt.status == "cancelled"
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
        payment.amount
        for payment in payments
        if payment.id in active_payment_ids
    )

    # ---------------------------------------------------------
    # RECOVERY RATE
    # ---------------------------------------------------------

    # Revenue-weighted recovery rate.
    #
    # Example:
    # ₹10,000 entered recovery
    # ₹3,000 successfully recovered
    #
    # Recovery rate = 30%

    total_amount_entered_recovery = sum(
        payment.amount
        for payment in payments
        if payment.id in {
            attempt.payment_id
            for attempt in attempts
        }
    )

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
        db.query(WebhookEvent).count()
    )

    # ---------------------------------------------------------
    # RETURN DASHBOARD DATA
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

        "total_payment_amount": round(
            total_payment_amount / 100,
            2,
        ),

        # =====================================================
        # REVENUE RECOVERY METRICS
        # =====================================================

        "revenue_at_risk": round(
            revenue_at_risk / 100,
            2,
        ),

        "revenue_recovered": round(
            revenue_recovered / 100,
            2,
        ),

        "active_recovery_value": round(
            active_recovery_value / 100,
            2,
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

        "successful_recoveries": len(
            successful_attempts
        ),

        "blocked_recoveries": len(
            blocked_attempts
        ),

        "cancelled_recoveries": len(
            cancelled_attempts
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
    Return payments with their latest recovery attempt.
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
            db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id
                == payment.id
            )
            .order_by(
                RecoveryAttempt.attempt_number.desc()
            )
            .first()
        )

        recovery = None

        if latest_attempt:
            recovery = {
                "attempt_id": latest_attempt.id,

                "attempt_number": (
                    latest_attempt.attempt_number
                ),

                "action": latest_attempt.action,

                "status": latest_attempt.status,

                "recovered": latest_attempt.recovered,

                "provider_reference_id": (
                    latest_attempt.provider_reference_id
                ),

                "error_message": (
                    latest_attempt.error_message
                ),
            }

        results.append(
            {
                "id": payment.id,

                "order_id": (
                    payment.razorpay_order_id
                ),

                "payment_id": (
                    payment.razorpay_payment_id
                ),

                # Convert paise to rupees.
                "amount": payment.amount / 100,

                "currency": payment.currency,

                "status": payment.status,

                "receipt": payment.receipt,

                "created_at": (
                    payment.created_at.isoformat()
                ),

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
    Return all recovery attempts with associated payment data.
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
                "id": attempt.id,

                "payment_id": payment.id,

                "razorpay_order_id": (
                    payment.razorpay_order_id
                ),

                # Convert paise to rupees.
                "amount": payment.amount / 100,

                "payment_status": payment.status,

                "action": attempt.action,

                "attempt_number": (
                    attempt.attempt_number
                ),

                "status": attempt.status,

                "recovered": attempt.recovered,

                "provider_reference_id": (
                    attempt.provider_reference_id
                ),

                "error_message": (
                    attempt.error_message
                ),

                "created_at": (
                    attempt.created_at.isoformat()
                ),

                "completed_at": (
                    attempt.completed_at.isoformat()
                    if attempt.completed_at
                    else None
                ),
            }
        )

    return {
        "count": len(results),
        "recovery_attempts": results,
    }