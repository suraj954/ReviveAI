import { useCallback, useState } from 'react'
import {
  BrowserRouter,
  Routes,
  Route,
  useLocation,
} from 'react-router-dom'

import Sidebar from './components/Sidebar'
import Header from './components/Header'
import PaymentIntelligenceModal from './components/PaymentIntelligenceModal'

import Dashboard from './pages/Dashboard'
import Payments from './pages/Payments'
import RecoveryPipelinePage from './pages/RecoveryPipelinePage'
import Intelligence from './pages/Intelligence'

import {
  getPaymentInsights,
  ApiError,
} from './services/api'

const PAGE_META = {
  '/': {
    title: 'Dashboard',
    subtitle: 'Revenue recovery, at a glance',
  },
  '/payments': {
    title: 'Payments',
    subtitle: 'Every payment ReviveAI has seen',
  },
  '/recovery-pipeline': {
    title: 'Recovery Pipeline',
    subtitle: 'Every recovery attempt in flight or finished',
  },
  '/intelligence': {
    title: 'AI Intelligence',
    subtitle: 'How the recovery engine reasons',
  },
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}

function AppShell() {
  const location = useLocation()

  const [sidebarOpen, setSidebarOpen] = useState(false)

  const [refreshing, setRefreshing] = useState(false)
  const [refreshToken, setRefreshToken] = useState(0)

  const [backendOnline, setBackendOnline] = useState(null)

  const [modalPaymentId, setModalPaymentId] = useState(null)
  const [modalData, setModalData] = useState(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError] = useState(null)

  const meta =
    PAGE_META[location.pathname] ||
    PAGE_META['/']

  const handleRefresh = useCallback(() => {
    setRefreshing(true)

    setRefreshToken((token) => token + 1)

    setTimeout(() => {
      setRefreshing(false)
    }, 500)
  }, [])

  const openIntelligence =
    useCallback(async (paymentId) => {
      setModalPaymentId(paymentId)

      setModalData(null)
      setModalError(null)
      setModalLoading(true)

      try {
        const data =
          await getPaymentInsights(paymentId)

        setModalData(data)

        setBackendOnline(true)

      } catch (err) {
        setModalError(err.message)

        if (
          err instanceof ApiError &&
          err.status === 0
        ) {
          setBackendOnline(false)
        }

      } finally {
        setModalLoading(false)
      }
    }, [])

  const retryIntelligence =
    useCallback(() => {
      if (modalPaymentId) {
        openIntelligence(
          modalPaymentId
        )
      }
    }, [
      modalPaymentId,
      openIntelligence,
    ])

  const closeModal =
    useCallback(() => {
      setModalPaymentId(null)
      setModalData(null)
      setModalError(null)
    }, [])

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        onNavigate={() =>
          setSidebarOpen(false)
        }
        backendOnline={backendOnline}
      />

      <div className="app-main">
        <Header
          title={meta.title}
          subtitle={meta.subtitle}
          onRefresh={handleRefresh}
          refreshing={refreshing}
          onMenuToggle={() =>
            setSidebarOpen((open) => !open)
          }
        />

        <div className="app-content">
          <Routes>
            <Route
              path="/"
              element={
                <Dashboard
                  onViewIntelligence={
                    openIntelligence
                  }
                  refreshToken={
                    refreshToken
                  }
                />
              }
            />

            <Route
              path="/payments"
              element={
                <Payments
                  onViewIntelligence={
                    openIntelligence
                  }
                  refreshToken={
                    refreshToken
                  }
                />
              }
            />

            <Route
              path="/recovery-pipeline"
              element={
                <RecoveryPipelinePage
                  onViewIntelligence={
                    openIntelligence
                  }
                  refreshToken={
                    refreshToken
                  }
                />
              }
            />

            <Route
              path="/intelligence"
              element={
                <Intelligence
                  refreshToken={
                    refreshToken
                  }
                />
              }
            />
          </Routes>
        </div>
      </div>

      {modalPaymentId !== null && (
        <PaymentIntelligenceModal
          paymentId={modalPaymentId}
          data={modalData}
          loading={modalLoading}
          error={modalError}
          onClose={closeModal}
          onRetry={retryIntelligence}
        />
      )}
    </div>
  )
}