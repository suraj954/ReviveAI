export default function MetricCard({ label, value, sub, accent = 'primary', small = false }) {
  return (
    <div className={`metric-card accent-${accent}`}>
      <div className="metric-label">{label}</div>
      <div className={`metric-value${small ? ' small' : ''}`}>{value}</div>
      {sub ? <div className="metric-sub">{sub}</div> : null}
    </div>
  )
}
