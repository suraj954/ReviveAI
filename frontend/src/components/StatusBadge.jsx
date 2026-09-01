import { statusTone, formatStatusLabel } from '../utils'

// Reusable status badge. Pass either a raw backend `status` string (tone is
// inferred) or an explicit `tone` to override (e.g. for booleans like recovered).
export default function StatusBadge({ status, tone, label }) {
  const resolvedTone = tone || statusTone(status)
  const text = label || formatStatusLabel(status)
  return <span className={`badge badge-${resolvedTone}`}>{text}</span>
}
