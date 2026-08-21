import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ReviewMap } from '../components/ReviewMap'
import { getReviewQueue, type VerificationVerdict } from '../lib/verificationApi'

function percent(value?: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

function score(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(2) : '—'
}

function verdictClass(value: VerificationVerdict) {
  if (value === 'VERIFIED') return 'badge badge-ready'
  if (value === 'REVIEW_REQUIRED') return 'badge badge-high'
  if (value === 'FLAGGED') return 'badge badge-critical'
  return 'badge badge-acknowledged'
}

function reviewClass(value?: string | null) {
  if (value === 'APPROVED') return 'badge badge-ready'
  if (value === 'REJECTED') return 'badge badge-critical'
  if (value === 'RECAPTURE_REQUIRED') return 'badge badge-high'
  return 'badge'
}

export function ReviewWorkspacePage() {
  const [search, setSearch] = useState('')
  const [verdict, setVerdict] = useState<VerificationVerdict | ''>('')
  const [reviewState, setReviewState] = useState<'all' | 'pending' | 'reviewed'>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const params = useMemo(() => {
    const next = new URLSearchParams({ limit: '150' })
    if (search.trim()) next.set('search', search.trim())
    if (verdict) next.set('verdict', verdict)
    if (reviewState === 'pending') next.set('reviewed', 'false')
    if (reviewState === 'reviewed') next.set('reviewed', 'true')
    return next
  }, [search, verdict, reviewState])

  const queue = useQuery({
    queryKey: ['review-workspace', params.toString()],
    queryFn: () => getReviewQueue(params),
  })

  const items = queue.data?.items ?? []
  const pending = items.filter((item) => !item.latestReview).length
  const attention = items.filter((item) => ['REVIEW_REQUIRED', 'FLAGGED', 'INCONCLUSIVE'].includes(item.verdict)).length

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">REVIEW OPERATIONS</p>
          <h1>Reviewer workspace</h1>
          <p>Map current verification decisions, prioritize attention, and open the complete evidence record without changing the automated verdict.</p>
        </div>
        <div className="review-summary-chips">
          <span className="secure-chip">{queue.isLoading ? '…' : `${queue.data?.total ?? 0} current decisions`}</span>
          <span className="secure-chip">{queue.isLoading ? '…' : `${pending} pending review`}</span>
        </div>
      </section>

      <section className="review-filter-bar">
        <input
          placeholder="Search inspection, site or address"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search reviewer workspace"
        />
        <select value={verdict} onChange={(event) => setVerdict(event.target.value as VerificationVerdict | '')} aria-label="Filter by automated verdict">
          <option value="">All automated verdicts</option>
          <option value="REVIEW_REQUIRED">Review required</option>
          <option value="FLAGGED">Flagged</option>
          <option value="INCONCLUSIVE">Inconclusive</option>
          <option value="VERIFIED">Verified</option>
        </select>
        <select value={reviewState} onChange={(event) => setReviewState(event.target.value as 'all' | 'pending' | 'reviewed')} aria-label="Filter by human review state">
          <option value="all">All review states</option>
          <option value="pending">Pending human review</option>
          <option value="reviewed">Reviewed</option>
        </select>
      </section>

      {queue.isError ? <div className="notice error">Unable to load reviewer workspace: {queue.error.message}</div> : null}

      <section className="review-metric-strip">
        <div><span>Visible decisions</span><strong>{queue.isLoading ? '…' : items.length}</strong></div>
        <div><span>Needs attention</span><strong>{queue.isLoading ? '…' : attention}</strong></div>
        <div><span>Pending human review</span><strong>{queue.isLoading ? '…' : pending}</strong></div>
      </section>

      <section className="review-workspace-grid">
        <article className="panel review-map-panel">
          <div className="review-section-heading">
            <div><p className="eyebrow">SITE OVERVIEW</p><h2>Verification map</h2></div>
            <small className="muted">Pins show expected inspection sites for the current verification decision.</small>
          </div>
          {queue.isLoading ? <div className="loading-block">Loading verification sites…</div> : null}
          {!queue.isLoading && !items.length ? <div className="empty-state"><h3>No matching sites</h3><p>Change the active filters to show current verification decisions.</p></div> : null}
          {items.length ? <ReviewMap items={items} selectedId={selectedId} onSelect={setSelectedId} /> : null}
        </article>

        <article className="panel review-queue-panel">
          <div className="review-section-heading">
            <div><p className="eyebrow">CURRENT DECISIONS</p><h2>Evidence queue</h2></div>
            <small className="muted">Automated verdicts remain immutable; reviewer actions are separate audit events.</small>
          </div>

          {queue.isLoading ? <div className="loading-block">Loading current decisions…</div> : null}
          {!queue.isLoading && !items.length ? <div className="empty-state"><h3>No decisions found</h3><p>Nothing matches the current reviewer filters.</p></div> : null}

          <div className="review-card-list">
            {items.map((item) => (
              <button
                type="button"
                className={`review-card ${selectedId === item.inspectionId ? 'selected' : ''}`}
                key={item.inspectionId}
                onClick={() => setSelectedId(item.inspectionId)}
              >
                <div className="review-card-topline">
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.locationName || item.locationAddress || 'Unnamed site'}</span>
                  </div>
                  <span className={verdictClass(item.verdict)}>{item.verdict.replace(/_/g, ' ')}</span>
                </div>
                <div className="review-score-row">
                  <span><small>Score</small><strong>{score(item.score)}</strong></span>
                  <span><small>Confidence</small><strong>{percent(item.confidence)}</strong></span>
                  <span><small>Engine</small><strong>{item.engineVersion}</strong></span>
                </div>
                <div className="review-card-footer">
                  <span className={reviewClass(item.latestReview?.decision)}>{item.latestReview ? item.latestReview.decision.replace(/_/g, ' ') : 'PENDING REVIEW'}</span>
                  <Link className="button ghost" to={`/inspections/${item.inspectionId}`} onClick={(event) => event.stopPropagation()}>Open evidence</Link>
                </div>
              </button>
            ))}
          </div>
        </article>
      </section>
    </>
  )
}
