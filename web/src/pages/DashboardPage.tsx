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

function verdictBadgeClass(verdict?: string | null) {
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
          <p className="eyebrow">Overview</p>
          <h1>Field verification</h1>
          <p>Results, review work and active inspections at a glance.</p>
        </div>
        <div className={`status ${health.isSuccess ? 'online' : ''}`} role="status" aria-live="polite">
          <span className="dot" aria-hidden="true" />
          {health.isSuccess ? 'Online' : health.isError ? 'Backend unavailable' : 'Checking connection'}
        </div>
      </section>

      {summary.isError ? (
        <div className="notice error" role="alert">
          <strong>Could not load the overview</strong>
          <p>{summary.error.message}</p>
          <button className="button ghost" type="button" onClick={() => summary.refetch()}>Try again</button>
        </div>
      ) : null}

      <section className="metric-grid" aria-label="Verification metrics" aria-busy={summary.isLoading}>
        <article className="metric-card"><span>Inspections</span><strong>{summary.isLoading ? '…' : data?.total ?? 0}</strong></article>
        <article className="metric-card"><span>Verified</span><strong>{summary.isLoading ? '…' : data?.verified ?? 0}</strong></article>
        <article className="metric-card"><span>Needs review</span><strong>{summary.isLoading ? '…' : reviewQueue}</strong></article>
        <article className="metric-card"><span>Flagged</span><strong>{summary.isLoading ? '…' : data?.flagged ?? 0}</strong></article>
        <article className="metric-card"><span>Processing</span><strong>{summary.isLoading ? '…' : data?.verificationProcessing ?? 0}</strong></article>
      </section>

      <section className="dashboard-grid dashboard-priority-grid">
        <article className="panel verification-overview-card">
          <div className="verification-rate-tile" aria-label={`${verificationRate}% verified`}>
            <strong>{summary.isLoading ? '…' : `${verificationRate}%`}</strong>
            <span>verified</span>
          </div>
          <div className="verification-overview-copy">
            <p className="eyebrow">Verification</p>
            <h2>Automated results</h2>
            <p>{summary.isLoading ? 'Loading current verification results…' : `${data?.verificationCompleted ?? 0} inspections have a current verification result. Historical decisions remain preserved in each inspection.`}</p>
          </div>
          <div className="verification-overview-actions">
            <Link className="button primary" to="/review">Review results</Link>
            <Link className="button ghost" to="/inspections">View inspections</Link>
          </div>
        </article>

        <article className="panel attention-panel">
          <p className="eyebrow">Attention</p>
          <h2>Work to check</h2>
          <div className="attention-row"><span>Review required</span><strong>{data?.reviewRequired ?? 0}</strong></div>
          <div className="attention-row"><span>Inconclusive</span><strong>{data?.inconclusive ?? 0}</strong></div>
          <div className="attention-row"><span>Overdue</span><strong>{data?.overdue ?? 0}</strong></div>
          <div className="attention-row"><span>High priority</span><strong>{data?.highPriority ?? 0}</strong></div>
        </article>
      </section>

      <section className="dashboard-grid" style={{ marginTop: 14 }}>
        <article className="panel">
          <p className="eyebrow">Recent results</p>
          <h2>Latest decisions</h2>
          {summary.isLoading ? <div className="async-state" role="status">Loading results…</div> : null}
          {!summary.isLoading && !data?.latestVerifications?.length ? <p className="muted">No completed verification results yet.</p> : (
            <div className="recent-decision-list">
              {data?.latestVerifications?.map((item) => (
                <article className="recent-decision-card" key={item.inspectionId}>
                  <div className="recent-decision-topline">
                    <div>
                      <Link className="table-link" to={`/inspections/${item.inspectionId}`}>{item.title}</Link>
                      <small>{item.locationName || 'Unnamed site'}</small>
                    </div>
                    <div className="badge-row">
                      <span className={verdictBadgeClass(item.verdict)}>{item.verdict?.replace(/_/g, ' ') ?? item.verificationStatus.replace(/_/g, ' ')}</span>
                      {item.receiptStatus ? <span className={item.receiptStatus === 'ISSUED' ? 'badge badge-ready' : 'badge badge-acknowledged'}>{item.receiptStatus}</span> : null}
                    </div>
                  </div>
                  <div className="recent-decision-metrics">
                    <span><small>Score</small><strong>{typeof item.score === 'number' ? item.score.toFixed(2) : '—'}</strong></span>
                    <span><small>Confidence</small><strong>{percent(item.confidence)}</strong></span>
                    <span><small>Engine</small><strong>{item.engineVersion}</strong></span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>

        <article className="panel">
          <p className="eyebrow">Field work</p>
          <h2>Inspection status</h2>
          <div className="attention-row"><span>Draft</span><strong>{data?.draft ?? 0}</strong></div>
          <div className="attention-row"><span>Assigned</span><strong>{data?.assigned ?? 0}</strong></div>
          <div className="attention-row"><span>Acknowledged</span><strong>{data?.acknowledged ?? 0}</strong></div>
          <div className="attention-row"><span>Ready</span><strong>{data?.ready ?? 0}</strong></div>
          <div className="attention-row"><span>Due today</span><strong>{data?.dueToday ?? 0}</strong></div>
          <div className="attention-row"><span>Cancelled</span><strong>{data?.cancelled ?? 0}</strong></div>
        </article>
      </section>
    </>
  )
}
