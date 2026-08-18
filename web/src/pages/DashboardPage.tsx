import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getBackendHealth, getSummary } from '../lib/api'

export function DashboardPage() {
  const health = useQuery({ queryKey: ['backend-health'], queryFn: getBackendHealth, retry: 1 })
  const summary = useQuery({ queryKey: ['inspection-summary'], queryFn: getSummary })

  const cards: Array<[string, number | undefined]> = [
    ['Total inspections', summary.data?.total],
    ['Draft', summary.data?.draft],
    ['Assigned', summary.data?.assigned],
    ['Ready', summary.data?.ready],
    ['Cancelled', summary.data?.cancelled],
  ]

  return (
    <>
      <section className="page-heading split-heading">
        <div><p className="eyebrow">PHASE 2 · OPERATIONS</p><h1>Inspection control desk</h1><p>Real-time inspection workload for your organization.</p></div>
        <div className={`status ${health.isSuccess ? 'online' : ''}`}><span className="dot" />{health.isSuccess ? 'Backend online' : health.isError ? 'Backend unavailable' : 'Checking backend'}</div>
      </section>

      {summary.isError ? <div className="notice error">Unable to load inspection summary: {summary.error.message}</div> : null}
      <section className="metric-grid">
        {cards.map(([label, value]) => <article className="metric-card" key={label}><span>{label}</span><strong>{summary.isLoading ? '…' : value ?? 0}</strong></article>)}
      </section>

      <section className="dashboard-grid">
        <article className="panel accent-panel">
          <p className="eyebrow">FIELD READINESS</p>
          <h2>{summary.data?.ready ?? 0} inspections ready</h2>
          <p>Ready means the assigned inspector has acknowledged the task and explicitly marked it prepared for the next verification phase.</p>
          <Link className="button primary" to="/inspections">Open inspections</Link>
        </article>
        <article className="panel">
          <p className="eyebrow">ATTENTION</p>
          <div className="attention-row"><span>Overdue</span><strong>{summary.data?.overdue ?? 0}</strong></div>
          <div className="attention-row"><span>Due today</span><strong>{summary.data?.dueToday ?? 0}</strong></div>
          <div className="attention-row"><span>High / critical priority</span><strong>{summary.data?.highPriority ?? 0}</strong></div>
        </article>
      </section>
    </>
  )
}
