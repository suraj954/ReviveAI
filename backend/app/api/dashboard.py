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


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
):
    """
    Return high-level dashboard metrics.
    """

    total_payments = db.query(Payment).count()

    failed_payments = (
        db.query(Payment)
        .filter(Payment.status == "failed")
        .count()
    )

    successful_payments = (
        db.query(Payment)
        .filter(
            Payment.status.in_(
                ["paid", "captured"]
            )
        )
        .count()
    )

    payments = db.query(Payment).all()

    total_payment_amount = sum(
        payment.amount for payment in payments
    )

    total_recovery_attempts = (
        db.query(RecoveryAttempt).count()
    )

    successful_recoveries = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.recovered.is_(True)
        )
        .count()
    )

    webhook_events = (
        db.query(WebhookEvent).count()
    )

    return {
        "total_payments": total_payments,
        "failed_payments": failed_payments,
        "successful_payments": successful_payments,

        # Database stores Razorpay amounts in paise.
        # Convert to rupees for dashboard display.
        "total_payment_amount": (
            total_payment_amount / 100
        ),

        "total_recovery_attempts": (
            total_recovery_attempts
        ),

        "successful_recoveries": (
            successful_recoveries
        ),

        "webhook_events": webhook_events,
    }


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