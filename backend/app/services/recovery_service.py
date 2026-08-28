from sqlalchemy.orm import Session

from app.agents.recovery_agent import RecoveryAgent
from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt


class RecoveryService:
    """
    Coordinates recovery decisions and persists recovery attempts.

    The agent is responsible for deciding the action.
    The service is responsible for persistence.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.agent = RecoveryAgent()

    def evaluate_and_record(
        self,
        payment: Payment,
    ) -> RecoveryAttempt:
        """
        Evaluate a payment and persist the resulting recovery attempt.
        """

        decision = self.agent.evaluate(payment)

        attempt = RecoveryAttempt(
            payment_id=payment.id,
            action=decision.action,
            attempt_number=self._next_attempt_number(payment.id),
        )

        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)

        return attempt

    def _next_attempt_number(self, payment_id: int) -> int:
        """
        Return the next recovery attempt number for a payment.
        """

        latest_attempt = (
            self.db.query(RecoveryAttempt)
            .filter(
                RecoveryAttempt.payment_id == payment_id,
            )
            .order_by(RecoveryAttempt.attempt_number.desc())
            .first()
        )

        if latest_attempt is None:
            return 1

        return latest_attempt.attempt_number + 1