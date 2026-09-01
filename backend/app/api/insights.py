from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
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

    This endpoint is designed for the ReviveAI dashboard and exposes:

    - Payment status
    - Failure diagnosis
    - AI recovery decision
    - Recovery probability
    - Guardrail outcome
    - Recovery attempts
    - Recovery lifecycle
    - Immutable audit timeline
    """

    # ============================================================
    # FETCH PAYMENT
    # ============================================================

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

    # ============================================================
    # FETCH RECOVERY ATTEMPTS
    # ============================================================

    attempts = (
        db.query(RecoveryAttempt)
        .filter(
            RecoveryAttempt.payment_id == payment.id
        )
        .order_by(
            RecoveryAttempt.attempt_number.asc()
        )
        .all()
    )

    latest_attempt = (
        attempts[-1]
        if attempts
        else None
    )

    # ============================================================
    # FAILURE DIAGNOSIS
    # ============================================================

    diagnosis = {
        "failure_code": payment.failure_code,
        "failure_reason": payment.failure_reason,
        "failure_description": (
            payment.failure_description
        ),
    }

    # ============================================================
    # AI DECISION
    # ============================================================

    ai_decision = None

    if latest_attempt:

        ai_decision = {
            "action": latest_attempt.action,
            "recovery_probability": (
                latest_attempt.recovery_probability
            ),
            "reason": latest_attempt.decision_reason,
        }

    # ============================================================
    # GUARDRAIL RESULT
    # ============================================================

    guardrails = None

    if latest_attempt:

        guardrails = {
            "allowed": (
                latest_attempt.status
                != "blocked"
            ),
            "reason": (
                latest_attempt.guardrail_reason
            ),
        }

    # ============================================================
    # RECOVERY ATTEMPTS SUMMARY
    # ============================================================

    recovery_attempts = []

    for attempt in attempts:

        recovery_attempts.append(
            {
                "attempt_id": attempt.id,

                "attempt_number": (
                    attempt.attempt_number
                ),

                "action": attempt.action,

                "status": attempt.status,

                "executed": attempt.executed,

                "recovered": attempt.recovered,

                "recovery_probability": (
                    attempt.recovery_probability
                ),

                "provider_reference_id": (
                    attempt.provider_reference_id
                ),

                "recovery_payment_id": (
                    attempt.recovery_payment_id
                ),

                "recovered_amount": (
                    attempt.recovered_amount / 100
                    if attempt.recovered_amount
                    else None
                ),

                "error_message": (
                    attempt.error_message
                ),

                "scheduled_for": (
                    attempt.scheduled_for.isoformat()
                    if attempt.scheduled_for
                    else None
                ),

                "created_at": (
                    attempt.created_at.isoformat()
                ),

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
        )

    # ============================================================
    # AUDIT TRAIL
    # ============================================================

    audit_events = []

    if attempts:

        attempt_ids = [
            attempt.id
            for attempt in attempts
        ]

        events = (
            db.query(RecoveryEvent)
            .filter(
                RecoveryEvent.recovery_attempt_id.in_(
                    attempt_ids
                )
            )
            .order_by(
                RecoveryEvent.created_at.asc()
            )
            .all()
        )

        for event in events:

            audit_events.append(
                {
                    "event_id": event.id,

                    "attempt_id": (
                        event.recovery_attempt_id
                    ),

                    "event_type": event.event_type,

                    "description": (
                        event.description
                    ),

                    "metadata": (
                        event.metadata_json
                    ),

                    "created_at": (
                        event.created_at.isoformat()
                    ),
                }
            )

    # ============================================================
    # RECOVERY STATE
    # ============================================================

    recovery_summary = {

        "attempt_count": len(attempts),

        "latest_attempt_id": (
            latest_attempt.id
            if latest_attempt
            else None
        ),

        "latest_status": (
            latest_attempt.status
            if latest_attempt
            else None
        ),

        "provider_reference_id": (
            latest_attempt.provider_reference_id
            if latest_attempt
            else None
        ),

        "recovered": (
            latest_attempt.recovered
            if latest_attempt
            else False
        ),
    }

    # ============================================================
    # MONEY METRICS
    # ============================================================

    recovered_amount = 0

    for attempt in attempts:

        if (
            attempt.recovered is True
            and attempt.recovered_amount
        ):
            recovered_amount += (
                attempt.recovered_amount
            )

    payment_amount_rupees = (
        payment.amount / 100
    )

    recovered_amount_rupees = (
        recovered_amount / 100
    )

    revenue_at_risk = 0

    if payment.status == "failed":

        if recovered_amount == 0:
            revenue_at_risk = (
                payment_amount_rupees
            )

    # ============================================================
    # FINAL RESPONSE
    # ============================================================

    return {

        "payment": {
            "payment_id": payment.id,

            "razorpay_order_id": (
                payment.razorpay_order_id
            ),

            "razorpay_payment_id": (
                payment.razorpay_payment_id
            ),

            "amount": payment_amount_rupees,

            "currency": payment.currency,

            "status": payment.status,

            "receipt": payment.receipt,

            "created_at": (
                payment.created_at.isoformat()
            ),
        },

        "diagnosis": diagnosis,

        "ai_decision": ai_decision,

        "guardrails": guardrails,

        "money": {
            "original_amount": (
                payment_amount_rupees
            ),

            "revenue_at_risk": (
                revenue_at_risk
            ),

            "revenue_recovered": (
                recovered_amount_rupees
            ),
        },

        "recovery": recovery_summary,

        "attempts": recovery_attempts,

        "audit_trail": audit_events,
    }