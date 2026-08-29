from sqlalchemy.orm import Session

from app.razorpay.recovery_gateway import RazorpayRecoveryGateway
from app.services.recovery_executor import RecoveryExecutor
from app.services.recovery_service import RecoveryService


def get_recovery_service(
    db: Session,
) -> RecoveryService:
    """
    Build a fully configured RecoveryService.

    Keeps provider-specific dependency wiring outside API routes
    and event handlers.
    """

    gateway = RazorpayRecoveryGateway()

    executor = RecoveryExecutor(
        gateway=gateway,
    )

    return RecoveryService(
        db=db,
        executor=executor,
    )
