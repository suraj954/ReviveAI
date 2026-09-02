import { useState } from "react";
import { createOrder } from "../services/api";
import { formatPrice } from "../data/products";

function CheckoutModal({ product, onClose, onPaymentComplete }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!product) {
    return null;
  }

  async function handlePayment() {
    try {
      setLoading(true);
      setError("");

      // ---------------------------------------------
      // 1. Create order through ReviveAI backend
      // ---------------------------------------------
      const order = await createOrder({
        amount: product.price,
        currency: "INR",
        receipt: `store_product_${product.id}_${Date.now()}`,
      });

      // ---------------------------------------------
      // 2. Ensure Razorpay Checkout SDK is available
      // ---------------------------------------------
      if (!window.Razorpay) {
        throw new Error(
          "Razorpay Checkout could not be loaded. Please refresh and try again."
        );
      }

      // ---------------------------------------------
      // 3. Configure Razorpay Checkout
      // ---------------------------------------------
      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: "Revive Store",
        description: product.name,
        order_id: order.order_id,

        handler: function (response) {
          onPaymentComplete({
            success: true,
            product,
            payment: response,
            recoveryToken: order.recovery_access_token,
          });

          onClose();
        },

        modal: {
          ondismiss: function () {
            setLoading(false);
          },
        },

        theme: {
          color: "#635bff",
        },
      };

      // ---------------------------------------------
      // 4. Open Razorpay Checkout
      // ---------------------------------------------
      const razorpay = new window.Razorpay(options);

      razorpay.on("payment.failed", function (response) {
        onPaymentComplete({
          success: false,
          product,
          payment: response.error,
          recoveryToken: order.recovery_access_token,
        });

        onClose();
      });

      razorpay.open();
    } catch (err) {
      console.error("Checkout error:", err);

      setError(
        err.message ||
          "Unable to start checkout. Please try again."
      );

      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="checkout-modal">
        <button
        className="modal-close"
        onClick={onClose}
        disabled={loading}
        aria-label="Close checkout"
        >
        X
        </button>

        <div className="checkout-product">
          <div className="checkout-icon">
            {product.icon}
          </div>

          <div>
            <p className="product-category">
              {product.category}
            </p>

            <h2>{product.name}</h2>

            <p className="checkout-price">
              {formatPrice(product.price)}
            </p>
          </div>
        </div>

        <div className="checkout-divider" />

        <div className="checkout-summary">
          <span>Total amount</span>
          <strong>{formatPrice(product.price)}</strong>
        </div>

        {error && (
          <div className="checkout-error">
            {error}
          </div>
        )}

        <button
          className="checkout-button"
          onClick={handlePayment}
          disabled={loading}
        >
          {loading
            ? "Preparing secure checkout..."
            : `Pay ${formatPrice(product.price)}`}
        </button>

        <p className="checkout-security">
          Secure checkout powered by Razorpay
        </p>
      </div>
    </div>
  );
}

export default CheckoutModal;