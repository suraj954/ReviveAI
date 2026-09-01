import { useEffect, useState, useCallback } from 'react'
import MetricCard from '../components/MetricCard'
import LifecycleRail from '../components/LifecycleRail'
import PaymentsTable from '../components/PaymentsTable'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { getDashboardSummary, getPayments } from '../services/api'
import { formatINR } from '../utils'

export default function Dashboard({ onViewIntelligence, refreshToken }) {
  const [summary, setSummary] = useState(null)
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryRes, paymentsRes] = await Promise.all([getDashboardSummary(), getPayments()])
      setSummary(summaryRes)
      setPayments(paymentsRes.payments || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load, refreshToken])

  const atRiskPayments = payments
    .filter((p) => String(p.status).toLowerCase() === 'failed')
    .slice(0, 8)

  if (loading) return <LoadingState label="Loading revenue recovery snapshot…" />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <>
      <div className="hero-band">
        <div className="hero-eyebrow">Revenue Recovery Command Center</div>
        <h1>Failed payments don't have to mean lost revenue.</h1>
        <p>
          ReviveAI diagnoses every failure, lets a decision engine choose a recovery strategy,
          checks it against guardrails, and only counts revenue as recovered once the provider's
          webhook confirms it.
        </p>
      </div>

      <div className="section-heading">
        <h2>Recovery Lifecycle</h2>
        <span>Live pipeline stages</span>
      </div>
      <LifecycleRail />

      <div className="section-heading">
        <h2>Revenue Metrics</h2>
        <span>From /api/dashboard/summary</span>
      </div>
      <div className="metric-grid">
        <MetricCard label="Revenue At Risk" value={formatINR(summary?.revenue_at_risk)} accent="warning" />
        <MetricCard label="Revenue Recovered" value={formatINR(summary?.revenue_recovered)} accent="success" />
        <MetricCard
          label="Active Recovery Value"
          value={formatINR(summary?.active_recovery_value)}
          accent="primary"
        />
        <MetricCard
          label="Recovery Rate"
          value={`${summary?.recovery_rate ?? 0}%`}
          accent="primary"
        />
      </div>

      <div className="metric-grid secondary">
        <MetricCard label="Total Payments" value={summary?.total_payments ?? 0} small />
        <MetricCard label="Failed Payments" value={summary?.failed_payments ?? 0} accent="failure" small />
        <MetricCard label="Successful Payments" value={summary?.successful_payments ?? 0} accent="success" small />
        <MetricCard label="Total Recovery Attempts" value={summary?.total_recovery_attempts ?? 0} small />
        <MetricCard label="Active Recoveries" value={summary?.active_recoveries ?? 0} accent="warning" small />
        <MetricCard label="Successful Recoveries" value={summary?.successful_recoveries ?? 0} accent="success" small />
        <MetricCard label="Blocked by Guardrails" value={summary?.blocked_recoveries ?? 0} accent="failure" small />
        <MetricCard label="Cancelled Recoveries" value={summary?.cancelled_recoveries ?? 0} small />
        <MetricCard label="Webhook Events Processed" value={summary?.webhook_events ?? 0} small />
      </div>

      <div className="section-heading">
        <h2>Recent Payments at Risk</h2>
        <span>{atRiskPayments.length} shown</span>
      </div>
      <div className="panel">
        <PaymentsTable
          payments={atRiskPayments}
          onViewIntelligence={onViewIntelligence}
          variant="compact"
        />
      </div>
    </>
  )
}
