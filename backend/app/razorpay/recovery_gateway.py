from __future__ import annotations

from app.models.payment import Payment
from app.razorpay.orders import create_order


class RazorpayRecoveryGateway:
    """
    Razorpay-specific implementation of the recovery gateway.

    The recovery executor depends only on the RecoveryGateway
    protocol. This class contains the provider-specific logic.
    """

    def execute_retry(self, payment: Payment) -> str:
        """
        Create a new Razorpay recovery order for a failed payment.

        The original payment is never modified or charged directly.
        A new order represents the recovery attempt.
        """

        if payment.status != "failed":
            raise ValueError(
                "Recovery retry is only allowed for failed payments."
            )

        receipt = f"recovery_{payment.razorpay_order_id}"

        order = create_order(
            amount_in_rupees=payment.amount / 100,
            receipt=receipt,
        )

        order_id = order.get("id")

        if not order_id:
            raise RuntimeError(
                "Razorpay did not return a recovery order ID."
            )

        return str(order_id)

    def execute_wait_and_retry(self, payment: Payment) -> str:
        """
        Schedule a recovery attempt.

        Actual delayed-job infrastructure will be introduced later.
        For now, this returns a deterministic scheduling reference
        without initiating another payment immediately.
        """

        if payment.status != "created":
            raise ValueError(
                "Wait-and-retry is only allowed for created payments."
            )

        return f"scheduled_recovery_{payment.razorpay_order_id}"