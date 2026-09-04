import { useEffect, useRef } from 'react'
import StatusBadge from './StatusBadge'
import LoadingState from './LoadingState'
import ErrorState from './ErrorState'
import { formatINR, formatDate } from '../utils'

export default function PaymentIntelligenceModal({ paymentId, data, loading, error, onClose, onRetry }) {
  const overlayRef = useRef(null)

  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose()
  }

  return (
    <div className="modal-overlay" ref={overlayRef} onMouseDown={handleOverlayClick}>
      <div className="modal-panel" role="dialog" aria-modal="true" aria-label="Payment intelligence">
        <div className="modal-header">
          <div>
            <h2>Recovery Intelligence</h2>
            <p>Payment #{paymentId}</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <div className="modal-body">
          {loading ? <LoadingState label="Fetching explainable AI insights…" /> : null}
          {error ? <ErrorState message={error} onRetry={onRetry} /> : null}

          {!loading && !error && data ? <IntelligenceContent data={data} /> : null}
        </div>
      </div>
    </div>
  )
}

function IntelligenceContent({ data }) {
  const { payment, diagnosis, ai_decision, guardrails, money, recovery, attempts, audit_trail } = data

  const probabilityPct = ai_decision?.recovery_probability
    ? Math.round(
        ai_decision.recovery_probability <= 1
          ? ai_decision.recovery_probability * 100
          : ai_decision.recovery_probability
      )
    : null

  const timelineEvents = buildTimeline({ diagnosis, ai_decision, guardrails, recovery, attempts, audit_trail })

  return (
    <>
      <Section idx="1" title="Payment Information">
        <div className="kv-grid">
          <KV label="Payment ID" value={`#${payment?.payment_id ?? '—'}`} />
          <KV label="Status" value={<StatusBadge status={payment?.status} />} raw />
          <KV label="Order ID" value={payment?.razorpay_order_id || '—'} />
          <KV label="Provider Payment ID" value={payment?.razorpay_payment_id || '—'} />
          <KV label="Amount" value={formatINR(payment?.amount)} />
          <KV label="Currency" value={payment?.currency || 'INR'} />
          <KV label="Receipt" value={payment?.receipt || '—'} />
          <KV label="Created At" value={formatDate(payment?.created_at)} />
        </div>
      </Section>

      <Section idx="2" title="Failure Diagnosis">
        {diagnosis?.failure_code || diagnosis?.failure_reason ? (
          <div className="kv-grid">
            <KV label="Failure Code" value={diagnosis?.failure_code || '—'} />
            <KV label="Failure Reason" value={diagnosis?.failure_reason || '—'} />
          </div>
        ) : (
          <p style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>No failure detected for this payment.</p>
        )}
        {diagnosis?.failure_description ? (
          <div className="reasoning-box">{diagnosis.failure_description}</div>
        ) : null}
      </Section>

      <Section idx="3" title="AI Recovery Decision">
        {ai_decision ? (
          <>
            <div className="kv-grid">
              <KV label="Recovery Action" value={<span className="badge badge-info">{ai_decision.action}</span>} raw />
              <KV label="Recovery Probability" value={probabilityPct !== null ? `${probabilityPct}%` : '—'} />
            </div>
            {probabilityPct !== null ? (
              <div className="probability-bar-track">
                <div className="probability-bar-fill" style={{ width: `${probabilityPct}%` }} />
              </div>
            ) : null}
            {ai_decision.reason ? <div className="reasoning-box">{ai_decision.reason}</div> : null}
          </>
        ) : (
          <p style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
            No AI recovery decision has been recorded for this payment yet.
          </p>
        )}
      </Section>

      <Section idx="4" title="Guardrail Decision">
        {guardrails ? (
          <>
            <div className="kv-grid">
              <KV
                label="Outcome"
                value={
                  <StatusBadge
                    tone={guardrails.allowed ? 'success' : 'failure'}
                    label={guardrails.allowed ? 'Allowed' : 'Blocked'}
                  />
                }
                raw
              />
            </div>
            {guardrails.reason ? <div className="reasoning-box">{guardrails.reason}</div> : null}
          </>
        ) : (
          <p style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>No guardrail evaluation recorded.</p>
        )}
      </Section>

      <Section idx="5" title="Recovery Timeline">
        {timelineEvents.length > 0 ? (
          <div className="timeline">
            {timelineEvents.map((event, i) => (
              <div className="timeline-item" key={i}>
                <div className="timeline-marker" />
                <div className="timeline-content">
                  <h4>{event.title}</h4>
                  <p>{event.detail}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>No timeline events recorded yet.</p>
        )}
      </Section>

      <Section idx="6" title="Money Flow">
        <div className="money-flow">
          <div className="money-step">
            <div className="money-step-label">Original Amount</div>
            <div className="money-step-value">{formatINR(money?.original_amount)}</div>
          </div>
          <ArrowIcon />
          <div className="money-step">
            <div className="money-step-label">Revenue At Risk</div>
            <div className="money-step-value" style={{ color: 'var(--warning)' }}>
              {formatINR(money?.revenue_at_risk)}
            </div>
          </div>
          <ArrowIcon />
          <div className="money-step">
            <div className="money-step-label">Revenue Recovered</div>
            <div className="money-step-value" style={{ color: 'var(--success)' }}>
              {formatINR(money?.revenue_recovered)}
            </div>
          </div>
        </div>
        {!recovery?.recovered ? (
          <p style={{ color: 'var(--text-tertiary)', fontSize: 12, marginTop: 10 }}>
            Recovery is confirmed only after provider webhook verification — this payment is not yet
            marked recovered.
          </p>
        ) : null}
      </Section>
    </>
  )
}

function buildTimeline({ diagnosis, ai_decision, guardrails, recovery, attempts, audit_trail }) {
  const events = []
  if (diagnosis?.failure_reason) {
    events.push({ title: 'Failure diagnosed', detail: diagnosis.failure_reason })
  }
  if (ai_decision?.action) {
    events.push({
      title: `AI selected: ${ai_decision.action}`,
      detail: ai_decision.reason || 'Recovery strategy chosen by the decision engine.',
    })
  }
  if (guardrails) {
    events.push({
      title: guardrails.allowed ? 'Guardrails: allowed' : 'Guardrails: blocked',
      detail: guardrails.reason || 'Guardrail validation completed.',
    })
  }
  if (recovery?.latest_attempt_number ?? recovery?.latest_attempt_id) {
    events.push({
      title: `Recovery attempt #${recovery.latest_attempt_number ?? recovery.latest_attempt_id}`,
      detail: `Status: ${recovery.latest_status || 'unknown'}${
        recovery.provider_reference_id ? ` · Ref ${recovery.provider_reference_id}` : ''
      }`,
    })
  }
  if (Array.isArray(attempts)) {
    attempts.forEach((a) => {
      events.push({
        title: `Attempt #${a.attempt_number ?? a.id ?? ''} — ${a.status || 'unknown'}`,
        detail: a.error_message || (a.recovered ? 'Recovered successfully.' : 'In progress.'),
      })
    })
  }
  if (Array.isArray(audit_trail)) {
    audit_trail.forEach((entry) => {
      events.push({
        title: entry.event || entry.title || 'Audit event',
        detail: entry.description || entry.detail || formatDate(entry.timestamp),
      })
    })
  }
  if (recovery?.recovered) {
    events.push({ title: 'Verified recovery', detail: 'Confirmed via provider webhook verification.' })
  }
  return events
}

function Section({ idx, title, children }) {
  return (
    <div className="modal-section">
      <div className="modal-section-title">
        <span className="idx">{idx}</span>
        {title}
      </div>
      {children}
    </div>
  )
}

function KV({ label, value, raw }) {
  return (
    <div className="kv-item">
      <span className="kv-label">{label}</span>
      {raw ? value : <span className="kv-value">{value}</span>}
    </div>
  )
}

function ArrowIcon() {
  return (
    <svg
      className="money-arrow"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  )
}
