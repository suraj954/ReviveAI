import { NavLink } from 'react-router-dom'

const icons = {
  dashboard: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  payments: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="2.5" y="5" width="19" height="14" rx="2" />
      <path d="M2.5 10h19" />
      <path d="M6 15h4" />
    </svg>
  ),
  pipeline: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="5" cy="12" r="2.3" />
      <circle cx="12" cy="6" r="2.3" />
      <circle cx="12" cy="18" r="2.3" />
      <circle cx="19" cy="12" r="2.3" />
      <path d="M7 11l3-3M7 13l3 3M14 6.5l3 4M14 17.5l3-4" />
    </svg>
  ),
  intelligence: (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 3a5 5 0 0 0-5 5c0 1.7.7 2.7 1.6 3.6.6.6 1 1.2 1.1 2.1v1.3h4.6v-1.3c.1-.9.5-1.5 1.1-2.1.9-.9 1.6-1.9 1.6-3.6a5 5 0 0 0-5-5z" />
      <path d="M9.7 20h4.6M10.5 22h3" />
    </svg>
  ),
}

const links = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/payments', label: 'Payments', icon: 'payments' },
  { to: '/recovery-pipeline', label: 'Recovery Pipeline', icon: 'pipeline' },
  { to: '/intelligence', label: 'AI Intelligence', icon: 'intelligence' },
]

export default function Sidebar({ open, onNavigate, backendOnline }) {
  return (
    <aside className={`sidebar${open ? ' open' : ''}`}>
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">R</div>
        <div className="sidebar-brand-text">
          <span className="sidebar-brand-name">ReviveAI</span>
          <span className="sidebar-brand-tag">Recovery Engine</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
            onClick={onNavigate}
          >
            {icons[link.icon]}
            {link.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-status-row">
          <span className={`status-dot${backendOnline === false ? ' offline' : ''}`} />
          {backendOnline === false ? 'Backend unreachable' : 'Backend connected'}
        </div>
      </div>
    </aside>
  )
}
