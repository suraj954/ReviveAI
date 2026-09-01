import { useEffect, useState, useCallback } from 'react'
import RecoveryPipeline from '../components/RecoveryPipeline'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { getRecoveryAttempts } from '../services/api'

export default function RecoveryPipelinePage({ onViewIntelligence, refreshToken }) {
  const [attempts, setAttempts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getRecoveryAttempts()
      setAttempts(res.recovery_attempts || [])
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
      <div className="section-heading">
        <h2>Recovery Pipeline</h2>
        <span>{attempts.length} attempts</span>
      </div>
      {loading ? (
        <LoadingState label="Loading recovery attempts…" />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <RecoveryPipeline attempts={attempts} onViewIntelligence={onViewIntelligence} />
      )}
    </>
  )
}
