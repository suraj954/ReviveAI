from app.db.database import SessionLocal
from app.models.payment import Payment
from app.services.recovery_factory import get_recovery_service


def trigger_recovery_for_payment(
    payment_id: int,
) -> None:
    """
    Trigger the recovery workflow for an already persisted payment.

    This function owns an independent database session and transaction,
    keeping recovery orchestration separate from webhook ingestion.

    Flow:

        Persisted failed payment
                ↓
        Load payment in independent session
                ↓
        Build recovery service
                ↓
        AI decision + guardrails
                ↓
        Execute or schedule recovery
                ↓
        Commit recovery transaction
    """

    db = SessionLocal()

    try:
        payment = (
            db.query(Payment)
            .filter(
                Payment.id == payment_id,
            )
            .first()
        )

        if payment is None:
            raise ValueError(
                f"Payment with ID {payment_id} was not found."
            )

        recovery_service = get_recovery_service(db)
        

        recovery_service.evaluate_and_execute(
            payment,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()