import type { ReactNode } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { clearSession, getStoredUser } from '../lib/auth'
import { NetworkStatusBanner } from './NetworkStatusBanner'

function NavIcon({ path }: { path: 'home' | 'inspection' | 'review' | 'people' }) {
  const common = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8 }
  if (path === 'home') return <svg {...common} aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-5h5v5"/></svg>
  if (path === 'inspection') return <svg {...common} aria-hidden="true"><rect x="4" y="3.5" width="16" height="17" rx="2"/><path d="M8 8h8M8 12h5M8 16h7"/></svg>
  if (path === 'review') return <svg {...common} aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="m8 12 2.5 2.5L16 9"/></svg>
  return <svg {...common} aria-hidden="true"><path d="M16 20v-1.5a4.5 4.5 0 0 0-4.5-4.5h-3A4.5 4.5 0 0 0 4 18.5V20"/><circle cx="10" cy="7.5" r="3.5"/><path d="M17 11a3 3 0 1 0 0-6M18 14a4 4 0 0 1 3 3.9V20"/></svg>
}

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const user = getStoredUser()
  const canReview = user?.role === 'ADMIN' || user?.role === 'REVIEWER'
  const canManage = user?.role === 'ADMIN'
  const inspectorsActive = location.pathname.startsWith('/inspectors')

  function signOut() {
    clearSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-layout reference-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="sidebar" aria-label="SiteProof navigation">
        <div className="brand brand-gradient">
          <img className="brand-logo" src="/siteproof-icon.svg" alt="" aria-hidden="true" />
          <div>
            <strong>SiteProof</strong>
            <small>Field Verification</small>
          </div>
        </div>

        <nav aria-label="Primary">
          <NavLink to="/" end><NavIcon path="home"/><span>Overview</span></NavLink>
          <NavLink to="/inspections"><NavIcon path="inspection"/><span>Inspections</span></NavLink>
          {canReview ? <NavLink to="/review"><NavIcon path="review"/><span>Review</span></NavLink> : null}
          {canManage ? (
            <div className={`nav-group ${inspectorsActive ? 'open' : ''}`}>
              <NavLink to="/inspectors"><NavIcon path="people"/><span>Inspectors</span><span className="nav-chevron">⌄</span></NavLink>
              {inspectorsActive ? (
                <div className="nav-submenu" aria-label="Inspector management">
                  <a href="#all-inspectors">All Inspectors</a>
                  <a href="#add-inspector">Add Inspector</a>
                  <a href="#password-management">Change Passwords</a>
                </div>
              ) : null}
            </div>
          ) : null}
        </nav>

        <div className="sidebar-user">
          <div className="sidebar-avatar" aria-hidden="true">{(user?.fullName ?? 'S').slice(0, 1).toUpperCase()}</div>
          <div className="sidebar-user-copy">
            <strong>{user?.fullName ?? 'SiteProof user'}</strong>
            <small>{user?.role?.replace(/_/g, ' ') ?? ''}</small>
          </div>
          <button className="icon-action" type="button" onClick={signOut} aria-label="Sign out">›</button>
        </div>
      </aside>

      <div className="content-wrap">
        <header className="topbar topbar-gradient" aria-label="Application status">
          <button className="topbar-icon" type="button" aria-label="Navigation menu">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
          </button>
          <div className="topbar-actions">
            <span className="notification-dot" aria-hidden="true" />
            <button className="topbar-icon" type="button" aria-label="Notifications">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg>
            </button>
            <span className="topbar-avatar">{(user?.fullName ?? 'A').slice(0, 1).toUpperCase()}</span>
          </div>
        </header>
        <NetworkStatusBanner />
        <main className="content" id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  )
}
