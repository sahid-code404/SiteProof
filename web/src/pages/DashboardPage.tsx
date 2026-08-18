import { useQuery } from '@tanstack/react-query'
import { getBackendHealth } from '../lib/api'

const stats = [
  ['Active inspections', '—'],
  ['Pending reviews', '—'],
  ['Verified today', '—'],
  ['Flagged submissions', '—'],
]

export function DashboardPage() {
  const health = useQuery({
    queryKey: ['backend-health'],
    queryFn: getBackendHealth,
    retry: 1,
  })

  return (
    <main className="shell">
      <header className="header">
        <div>
          <p className="eyebrow">FIELD VERIFICATION PLATFORM</p>
          <h1>SiteProof</h1>
          <p className="subtitle">Phase 1 foundation dashboard</p>
        </div>
        <div className={`status ${health.isSuccess ? 'online' : ''}`}>
          <span className="dot" />
          {health.isSuccess ? 'Backend online' : health.isError ? 'Backend unavailable' : 'Checking backend'}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">FOUNDATION READY</p>
          <h2>Build verification in layers, not shortcuts.</h2>
          <p>
            Authentication, inspection management, live capture, randomized challenges and sensor fusion will be added milestone by milestone.
          </p>
        </div>
        <div className="score">01<span>/11</span><small>phases</small></div>
      </section>

      <section className="stats">
        {stats.map(([label, value]) => (
          <article className="card" key={label}>
            <p>{label}</p>
            <strong>{value}</strong>
            <small>Available after Phase 2</small>
          </article>
        ))}
      </section>

      <section className="panel">
        <div>
          <p className="eyebrow">NEXT MILESTONE</p>
          <h3>Inspection management</h3>
          <p>Create organizations, users, inspectors, inspections and assignment workflow.</p>
        </div>
        <span className="pill">PHASE 2</span>
      </section>
    </main>
  )
}
