from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import RecoveryStatus
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.models.recovery_event import RecoveryEvent


router = APIRouter(
    prefix="/api/insights",
    tags=["Recovery Insights"],
)


@router.get("/payment/{payment_id}")
def get_payment_insights(
    payment_id: int,
    db: Session = Depends(get_db),
):
    """
    Return a complete explainable recovery view for a payment.

    Recovery success is a payment-level outcome: once any attempt is
    verified as completed, the payment is treated as recovered even if
    historical or late-created attempts also exist.
    """

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    attempts = (
        db.query(RecoveryAttempt)
        .filter(RecoveryAttempt.payment_id == payment.id)
        .order_by(
            RecoveryAttempt.attempt_number.asc(),
            RecoveryAttempt.id.asc(),
        )
        .all()
    )

    latest_attempt = attempts[-1] if attempts else None

    successful_attempts = [
        attempt
        for attempt in attempts
        if (
            attempt.status == RecoveryStatus.COMPLETED.value
            or attempt.recovered is True
        )
    ]

    # A successful recovery is authoritative for the whole payment.
    recovered = bool(successful_attempts)
    successful_attempt = successful_attempts[-1] if successful_attempts else None

    # For current state display, prefer the verified successful attempt
    # after recovery. Before recovery, show the latest attempt.
    state_attempt = successful_attempt if recovered else latest_attempt

    diagnosis = {
        "failure_code": payment.failure_code,
        "failure_reason": payment.failure_reason,
        "failure_description": payment.failure_description,
    }

    ai_decision = None
    if latest_attempt:
        ai_decision = {
            "action": latest_attempt.action,
            "recovery_probability": latest_attempt.recovery_probability,
            "reason": latest_attempt.decision_reason,
        }

    guardrails = None
    if latest_attempt:
        guardrails = {
            "allowed": latest_attempt.status != RecoveryStatus.BLOCKED.value,
            "reason": latest_attempt.guardrail_reason,
        }

    recovery_attempts = [
        {
            "attempt_id": attempt.id,
            "attempt_number": attempt.attempt_number,
            "action": attempt.action,
            "status": attempt.status,
            "executed": attempt.executed,
            "recovered": attempt.recovered,
            "recovery_probability": attempt.recovery_probability,
            "provider_reference_id": attempt.provider_reference_id,
            "recovery_payment_id": attempt.recovery_payment_id,
            "recovered_amount": (
                attempt.recovered_amount / 100
                if attempt.recovered_amount is not None
                else None
            ),
            "error_message": attempt.error_message,
            "scheduled_for": (
                attempt.scheduled_for.isoformat()
                if attempt.scheduled_for
                else None
            ),
            "created_at": attempt.created_at.isoformat(),
            "executed_at": (
                attempt.executed_at.isoformat()
                if attempt.executed_at
                else None
            ),
            "completed_at": (
                attempt.completed_at.isoformat()
                if attempt.completed_at
                else None
            ),
        }
        for attempt in attempts
    ]

    audit_events = []

    if attempts:
        attempt_ids = [attempt.id for attempt in attempts]

        events = (
            db.query(RecoveryEvent)
            .filter(
                RecoveryEvent.recovery_attempt_id.in_(attempt_ids)
            )
            .order_by(
                RecoveryEvent.created_at.asc(),
                RecoveryEvent.id.asc(),
            )
            .all()
        )

        audit_events = [
            {
                "event_id": event.id,
                "attempt_id": event.recovery_attempt_id,
                "event_type": event.event_type,
                "description": event.description,
                "metadata": event.metadata_json,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]

    recovery_summary = {
        "attempt_count": len(attempts),
        "latest_attempt_id": (
            state_attempt.id if state_attempt else None
        ),
        "latest_attempt_number": (
            state_attempt.attempt_number
            if state_attempt
            else None
        ),
        "latest_status": (
            RecoveryStatus.COMPLETED.value
            if recovered
            else (state_attempt.status if state_attempt else None)
        ),
        "provider_reference_id": (
            state_attempt.provider_reference_id
            if state_attempt
            else None
        ),
        "recovered": recovered,
    }

    # Count recovered value once per original payment. A payment can
    # never contribute recovered revenue multiple times because of
    # duplicate/late provider events.
    if recovered:
        recovered_amount = (
            successful_attempt.recovered_amount
            if successful_attempt
            and successful_attempt.recovered_amount is not None
            else payment.amount
        )
    else:
        recovered_amount = 0

    payment_amount_rupees = payment.amount / 100
    recovered_amount_rupees = recovered_amount / 100

    revenue_at_risk = (
        0
        if recovered
        else payment_amount_rupees
        if payment.status == "failed"
        else 0
    )

    return {
        "payment": {
            "payment_id": payment.id,
            "razorpay_order_id": payment.razorpay_order_id,
            "razorpay_payment_id": payment.razorpay_payment_id,
            "amount": payment_amount_rupees,
            "currency": payment.currency,
            "status": payment.status,
            "receipt": payment.receipt,
            "created_at": payment.created_at.isoformat(),
        },
        "diagnosis": diagnosis,
        "ai_decision": ai_decision,
        "guardrails": guardrails,
        "money": {
            "original_amount": payment_amount_rupees,
            "revenue_at_risk": revenue_at_risk,
            "revenue_recovered": recovered_amount_rupees,
        },
        "recovery": recovery_summary,
        "attempts": recovery_attempts,
        "audit_trail": audit_events,
    }
