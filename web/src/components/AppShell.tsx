import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { clearSession, getStoredUser } from '../lib/auth'
import { NetworkStatusBanner } from './NetworkStatusBanner'

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const user = getStoredUser()
  const canReview = user?.role === 'ADMIN' || user?.role === 'REVIEWER'

  function signOut() {
    clearSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="sidebar" aria-label="SiteProof navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">SP</span>
          <div><strong>SiteProof</strong><small>Field verification</small></div>
        </div>
        <nav aria-label="Primary">
          <NavLink to="/" end>Overview</NavLink>
          {canReview ? <NavLink to="/review">Review</NavLink> : null}
          <NavLink to="/inspections">Inspections</NavLink>
        </nav>
        <div className="sidebar-user">
          <div><strong>{user?.fullName ?? 'SiteProof user'}</strong><small>{user?.role ?? ''}</small></div>
          <button className="button ghost" type="button" onClick={signOut}>Sign out</button>
        </div>
      </aside>
      <div className="content-wrap">
        <header className="topbar" aria-label="Application status">
          <div><span className="eyebrow">SITEPROOF CONTROL DESK</span></div>
          <span className="secure-chip" title="Data is scoped to the signed-in organization">Organization isolated</span>
        </header>
        <NetworkStatusBanner />
        <main className="content" id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  )
}
