const stages = [
  { key: 'failure', title: 'Payment Failure', sub: 'Provider reports a decline', cls: 'stage-failure', glyph: '01' },
  { key: 'diagnosis', title: 'AI Diagnosis', sub: 'Failure code is classified', cls: 'stage-ai', glyph: '02' },
  { key: 'decision', title: 'Recovery Decision', sub: 'Model scores an action', cls: 'stage-ai', glyph: '03' },
  { key: 'guardrail', title: 'Guardrails', sub: 'Decision is validated', cls: 'stage-guard', glyph: '04' },
  { key: 'execution', title: 'Recovery Execution', sub: 'Checkout order is created', cls: 'stage-ai', glyph: '05' },
  { key: 'verified', title: 'Verified Recovery', sub: 'Webhook confirms revenue', cls: 'stage-success', glyph: '06' },
]

// The signature visual: a horizontal rail tracing the payment's journey from
// failure to verified recovery, so a judge can read the whole product thesis
// in one glance without opening a single table.
export default function LifecycleRail() {
  return (
    <div className="panel lifecycle-rail">
      <div className="lifecycle-track">
        <div className="lifecycle-line" aria-hidden="true" />
        {stages.map((stage) => (
          <div className={`lifecycle-node ${stage.cls}`} key={stage.key}>
            <div className="lifecycle-dot">{stage.glyph}</div>
            <div className="lifecycle-node-title">{stage.title}</div>
            <div className="lifecycle-node-sub">{stage.sub}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
