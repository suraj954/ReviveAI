from datetime import datetime, timezone

from app.agents.recovery_agent import RecoveryAgent
from app.models.payment import Payment


def make_payment(status: str) -> Payment:
    return Payment(
        razorpay_order_id=f"order_{status}",
        amount=50000,
        currency="INR",
        status=status,
        receipt="test_receipt",
        created_at=datetime.now(timezone.utc),
    )


def test_agent_recommends_retry_for_failed_payment() -> None:
    agent = RecoveryAgent()

    decision = agent.evaluate(make_payment("failed"))

    assert decision.action == "retry"
    assert "failed" in decision.reason.lower()


def test_agent_recommends_no_action_for_captured_payment() -> None:
    agent = RecoveryAgent()

    decision = agent.evaluate(make_payment("captured"))

    assert decision.action == "no_action"
    assert "captured" in decision.reason.lower()


def test_agent_recommends_wait_for_created_payment() -> None:
    agent = RecoveryAgent()

    decision = agent.evaluate(make_payment("created"))

    assert decision.action == "wait_and_retry"
    assert "created" in decision.reason.lower()