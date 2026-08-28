from datetime import datetime

from app.models.payment import Payment
from app.models.recovery_attempt import RecoveryAttempt
from app.services.recovery_service import RecoveryService


class FakeQuery:
    def __init__(self, attempts):
        self.attempts = attempts

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.attempts[-1] if self.attempts else None


class FakeSession:
    def __init__(self):
        self.attempts = []
        self.added = []

    def query(self, model):
        return FakeQuery(self.attempts)

    def add(self, obj):
        self.added.append(obj)
        self.attempts.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def make_payment(status: str, payment_id: int = 1) -> Payment:
    payment = Payment(
        razorpay_order_id=f"order_{payment_id}",
        amount=50000,
        currency="INR",
        status=status,
        receipt="test_receipt",
        created_at=datetime.utcnow(),
    )

    payment.id = payment_id

    return payment


def test_failed_payment_creates_retry_attempt() -> None:
    db = FakeSession()
    service = RecoveryService(db)

    attempt = service.evaluate_and_record(
        make_payment("failed"),
    )

    assert attempt.payment_id == 1
    assert attempt.action == "retry"
    assert attempt.attempt_number == 1
    assert attempt.status == "pending"

    assert len(db.added) == 1


def test_second_attempt_increments_attempt_number() -> None:
    db = FakeSession()

    existing = RecoveryAttempt(
        payment_id=1,
        action="retry",
        attempt_number=1,
    )

    db.attempts.append(existing)

    service = RecoveryService(db)

    attempt = service.evaluate_and_record(
        make_payment("failed"),
    )

    assert attempt.attempt_number == 2
    assert attempt.action == "retry"


def test_captured_payment_creates_no_action_attempt() -> None:
    db = FakeSession()
    service = RecoveryService(db)

    attempt = service.evaluate_and_record(
        make_payment("captured"),
    )

    assert attempt.payment_id == 1
    assert attempt.action == "no_action"
    assert attempt.attempt_number == 1