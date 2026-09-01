// Shared formatting + status-mapping helpers used across pages/components.

export function formatINR(amount) {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(amount))
}

export function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Maps a raw backend status string to a badge tone.
export function statusTone(status) {
  if (!status) return 'neutral'
  const s = String(status).toLowerCase()
  if (['failed', 'blocked', 'error'].includes(s)) return 'failure'
  if (['paid', 'captured', 'recovered', 'success', 'successful', 'verified'].includes(s))
    return 'success'
  if (['awaiting_payment', 'scheduled', 'pending', 'active', 'processing'].includes(s))
    return 'warning'
  if (['cancelled', 'canceled'].includes(s)) return 'neutral'
  return 'info'
}

export function formatStatusLabel(status) {
  if (!status) return 'Unknown'
  return String(status).replace(/_/g, ' ')
}
