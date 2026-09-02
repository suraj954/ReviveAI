const API_BASE_URL = "http://127.0.0.1:8000";

async function request(endpoint, options = {}) {
  const response = await fetch(
    `${API_BASE_URL}${endpoint}`,
    {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    }
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail
        ? typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail)
        : "Something went wrong while communicating with ReviveAI."
    );
  }

  return data;
}

/**
 * Create a merchant payment order.
 *
 * The backend:
 * 1. Creates a Razorpay order
 * 2. Creates a local Payment record
 * 3. Returns a customer-scoped recovery access token
 */
export async function createOrder({
  amount,
  currency = "INR",
  receipt = "revive_demo",
}) {
  return request("/api/orders", {
    method: "POST",
    body: JSON.stringify({
      amount,
      currency,
      receipt,
    }),
  });
}

/**
 * Get the customer-safe recovery status.
 *
 * This endpoint is read-only and does not expose internal
 * recovery intelligence.
 */
export async function getRecoveryStatus(token) {
  return request("/api/orders/recovery-status", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Fetch an already-created recovery checkout.
 *
 * This does NOT create another recovery attempt.
 */
export async function getRecoveryCheckout(attemptId) {
  return request(`/api/recovery-checkout/${attemptId}`, {
    method: "GET",
  });
}