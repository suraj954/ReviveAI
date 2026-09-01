// ReviveAI API Service
// Centralized client for the FastAPI backend.

const BASE_URL = 'http://127.0.0.1:8000'

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  let response

  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
      ...options,
    })
  } catch (_) {
    throw new ApiError(
      `Could not reach ReviveAI backend at ${BASE_URL}. Is the FastAPI server running?`,
      0
    )
  }

  if (!response.ok) {
    let detail = ''

    try {
      const body = await response.json()
      detail = body?.detail || body?.message || ''
    } catch (_) {
      // Ignore JSON parsing failure.
    }

    throw new ApiError(
      detail || `Request to ${path} failed with status ${response.status}`,
      response.status
    )
  }

  return response.json()
}

export function getDashboardSummary() {
  return request('/api/dashboard/summary')
}

export function getPayments() {
  return request('/api/dashboard/payments')
}

export function getRecoveryAttempts() {
  return request('/api/dashboard/recovery-attempts')
}

export function getPaymentInsights(paymentId) {
  return request(`/api/insights/payment/${paymentId}`)
}

export function getRecoveryCheckout(attemptId) {
  return request(`/api/recovery-checkout/${attemptId}`)
}

export function createDemoOrder() {
  const receipt = `revive_demo_${Date.now()}`

  return request('/api/orders', {
    method: 'POST',
    body: JSON.stringify({
      amount: 500,
      currency: 'INR',
      receipt,
    }),
  })
}

export { ApiError, BASE_URL }