import RecoveryTable from './RecoveryTable'

// Wraps the recovery attempts table with a short framing strip so the
// Recovery Pipeline page reads as a stage of the lifecycle, not just a table.
export default function RecoveryPipeline({ attempts, onViewIntelligence }) {
  return (
    <div className="panel">
      <RecoveryTable attempts={attempts} onViewIntelligence={onViewIntelligence} />
    </div>
  )
}
