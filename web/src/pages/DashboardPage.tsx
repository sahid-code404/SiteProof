import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getBackendHealth, getSummary } from '../lib/api'

type LatestVerification = {
  inspectionId: string
  title: string
  locationName?: string | null
  inspectionStatus: string
  verificationStatus: string
  verdict?: string | null
  score?: number | null
  confidence?: number | null
  engineVersion: string
  calculatedAt?: string | null
  receiptNumber?: string | null
  receiptStatus?: string | null
}

type DashboardSummary = Awaited<ReturnType<typeof getSummary>> & {
  verified: number
  reviewRequired: number
  flagged: number
  inconclusive: number
  verificationProcessing: number
  verificationCompleted: number
  verificationRate: number
  latestVerifications: LatestVerification[]
}

function badgeClass(verdict?: string | null) {
  if (verdict === 'VERIFIED') return 'badge badge-ready'
  if (verdict === 'FLAGGED') return 'badge badge-critical'
  if (verdict === 'REVIEW_REQUIRED') return 'badge badge-high'
  return 'badge'
}

function percent(value?: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

export function DashboardPage() {
  const health = useQuery({ queryKey: ['backend-health'], queryFn: getBackendHealth, retry: 1 })
  const summary = useQuery({ queryKey: ['inspection-summary'], queryFn: getSummary })
  const data = summary.data as DashboardSummary | undefined
  const reviewQueue = (data?.reviewRequired ?? 0) + (data?.inconclusive ?? 0)
  const verificationRate = Math.round(data?.verificationRate ?? 0)

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Field verification</h1>
          <p>Only the information that needs a decision: current workload, verification results and exceptions.</p>
        </div>
        <div className={`status ${health.isSuccess ? 'online' : ''}`} role="status" aria-live="polite">
          <span className="dot" aria-hidden="true" />
          {health.isSuccess ? 'System online' : health.isError ? 'Backend unavailable' : 'Checking system'}
        </div>
      </section>

      {summary.isError ? (
        <div className="notice error" role="alert">
          <strong>Overview unavailable.</strong>
          <p>{summary.error.message}</p>
          <button className="button ghost" type="button" onClick={() => summary.refetch()}>Retry</button>
        </div>
      ) : null}

      <section className="metric-grid" aria-label="Key metrics" aria-busy={summary.isLoading}>
        <article className="metric-card"><span>Total inspections</span><strong>{summary.isLoading ? '…' : data?.total ?? 0}</strong></article>
        <article className="metric-card"><span>Verified</span><strong>{summary.isLoading ? '…' : data?.verified ?? 0}</strong></article>
        <article className="metric-card"><span>Needs review</span><strong>{summary.isLoading ? '…' : reviewQueue}</strong></article>
        <article className="metric-card"><span>Overdue</span><strong>{summary.isLoading ? '…' : data?.overdue ?? 0}</strong></article>
      </section>

      <section className="dashboard-grid dashboard-priority-grid">
        <article className="panel verification-overview-card">
          <div className="verification-rate-tile"><strong>{summary.isLoading ? '…' : `${verificationRate}%`}</strong><span>verified</span></div>
          <div className="verification-overview-copy">
            <p className="eyebrow">Verification</p>
            <h2>Current decision state</h2>
            <p>{summary.isLoading ? 'Loading verification state…' : `${data?.verificationCompleted ?? 0} inspections have a current result. ${data?.verificationProcessing ?? 0} are still processing.`}</p>
          </div>
          <div className="verification-overview-actions">
            <Link className="button primary" to="/review">Open review queue</Link>
            <Link className="button ghost" to="/inspections">All inspections</Link>
          </div>
        </article>

        <article className="panel">
          <p className="eyebrow">Exceptions</p>
          <h2>Needs attention</h2>
          <div className="attention-row"><span>Review required</span><strong>{data?.reviewRequired ?? 0}</strong></div>
          <div className="attention-row"><span>Flagged</span><strong>{data?.flagged ?? 0}</strong></div>
          <div className="attention-row"><span>Inconclusive</span><strong>{data?.inconclusive ?? 0}</strong></div>
          <div className="attention-row"><span>High priority</span><strong>{data?.highPriority ?? 0}</strong></div>
        </article>
      </section>

      <section className="panel" style={{ marginTop: 14 }}>
        <div className="split-heading">
          <div><p className="eyebrow">Recent</p><h2>Latest verification decisions</h2></div>
          <Link className="button ghost" to="/review">View all</Link>
        </div>
        {summary.isLoading ? <div className="async-state" role="status">Loading recent decisions…</div> : null}
        {!summary.isLoading && !data?.latestVerifications?.length ? <div className="empty-state"><h3>No completed results yet</h3><p>Verification decisions will appear here after evidence processing.</p></div> : null}
        {data?.latestVerifications?.length ? (
          <div className="recent-decision-list">
            {data.latestVerifications.slice(0, 6).map((item) => (
              <article className="recent-decision-card" key={item.inspectionId}>
                <div className="recent-decision-topline">
                  <div><Link className="table-link" to={`/inspections/${item.inspectionId}`}>{item.title}</Link><small>{item.locationName || 'Unnamed site'}</small></div>
                  <span className={badgeClass(item.verdict)}>{item.verdict?.replace(/_/g, ' ') ?? item.verificationStatus.replace(/_/g, ' ')}</span>
                </div>
                <div className="recent-decision-metrics">
                  <span><small>Score</small><strong>{typeof item.score === 'number' ? item.score.toFixed(2) : '—'}</strong></span>
                  <span><small>Confidence</small><strong>{percent(item.confidence)}</strong></span>
                  <span><small>Engine</small><strong>{item.engineVersion}</strong></span>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </>
  )
}
