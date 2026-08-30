from __future__ import annotations

from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.razorpay.orders import create_order


class RazorpayRecoveryGateway:
    """
    Razorpay implementation of the recovery gateway.

    Creates a new Razorpay Order for payment recovery.

    Creating an order does NOT mean revenue has been recovered.
    Recovery is confirmed only after a verified successful
    payment webhook.
    """

    def create_recovery_checkout(
        self,
        payment: Payment,
    ) -> str:
        """
        Create a Razorpay recovery checkout/order.

        Returns the Razorpay recovery order ID.
        """

        return self.execute_retry(payment)

    def execute_retry(
        self,
        payment: Payment,
    ) -> str:
        """
        Execute an immediate recovery retry.

        A new Razorpay order is created for a failed payment.
        """

        if payment.status != PaymentStatus.FAILED.value:
            raise ValueError(
                "Recovery retry is only allowed for failed payments"
            )

        if payment.amount <= 0:
            raise ValueError(
                "Payment amount must be greater than zero"
            )

        # Payment amount is stored internally in paise.
        # The create_order helper expected by this recovery
        # gateway accepts the amount in rupees.
        amount_in_rupees = payment.amount / 100

        receipt = f"recovery_order_{payment.id}"

        order = create_order(
            amount_in_rupees=amount_in_rupees,
            receipt=receipt,
        )

        order_id = order.get("id")

        if not order_id:
            raise RuntimeError(
                "Razorpay did not return a recovery order ID"
            )

        return str(order_id)

    def execute_wait_and_retry(
        self,
        payment: Payment,
    ) -> str:
        """
        Return a scheduling reference for delayed recovery.

        No Razorpay order is created yet. Actual provider execution
        happens when the scheduler claims the attempt.
        """

        if payment.status != PaymentStatus.CREATED.value:
            raise ValueError(
                "Wait-and-retry is only allowed for created payments"
            )

        return f"scheduled_recovery_order_{payment.id}"