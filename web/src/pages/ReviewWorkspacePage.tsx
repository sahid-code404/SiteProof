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

function captured(value?: string | null) {
  if (!value) return 'Not available'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
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
  const [inspector, setInspector] = useState('')
  const [verdict, setVerdict] = useState<VerificationVerdict | ''>('')
  const [reviewState, setReviewState] = useState<'all' | 'pending' | 'reviewed'>('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const params = useMemo(() => {
    const next = new URLSearchParams({ limit: '150' })
    if (search.trim()) next.set('search', search.trim())
    if (inspector.trim()) next.set('inspector', inspector.trim())
    if (verdict) next.set('verdict', verdict)
    if (reviewState === 'pending') next.set('reviewed', 'false')
    if (reviewState === 'reviewed') next.set('reviewed', 'true')
    if (dateFrom) next.set('dateFrom', `${dateFrom}T00:00:00Z`)
    if (dateTo) next.set('dateTo', `${dateTo}T23:59:59Z`)
    return next
  }, [search, inspector, verdict, reviewState, dateFrom, dateTo])

  const queue = useQuery({
    queryKey: ['review-workspace', params.toString()],
    queryFn: () => getReviewQueue(params),
  })

  const items = queue.data?.items ?? []
  const pending = items.filter((item) => !item.latestReview).length
  const attention = items.filter((item) => ['REVIEW_REQUIRED', 'FLAGGED', 'INCONCLUSIVE'].includes(item.verdict)).length
  const hasFilters = Boolean(search || inspector || verdict || reviewState !== 'all' || dateFrom || dateTo)

  function clearFilters() {
    setSearch('')
    setInspector('')
    setVerdict('')
    setReviewState('all')
    setDateFrom('')
    setDateTo('')
    setSelectedId(null)
  }

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">Review</p>
          <h1>Verification results</h1>
          <p>Find inspections that need attention and open the evidence behind each result.</p>
        </div>
        <div className="review-summary-chips" aria-live="polite">
          <span className="secure-chip">{queue.isLoading ? '…' : `${pending} pending`}</span>
          <span className="secure-chip">{queue.isLoading ? '…' : `${attention} need attention`}</span>
        </div>
      </section>

      <section className="review-filter-bar" aria-label="Review filters">
        <input
          className="review-filter-search"
          placeholder="Search inspection or site"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search inspection or site"
        />
        <select value={verdict} onChange={(event) => setVerdict(event.target.value as VerificationVerdict | '')} aria-label="Filter by result">
          <option value="">All results</option>
          <option value="REVIEW_REQUIRED">Review required</option>
          <option value="FLAGGED">Flagged</option>
          <option value="INCONCLUSIVE">Inconclusive</option>
          <option value="VERIFIED">Verified</option>
        </select>
        <select value={reviewState} onChange={(event) => setReviewState(event.target.value as 'all' | 'pending' | 'reviewed')} aria-label="Filter by review state">
          <option value="all">All review states</option>
          <option value="pending">Pending</option>
          <option value="reviewed">Reviewed</option>
        </select>
        <div className="review-filter-actions">
          <button className="button ghost" type="button" disabled={!hasFilters} onClick={clearFilters}>Clear</button>
        </div>

        <details className="review-advanced-filters">
          <summary>More filters</summary>
          <div className="review-advanced-grid">
            <input
              placeholder="Inspector name"
              value={inspector}
              onChange={(event) => setInspector(event.target.value)}
              aria-label="Filter by inspector"
            />
            <label className="review-date-filter">From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
            <label className="review-date-filter">To<input type="date" value={dateTo} min={dateFrom || undefined} onChange={(event) => setDateTo(event.target.value)} /></label>
          </div>
        </details>
      </section>

      {queue.isError ? (
        <div className="notice error" role="alert">
          <strong>Could not load review results</strong>
          <p>{queue.error.message}</p>
          <button className="button ghost" type="button" onClick={() => queue.refetch()}>Try again</button>
        </div>
      ) : null}

      <p className="review-results-live" role="status" aria-live="polite">
        {queue.isLoading ? 'Loading results…' : `${items.length} shown`}
      </p>

      <section className="review-metric-strip" aria-label="Review summary">
        <div><span>Shown</span><strong>{queue.isLoading ? '…' : items.length}</strong></div>
        <div><span>Needs attention</span><strong>{queue.isLoading ? '…' : attention}</strong></div>
        <div><span>Pending review</span><strong>{queue.isLoading ? '…' : pending}</strong></div>
      </section>

      <section className="review-workspace-grid">
        <article className="panel review-map-panel">
          <div className="review-section-heading">
            <div><p className="eyebrow">Sites</p><h2>Map</h2></div>
            <small className="muted">Select a marker to match it with the result list.</small>
          </div>
          {queue.isLoading ? <div className="loading-block" role="status">Loading sites…</div> : null}
          {!queue.isLoading && !items.length ? <div className="empty-state"><h3>No matching sites</h3><p>Try clearing one or more filters.</p></div> : null}
          {items.length ? <ReviewMap items={items} selectedId={selectedId} onSelect={setSelectedId} /> : null}
        </article>

        <article className="panel review-queue-panel">
          <div className="review-section-heading">
            <div><p className="eyebrow">Results</p><h2>Inspection queue</h2></div>
            <small className="muted">Open an inspection to review its full evidence and history.</small>
          </div>

          {queue.isLoading ? <div className="loading-block" role="status">Loading results…</div> : null}
          {!queue.isLoading && !items.length ? <div className="empty-state"><h3>No results found</h3><p>Nothing matches the current filters.</p></div> : null}

          <div className="review-card-list">
            {items.map((item) => (
              <article
                className={`review-card ${selectedId === item.inspectionId ? 'selected' : ''}`}
                key={item.inspectionId}
                onMouseEnter={() => setSelectedId(item.inspectionId)}
                aria-label={`${item.title}, ${item.verdict.replace(/_/g, ' ')}`}
              >
                <div className="review-card-topline">
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.locationName || item.locationAddress || 'Unnamed site'}</span>
                  </div>
                  <span className={verdictClass(item.verdict)}>{item.verdict.replace(/_/g, ' ')}</span>
                </div>
                <div className="review-card-context">
                  <span>{item.inspectorName || 'Unassigned'}</span>
                  <span>{captured(item.captureEndedAt)}</span>
                </div>
                <div className="review-score-row">
                  <span><small>Score</small><strong>{score(item.score)}</strong></span>
                  <span><small>Confidence</small><strong>{percent(item.confidence)}</strong></span>
                  <span><small>Review</small><strong>{item.latestReview ? item.latestReview.decision.replace(/_/g, ' ') : 'Pending'}</strong></span>
                </div>
                <div className="review-card-footer">
                  <span className={reviewClass(item.latestReview?.decision)}>{item.latestReview ? 'REVIEWED' : 'PENDING'}</span>
                  <div className="review-card-actions">
                    <button className="review-card-focus" type="button" onClick={() => setSelectedId(item.inspectionId)}>Locate</button>
                    <Link className="button ghost" to={`/inspections/${item.inspectionId}`}>Open</Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </article>
      </section>
    </>
  )
}
