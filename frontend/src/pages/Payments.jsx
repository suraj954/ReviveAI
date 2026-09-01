import { useEffect, useState, useCallback } from 'react'
import PaymentsTable from '../components/PaymentsTable'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { getPayments } from '../services/api'

export default function Payments({ onViewIntelligence, refreshToken }) {
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getPayments()
      setPayments(res.payments || [])
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
        <h2>All Payments</h2>
        <span>{payments.length} total</span>
      </div>
      <div className="panel">
        {loading ? (
          <LoadingState label="Loading payments…" />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <PaymentsTable payments={payments} onViewIntelligence={onViewIntelligence} variant="full" />
        )}
      </div>
    </>
  )
}
