import StatusBadge from './StatusBadge'
import { formatINR, formatDate } from '../utils'

export default function RecoveryTable({ attempts, onViewIntelligence }) {
  if (!attempts || attempts.length === 0) {
    return (
      <div className="state-block">
        <h3>No recovery attempts yet</h3>
        <p>Recovery attempts will appear here as ReviveAI acts on failed payments.</p>
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Attempt ID</th>
            <th>Payment ID</th>
            <th>Amount</th>
            <th>Recovery Action</th>
            <th>Attempt #</th>
            <th>Status</th>
            <th>Recovered</th>
            <th>Provider Reference</th>
            <th>Created At</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {attempts.map((attempt) => (
            <tr key={attempt.id}>
              <td className="cell-mono">#{attempt.id}</td>
              <td className="cell-mono">#{attempt.payment_id}</td>
              <td className="cell-amount">{formatINR(attempt.amount)}</td>
              <td>
                <span className="badge badge-info">{attempt.action || '—'}</span>
              </td>
              <td className="cell-mono">{attempt.attempt_number ?? '—'}</td>
              <td>
                <StatusBadge status={attempt.status} />
              </td>
              <td>
                <StatusBadge
                  tone={attempt.recovered ? 'success' : 'neutral'}
                  label={attempt.recovered ? 'Recovered' : 'Not yet'}
                />
              </td>
              <td className="cell-mono">{attempt.provider_reference_id || '—'}</td>
              <td>{formatDate(attempt.created_at)}</td>
              <td>
                <button className="link-btn" onClick={() => onViewIntelligence(attempt.payment_id)}>
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
