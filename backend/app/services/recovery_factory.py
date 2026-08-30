from sqlalchemy.orm import Session

from app.agents.recovery_agent import RecoveryAgent
from app.ml.model_store import load_recovery_model
from app.razorpay.recovery_gateway import RazorpayRecoveryGateway
from app.services.recovery_executor import RecoveryExecutor
from app.services.recovery_service import RecoveryService


def get_recovery_service(
    db: Session,
) -> RecoveryService:
    """
    Build the complete RecoveryService dependency graph.

    The recovery workflow supports two modes:

    1. ML-assisted mode
       A trained recovery model is available.

    2. Deterministic fallback mode
       No trained model artifact is available, so the RecoveryAgent
       uses the explainable recovery policy.
    """

    # ---------------------------------------------------------
    # LOAD ML MODEL IF AVAILABLE
    # ---------------------------------------------------------

    try:
        recovery_model = load_recovery_model()

    except FileNotFoundError:
        recovery_model = None

    # ---------------------------------------------------------
    # AI RECOVERY AGENT
    # ---------------------------------------------------------

    agent = RecoveryAgent(
        model=recovery_model,
    )

    # ---------------------------------------------------------
    # RAZORPAY RECOVERY GATEWAY
    # ---------------------------------------------------------

    gateway = RazorpayRecoveryGateway()

    # ---------------------------------------------------------
    # RECOVERY EXECUTOR
    # ---------------------------------------------------------

    executor = RecoveryExecutor(
        gateway=gateway,
    )

    # ---------------------------------------------------------
    # RECOVERY SERVICE
    # ---------------------------------------------------------

    return RecoveryService(
        db=db,
        agent=agent,
        executor=executor,
    )