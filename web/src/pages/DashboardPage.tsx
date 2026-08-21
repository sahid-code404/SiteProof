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

type Phase11DashboardSummary = Awaited<ReturnType<typeof getSummary>> & {
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
  const data = summary.data as Phase11DashboardSummary | undefined
  const reviewQueue = (data?.reviewRequired ?? 0) + (data?.inconclusive ?? 0)

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">SITEPROOF · VERIFICATION OPERATIONS</p>
          <h1>Trust & evidence dashboard</h1>
          <p>Current verification outcomes, reviewer attention, signed receipt state, and field workload in one operational view.</p>
        </div>
        <div className={`status ${health.isSuccess ? 'online' : ''}`}><span className="dot" />{health.isSuccess ? 'Backend online' : health.isError ? 'Backend unavailable' : 'Checking backend'}</div>
      </section>

      {summary.isError ? <div className="notice error">Unable to load dashboard summary: {summary.error.message}</div> : null}

      <section className="metric-grid">
        <article className="metric-card"><span>Total inspections</span><strong>{summary.isLoading ? '…' : data?.total ?? 0}</strong></article>
        <article className="metric-card"><span>Verified</span><strong>{summary.isLoading ? '…' : data?.verified ?? 0}</strong></article>
        <article className="metric-card"><span>Review queue</span><strong>{summary.isLoading ? '…' : reviewQueue}</strong></article>
        <article className="metric-card"><span>Flagged</span><strong>{summary.isLoading ? '…' : data?.flagged ?? 0}</strong></article>
        <article className="metric-card"><span>Processing</span><strong>{summary.isLoading ? '…' : data?.verificationProcessing ?? 0}</strong></article>
      </section>

      <section className="dashboard-grid">
        <article className="panel accent-panel">
          <p className="eyebrow">AUTOMATED VERIFICATION</p>
          <h2>{summary.isLoading ? 'Calculating…' : `${data?.verificationRate ?? 0}% verified`}</h2>
          <p>{data?.verificationCompleted ?? 0} latest immutable verification decisions are represented in the current rate. Historical results remain preserved but do not inflate current verdict counts.</p>
          <Link className="button primary" to="/inspections">Open inspection evidence</Link>
        </article>
        <article className="panel">
          <p className="eyebrow">REVIEW ATTENTION</p>
          <div className="attention-row"><span>Review required</span><strong>{data?.reviewRequired ?? 0}</strong></div>
          <div className="attention-row"><span>Inconclusive</span><strong>{data?.inconclusive ?? 0}</strong></div>
          <div className="attention-row"><span>Overdue inspections</span><strong>{data?.overdue ?? 0}</strong></div>
          <div className="attention-row"><span>High / critical priority</span><strong>{data?.highPriority ?? 0}</strong></div>
        </article>
      </section>

      <section className="dashboard-grid" style={{ marginTop: 20 }}>
        <article className="panel">
          <p className="eyebrow">LATEST VERIFICATION RESULTS</p>
          <h2>Recent trust decisions</h2>
          {!data?.latestVerifications?.length ? <p className="muted">No completed verification results yet.</p> : data.latestVerifications.map((item) => (
            <div className="challenge-row" key={item.inspectionId}>
              <div>
                <Link className="table-link" to={`/inspections/${item.inspectionId}`}>{item.title}</Link>
                <small>{item.locationName || 'Unnamed site'} · {item.engineVersion}</small>
              </div>
              <div className="badge-row">
                <span className={verdictBadgeClass(item.verdict)}>{item.verdict?.replace(/_/g, ' ') ?? item.verificationStatus.replace(/_/g, ' ')}</span>
                {item.receiptStatus ? <span className={item.receiptStatus === 'ISSUED' ? 'badge badge-ready' : 'badge badge-acknowledged'}>{item.receiptStatus}</span> : <span className="badge">NO RECEIPT</span>}
              </div>
              <small>Score {typeof item.score === 'number' ? item.score.toFixed(2) : '—'} · confidence {percent(item.confidence)}{item.receiptNumber ? ` · ${item.receiptNumber}` : ''}</small>
            </div>
          ))}
        </article>

        <article className="panel">
          <p className="eyebrow">FIELD WORKFLOW</p>
          <h2>Inspection pipeline</h2>
          <div className="attention-row"><span>Draft</span><strong>{data?.draft ?? 0}</strong></div>
          <div className="attention-row"><span>Assigned</span><strong>{data?.assigned ?? 0}</strong></div>
          <div className="attention-row"><span>Acknowledged</span><strong>{data?.acknowledged ?? 0}</strong></div>
          <div className="attention-row"><span>Ready for capture</span><strong>{data?.ready ?? 0}</strong></div>
          <div className="attention-row"><span>Due today</span><strong>{data?.dueToday ?? 0}</strong></div>
          <div className="attention-row"><span>Cancelled</span><strong>{data?.cancelled ?? 0}</strong></div>
        </article>
      </section>
    </>
  )
}
