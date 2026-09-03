import { useState } from "react";

import Navbar from "./components/Navbar";
import ProductCard from "./components/ProductCard";
import CheckoutModal from "./components/CheckoutModal";
import RecoveryStatus from "./components/RecoveryStatus";

import { products } from "./data/products";

import "./App.css";

function App() {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  const [paymentResult, setPaymentResult] = useState(null);

  const [recoveryCheckout, setRecoveryCheckout] =
    useState(null);

  function handleBuy(product) {
    // Reset previous payment/recovery state for a new purchase
    setSelectedProduct(product);
    setPaymentResult(null);
    setRecoveryCheckout(null);
    setCheckoutOpen(true);
  }

  function handleCloseCheckout() {
    setCheckoutOpen(false);
  }

  function handlePaymentComplete(result) {
    setPaymentResult(result);

    // Clear any previous recovery checkout
    if (result.success) {
      setRecoveryCheckout(null);
    }
  }

  function handleRecoveryAvailable(checkout) {
    setRecoveryCheckout(checkout);
  }

  function handleRecoveryPaymentSuccess(response) {
    console.log(
      "Recovery payment completed successfully:",
      response
    );

    // Remove recovery checkout state
    setRecoveryCheckout(null);

    // IMPORTANT:
    // Replace the original failed payment state with success.
    // This automatically removes the recovery UI.
    setPaymentResult((previousResult) => ({
      success: true,
      product: previousResult?.product,
      payment: response,
      recovered: true,
    }));
  }

  function openRecoveryCheckout() {
    if (!recoveryCheckout) {
      return;
    }

    if (!window.Razorpay) {
      console.error(
        "Razorpay Checkout SDK is not available."
      );
      return;
    }

    const options = {
      key: recoveryCheckout.key_id,
      amount: recoveryCheckout.amount,
      currency: recoveryCheckout.currency,

      name: "Revive Store",
      description: "Secure payment recovery",

      order_id: recoveryCheckout.order_id,

      handler: function (response) {
        handleRecoveryPaymentSuccess(response);
      },

      modal: {
        ondismiss: function () {
          console.log("Recovery checkout dismissed.");
        },
      },

      theme: {
        color: "#635bff",
      },
    };

    const razorpay = new window.Razorpay(options);

    razorpay.on("payment.failed", function (response) {
      console.error(
        "Recovery payment failed:",
        response.error
      );
    });

    razorpay.open();
  }

  return (
    <div className="app">
      <Navbar />

      <main>
        {/* ================================================= */}
        {/* HERO */}
        {/* ================================================= */}

        <section className="hero">
          <div className="hero-content">
            <div className="hero-badge">
              <span className="hero-badge-dot" />
              Intelligent commerce powered by ReviveAI
            </div>

            <h1>
              Shopping that doesn't
              <span> give up on you.</span>
            </h1>

            <p>
              Discover premium technology products with a
              smarter payment experience powered by an
              intelligent revenue recovery engine.
            </p>

            <a
              href="#products"
              className="hero-button"
            >
              Explore products
            </a>
          </div>

          <div className="hero-visual">
            <div className="hero-orbit orbit-one" />
            <div className="hero-orbit orbit-two" />

            <div className="hero-card">
              <div className="hero-card-icon">
                AI
              </div>

              <div>
                <span>Payment intelligence</span>
                <strong>Always monitoring</strong>
              </div>
            </div>
          </div>
        </section>

        {/* ================================================= */}
        {/* PRODUCTS */}
        {/* ================================================= */}

        <section
          id="products"
          className="products-section"
        >
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">
                CURATED COLLECTION
              </p>

              <h2>
                Designed for everyday excellence
              </h2>
            </div>

            <p>
              Premium products paired with a more resilient
              payment experience.
            </p>
          </div>

          <div className="products-grid">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onBuy={handleBuy}
              />
            ))}
          </div>
        </section>

        {/* ================================================= */}
        {/* PAYMENT RESULT */}
        {/* ================================================= */}

        {paymentResult && (
          <section className="payment-result-section">
            {paymentResult.success ? (
              <div className="payment-success">
                <span className="result-icon">
                  ✓
                </span>

                <div>
                  <p>
                    {paymentResult.recovered
                      ? "PAYMENT RECOVERED"
                      : "PAYMENT SUCCESSFUL"}
                  </p>

                  <h2>
                    {paymentResult.recovered
                      ? "Payment successfully recovered!"
                      : "Thank you for your purchase!"}
                  </h2>

                  <span>
                    {paymentResult.recovered
                      ? `ReviveAI successfully recovered your payment for ${paymentResult.product?.name}.`
                      : `Your payment for ${paymentResult.product?.name} was completed successfully.`}
                  </span>
                </div>
              </div>
            ) : (
              <div className="payment-failed">
                <span className="result-icon">
                  !
                </span>

                <div>
                  <p>PAYMENT INTERRUPTED</p>

                  <h2>
                    Don't worry — ReviveAI is on it.
                  </h2>

                  <span>
                    We're analyzing your payment and checking
                    whether a safe recovery option is available.
                  </span>
                </div>
              </div>
            )}
          </section>
        )}

        {/* ================================================= */}
        {/* REVIVEAI RECOVERY */}
        {/* Only visible while original payment remains failed */}
        {/* ================================================= */}

        {paymentResult &&
          !paymentResult.success &&
          paymentResult.recoveryToken && (
            <section className="recovery-section">
              <RecoveryStatus
                product={paymentResult.product}
                recoveryToken={
                  paymentResult.recoveryToken
                }
                onRecoveryAvailable={
                  handleRecoveryAvailable
                }
              />

              {recoveryCheckout && (
                <button
                  className="recovery-checkout-button"
                  onClick={openRecoveryCheckout}
                >
                  Retry payment securely
                </button>
              )}
            </section>
          )}

        {/* ================================================= */}
        {/* HOW IT WORKS */}
        {/* ================================================= */}

        <section
          id="how-it-works"
          className="how-it-works"
        >
          <div className="section-heading centered">
            <p className="section-eyebrow">
              HOW REVIVEAI WORKS
            </p>

            <h2>
              Revenue recovery without customer friction
            </h2>
          </div>

          <div className="steps-grid">
            <article>
              <span>01</span>

              <h3>Payment monitored</h3>

              <p>
                ReviveAI detects payment failures through
                verified provider events.
              </p>
            </article>

            <article>
              <span>02</span>

              <h3>AI evaluates recovery</h3>

              <p>
                Recovery probability, guardrails and policy
                determine the safest next action.
              </p>
            </article>

            <article>
              <span>03</span>

              <h3>Revenue gets another chance</h3>

              <p>
                Approved recovery workflows reconnect the
                customer with a safe payment path.
              </p>
            </article>
          </div>
        </section>
      </main>

      {/* ================================================= */}
      {/* CHECKOUT MODAL */}
      {/* ================================================= */}

      {checkoutOpen && (
        <CheckoutModal
          product={selectedProduct}
          onClose={handleCloseCheckout}
          onPaymentComplete={handlePaymentComplete}
        />
      )}
    </div>
  );
}

export default App;