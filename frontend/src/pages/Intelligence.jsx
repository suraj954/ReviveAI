import { useEffect, useState, useCallback } from 'react'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import LifecycleRail from '../components/LifecycleRail'
import { getDashboardSummary } from '../services/api'
import { formatINR } from '../utils'

const concepts = [
  {
    num: '01',
    title: 'Failure Diagnosis',
    body: 'Every declined payment is classified by failure code and reason — insufficient funds, expired card, issuer decline — before any recovery is attempted.',
  },
  {
    num: '02',
    title: 'AI Decision Engine',
    body: 'A model reviews the diagnosis and payment context to choose a recovery action, rather than applying the same retry logic to every failure.',
  },
  {
    num: '03',
    title: 'Recovery Probability',
    body: "Each decision carries a probability score, so the system — and the operator — can see how confident the model is before acting.",
  },
  {
    num: '04',
    title: 'Guardrail Validation',
    body: 'Before execution, every AI decision passes through guardrails that can allow or block it, with a stated reason either way.',
  },
  {
    num: '05',
    title: 'Recovery Strategy',
    body: 'Allowed decisions become a concrete strategy — retry, reschedule, or hand off to a recovery checkout — matched to the failure type.',
  },
  {
    num: '06',
    title: 'Recovery Execution',
    body: 'The chosen strategy is executed through the provider, creating a real checkout order for the customer to complete.',
  },
  {
    num: '07',
    title: 'Webhook Verification',
    body: 'Recovery is only ever marked successful once the provider sends a verified webhook — a checkout being opened is never treated as revenue recovered.',
  },
]

export default function Intelligence({ refreshToken }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getDashboardSummary()
      setSummary(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load, refreshToken])

  return (
    <>
      <div className="hero-band">
        <div className="hero-eyebrow">Explainable Recovery Intelligence</div>
        <h1>How ReviveAI decides what to do with a failed payment.</h1>
        <p>
          Every recovery ReviveAI attempts can be traced back through diagnosis, decision, and
          guardrail checks — nothing is a black box, and nothing counts as recovered until a
          webhook proves it.
        </p>
      </div>

      <LifecycleRail />

      <div className="section-heading">
        <h2>Live Signals</h2>
        <span>From /api/dashboard/summary</span>
      </div>

      {loading ? (
        <LoadingState label="Reading live signals…" />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <div className="signal-row">
          <SignalChip label="Failed Payments" value={summary?.failed_payments ?? 0} />
          <SignalChip label="Active Recoveries" value={summary?.active_recoveries ?? 0} />
          <SignalChip label="Revenue At Risk" value={formatINR(summary?.revenue_at_risk)} />
          <SignalChip label="Revenue Recovered" value={formatINR(summary?.revenue_recovered)} />
          <SignalChip label="Recovery Rate" value={`${summary?.recovery_rate ?? 0}%`} />
          <SignalChip label="Webhook Events" value={summary?.webhook_events ?? 0} />
        </div>
      )}

      <div className="section-heading">
        <h2>How the system reasons</h2>
        <span>Seven stages of the decision engine</span>
      </div>
      <div className="intel-grid">
        {concepts.map((c) => (
          <div className="intel-card" key={c.num}>
            <div className="intel-card-head">
              <span className="intel-card-num">{c.num}</span>
              <h3>{c.title}</h3>
            </div>
            <p>{c.body}</p>
          </div>
        ))}
      </div>
    </>
  )
}

function SignalChip({ label, value }) {
  return (
    <div className="signal-chip">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  )
}
