import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  getInspections,
  getInspectors,
  type InspectionPriority,
  type InspectionStatus,
} from '../lib/api'
import { getStoredUser } from '../lib/auth'
import { StatusBadge } from '../components/StatusBadge'

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function InspectionsPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<InspectionStatus | ''>('')
  const [priority, setPriority] = useState<InspectionPriority | ''>('')
  const [inspectorId, setInspectorId] = useState('')
  const [page, setPage] = useState(1)
  const canManage = getStoredUser()?.role === 'ADMIN'
  const inspectors = useQuery({ queryKey: ['inspectors', 'filter'], queryFn: () => getInspectors() })

  const params = useMemo(() => {
    const next = new URLSearchParams({ page: String(page), pageSize: '20' })
    if (search.trim()) next.set('search', search.trim())
    if (status) next.set('status', status)
    if (priority) next.set('priority', priority)
    if (inspectorId) next.set('inspectorId', inspectorId)
    return next
  }, [search, status, priority, inspectorId, page])

  const query = useQuery({ queryKey: ['inspections', params.toString()], queryFn: () => getInspections(params) })
  const hasExtraFilters = Boolean(priority || inspectorId)

  function clearExtraFilters() {
    setPriority('')
    setInspectorId('')
    setPage(1)
  }

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">Field work</p>
          <h1>Inspections</h1>
          <p>Find an inspection, check its status and open the full record.</p>
        </div>
        {canManage ? <Link className="button primary" to="/inspections/new">New inspection</Link> : null}
      </section>

      <section className="filter-bar inspection-filter-bar" aria-label="Inspection filters">
        <input
          className="search-input"
          aria-label="Search inspections"
          placeholder="Search inspection or site"
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(1) }}
        />
        <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as InspectionStatus | ''); setPage(1) }}>
          <option value="">All statuses</option>
          {['DRAFT','ASSIGNED','ACKNOWLEDGED','READY','CANCELLED'].map((item) => <option key={item}>{item}</option>)}
        </select>
        <details className="inspection-more-filters">
          <summary>More filters{hasExtraFilters ? ' · active' : ''}</summary>
          <div className="inspection-more-filter-grid">
            <select aria-label="Filter by priority" value={priority} onChange={(event) => { setPriority(event.target.value as InspectionPriority | ''); setPage(1) }}>
              <option value="">All priorities</option>
              {['LOW','MEDIUM','HIGH','CRITICAL'].map((item) => <option key={item}>{item}</option>)}
            </select>
            <select aria-label="Filter by inspector" value={inspectorId} onChange={(event) => { setInspectorId(event.target.value); setPage(1) }}>
              <option value="">All inspectors</option>
              {inspectors.data?.items.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
            </select>
            <button className="button ghost" type="button" disabled={!hasExtraFilters} onClick={clearExtraFilters}>Clear</button>
          </div>
        </details>
      </section>

      <section className="table-panel" aria-busy={query.isLoading}>
        {query.isLoading ? <div className="loading-block" role="status">Loading inspections…</div> : null}
        {query.isError ? (
          <div className="notice error" role="alert">
            <strong>Could not load inspections</strong>
            <p>{query.error.message}</p>
            <button className="button ghost" type="button" onClick={() => query.refetch()}>Try again</button>
          </div>
        ) : null}
        {query.data?.items.length === 0 ? <div className="empty-state"><h3>No inspections found</h3><p>Try another search or filter.</p></div> : null}
        {query.data?.items.length ? (
          <div className="table-scroll">
            <table className="inspection-table">
              <caption className="sr-only">Inspections with site, assignment, deadline and status</caption>
              <thead>
                <tr>
                  <th scope="col">Inspection</th>
                  <th scope="col">Site</th>
                  <th scope="col">Inspector</th>
                  <th scope="col">Due</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((inspection) => (
                  <tr key={inspection.id}>
                    <td>
                      <Link className="table-link" to={`/inspections/${inspection.id}`}>{inspection.title}</Link>
                      <div className="table-secondary-line">
                        <StatusBadge value={inspection.priority} />
                        <span>{inspection.inspectionType.replace('_', ' ')}</span>
                        {inspection.isOverdue ? <span className="overdue-inline">Overdue</span> : null}
                      </div>
                    </td>
                    <td>{inspection.locationName || inspection.locationAddress || `${inspection.expectedLatitude.toFixed(4)}, ${inspection.expectedLongitude.toFixed(4)}`}</td>
                    <td>{inspection.activeAssignment?.inspector.name ?? 'Unassigned'}</td>
                    <td>{formatDate(inspection.deadline)}</td>
                    <td><StatusBadge value={inspection.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {query.data && query.data.totalPages > 1 ? (
          <div className="pagination">
            <button className="button ghost" type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
            <span aria-live="polite">{query.data.page} / {query.data.totalPages}</span>
            <button className="button ghost" type="button" disabled={page >= query.data.totalPages} onClick={() => setPage((value) => value + 1)}>Next</button>
          </div>
        ) : null}
      </section>
    </>
  )
}
