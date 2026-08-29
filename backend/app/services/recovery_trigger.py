from app.db.database import SessionLocal
from app.models.payment import Payment
from app.services.recovery_factory import get_recovery_service


def trigger_recovery_for_payment(
    payment_id: int,
) -> None:
    """
    Trigger the recovery workflow for a persisted payment.

    This function creates its own database session so recovery
    orchestration remains independent from webhook ingestion.
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

    finally:
        db.close()