export default function Header({
  title,
  subtitle,
  onRefresh,
  refreshing,
  onMenuToggle,
}) {
  return (
    <header className="header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          className="menu-toggle"
          onClick={onMenuToggle}
          aria-label="Toggle navigation"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>

        <div className="header-title-group">
          <h1>{title}</h1>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>

      <div className="header-actions">
        <button
          className={`btn${refreshing ? ' is-loading' : ''}`}
          onClick={onRefresh}
          disabled={refreshing}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 12a9 9 0 1 1-2.6-6.4" />
            <path d="M21 3v6h-6" />
          </svg>

          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
    </header>
  )
}