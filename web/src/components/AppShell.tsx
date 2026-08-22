import { useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { getSummary, type DashboardSummary } from '../lib/api'
import { clearSession, getStoredUser } from '../lib/auth'
import { NetworkStatusBanner } from './NetworkStatusBanner'

type ShellSummary = DashboardSummary & { reviewRequired?: number; flagged?: number }

type NavIconName = 'home' | 'inspection' | 'review' | 'people'

function NavIcon({ name }: { name: NavIconName }) {
  const common = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  if (name === 'home') return <svg {...common} aria-hidden="true"><path d="M3.5 11.5 12 4.5l8.5 7"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-5h5v5"/></svg>
  if (name === 'inspection') return <svg {...common} aria-hidden="true"><rect x="4" y="3.5" width="16" height="17" rx="2.5"/><path d="M8 8h8M8 12h5M8 16h7"/></svg>
  if (name === 'review') return <svg {...common} aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="m8 12 2.5 2.5L16 9"/></svg>
  return <svg {...common} aria-hidden="true"><path d="M15.5 20v-1.4A4.6 4.6 0 0 0 10.9 14H8.6A4.6 4.6 0 0 0 4 18.6V20"/><circle cx="9.8" cy="7.5" r="3.5"/><path d="M16.8 11a3 3 0 1 0 0-6M17.5 14.3A4 4 0 0 1 21 18.2V20"/></svg>
}

function pageMeta(pathname: string) {
  if (pathname.startsWith('/inspectors')) return { title: 'Inspectors', subtitle: 'Access and field team management' }
  if (pathname.startsWith('/review')) return { title: 'Review', subtitle: 'Verification decisions and evidence' }
  if (pathname.startsWith('/receipts')) return { title: 'Receipt', subtitle: 'Signed verification record' }
  if (pathname.startsWith('/inspections/new')) return { title: 'New inspection', subtitle: 'Create field work' }
  if (pathname.includes('/edit')) return { title: 'Edit inspection', subtitle: 'Update field work' }
  if (pathname.startsWith('/inspections/')) return { title: 'Inspection', subtitle: 'Assignment and verification record' }
  if (pathname.startsWith('/inspections')) return { title: 'Inspections', subtitle: 'Field work and status' }
  return { title: 'Overview', subtitle: 'Field verification operations' }
}

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const user = getStoredUser()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const summary = useQuery({ queryKey: ['shell-summary'], queryFn: getSummary, staleTime: 30_000 })
  const shellSummary = summary.data as ShellSummary | undefined
  const canReview = user?.role === 'ADMIN' || user?.role === 'REVIEWER'
  const canManage = user?.role === 'ADMIN'
  const meta = useMemo(() => pageMeta(location.pathname), [location.pathname])
  const notices = [
    shellSummary?.overdue ? `${shellSummary.overdue} overdue inspection${shellSummary.overdue === 1 ? '' : 's'}` : null,
    shellSummary?.reviewRequired ? `${shellSummary.reviewRequired} result${shellSummary.reviewRequired === 1 ? '' : 's'} need review` : null,
    shellSummary?.flagged ? `${shellSummary.flagged} flagged verification${shellSummary.flagged === 1 ? '' : 's'}` : null,
  ].filter(Boolean) as string[]

  function closeMenus() {
    setNotificationsOpen(false)
    setAccountOpen(false)
    setMobileNavOpen(false)
  }

  function signOut() {
    clearSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className={`app-layout ${mobileNavOpen ? 'nav-open' : ''}`}>
      <a className="skip-link" href="#main-content">Skip to content</a>

      <aside className="sidebar" aria-label="SiteProof navigation">
        <div className="brand">
          <img className="brand-logo" src="/siteproof-icon.svg" alt="" aria-hidden="true" />
          <div><strong>SiteProof</strong><small>Field verification</small></div>
        </div>

        <nav aria-label="Primary" onClick={closeMenus}>
          <NavLink to="/" end><NavIcon name="home"/><span>Overview</span></NavLink>
          <NavLink to="/inspections"><NavIcon name="inspection"/><span>Inspections</span></NavLink>
          {canReview ? <NavLink to="/review"><NavIcon name="review"/><span>Review</span></NavLink> : null}
          {canManage ? <NavLink to="/inspectors"><NavIcon name="people"/><span>Inspectors</span></NavLink> : null}
        </nav>

        <button className="sidebar-user" type="button" onClick={() => { setAccountOpen(!accountOpen); setNotificationsOpen(false) }} aria-expanded={accountOpen}>
          <span className="sidebar-avatar" aria-hidden="true">{(user?.fullName ?? 'S').slice(0, 1).toUpperCase()}</span>
          <span className="sidebar-user-copy"><strong>{user?.fullName ?? 'SiteProof user'}</strong><small>{user?.email ?? ''}</small></span>
          <span className="icon-action" aria-hidden="true">›</span>
        </button>
      </aside>

      <div className="content-wrap">
        <header className="topbar" aria-label="Application controls">
          <button className="topbar-icon mobile-menu-button" type="button" aria-label={mobileNavOpen ? 'Close navigation' : 'Open navigation'} onClick={() => setMobileNavOpen(!mobileNavOpen)}>
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
          </button>

          <div className="topbar-title"><strong>{meta.title}</strong><span>{meta.subtitle}</span></div>

          <div className="topbar-actions">
            <div className="popover-anchor">
              <button className="topbar-icon" type="button" aria-label={`Notifications${notices.length ? `, ${notices.length} unread` : ''}`} aria-expanded={notificationsOpen} onClick={() => { setNotificationsOpen(!notificationsOpen); setAccountOpen(false) }}>
                <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg>
                {notices.length ? <span className="notification-count">{notices.length}</span> : null}
              </button>
              {notificationsOpen ? (
                <div className="app-popover notification-popover" role="dialog" aria-label="Notifications">
                  <div className="popover-title"><strong>Attention</strong><small>Items that may need action</small></div>
                  {summary.isLoading ? <div className="async-state">Checking status…</div> : notices.length ? notices.map((notice) => (
                    <button key={notice} type="button" className="notification-item" onClick={() => { closeMenus(); navigate(notice.includes('review') || notice.includes('flagged') ? '/review' : '/inspections') }}>
                      <span className="notification-pulse"/><span>{notice}</span><span aria-hidden="true">›</span>
                    </button>
                  )) : <div className="popover-empty"><strong>Nothing urgent</strong><span>No items currently need attention.</span></div>}
                </div>
              ) : null}
            </div>

            <div className="popover-anchor">
              <button className="topbar-avatar" type="button" aria-label="Account" aria-expanded={accountOpen} onClick={() => { setAccountOpen(!accountOpen); setNotificationsOpen(false) }}>{(user?.fullName ?? 'A').slice(0, 1).toUpperCase()}</button>
              {accountOpen ? (
                <div className="app-popover account-popover" role="dialog" aria-label="Account">
                  <div className="account-card"><span className="account-avatar-large">{(user?.fullName ?? 'A').slice(0, 1).toUpperCase()}</span><div><strong>{user?.fullName ?? 'SiteProof user'}</strong><span>{user?.email ?? ''}</span><small>{user?.role?.replace(/_/g, ' ')}</small></div></div>
                  {canManage ? <button type="button" onClick={() => { closeMenus(); navigate('/inspectors') }}>Manage inspectors</button> : null}
                  <button type="button" onClick={() => { closeMenus(); navigate('/') }}>Overview</button>
                  <button type="button" className="signout-row" onClick={signOut}>Sign out</button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <NetworkStatusBanner />
        <main className="content" id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  )
}
