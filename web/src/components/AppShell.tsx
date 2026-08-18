import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { clearSession, getStoredUser } from '../lib/auth'

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const user = getStoredUser()

  function signOut() {
    clearSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">SP</span>
          <div><strong>SiteProof</strong><small>Field verification</small></div>
        </div>
        <nav>
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/inspections">Inspections</NavLink>
        </nav>
        <div className="sidebar-user">
          <div><strong>{user?.fullName ?? 'SiteProof user'}</strong><small>{user?.role ?? ''}</small></div>
          <button className="button ghost" onClick={signOut}>Sign out</button>
        </div>
      </aside>
      <div className="content-wrap">
        <header className="topbar">
          <div><span className="eyebrow">SITEPROOF CONTROL DESK</span></div>
          <span className="secure-chip">Organization isolated</span>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}
