import StatusBadge from './StatusBadge'
import { formatINR, formatDate } from '../utils'

// Shared table for rendering a list of payments with recovery context.
// `variant="compact"` is used on the Dashboard's "at risk" preview;
// `variant="full"` renders the full Payments page with extra columns.
export default function PaymentsTable({ payments, onViewIntelligence, variant = 'full' }) {
  if (!payments || payments.length === 0) {
    return (
      <div className="state-block">
        <h3>No payments yet</h3>
        <p>Once payments start flowing through ReviveAI, they'll show up here.</p>
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Payment</th>
            {variant === 'full' ? <th>Order ID</th> : null}
            <th>Amount</th>
            {variant === 'full' ? <th>Currency</th> : null}
            <th>Status</th>
            {variant === 'full' ? <th>Created At</th> : null}
            <th>AI Recovery Action</th>
            <th>Recovery Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => (
            <tr key={payment.id}>
              <td className="cell-mono">#{payment.id}</td>
              {variant === 'full' ? (
                <td className="cell-mono">{payment.order_id || '—'}</td>
              ) : null}
              <td className="cell-amount">{formatINR(payment.amount)}</td>
              {variant === 'full' ? <td>{payment.currency || 'INR'}</td> : null}
              <td>
                <StatusBadge status={payment.status} />
              </td>
              {variant === 'full' ? <td>{formatDate(payment.created_at)}</td> : null}
              <td>
                {payment.recovery?.action ? (
                  <span className="badge badge-info">{payment.recovery.action}</span>
                ) : (
                  <span style={{ color: 'var(--text-tertiary)' }}>—</span>
                )}
              </td>
              <td>
                {payment.recovery ? (
                  <StatusBadge status={payment.recovery.status} />
                ) : (
                  <span style={{ color: 'var(--text-tertiary)' }}>—</span>
                )}
              </td>
              <td>
                <button className="link-btn" onClick={() => onViewIntelligence(payment.id)}>
                  View Intelligence
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
