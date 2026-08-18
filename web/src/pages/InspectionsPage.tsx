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
  const inspectors = useQuery({
    queryKey: ['inspectors', 'filter'],
    queryFn: () => getInspectors(),
  })

  const params = useMemo(() => {
    const next = new URLSearchParams({ page: String(page), pageSize: '20' })
    if (search.trim()) next.set('search', search.trim())
    if (status) next.set('status', status)
    if (priority) next.set('priority', priority)
    if (inspectorId) next.set('inspectorId', inspectorId)
    return next
  }, [search, status, priority, inspectorId, page])

  const query = useQuery({
    queryKey: ['inspections', params.toString()],
    queryFn: () => getInspections(params),
  })

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">INSPECTION MANAGEMENT</p>
          <h1>Inspections</h1>
          <p>Create, assign and track field work without losing assignment history.</p>
        </div>
        {canManage ? <Link className="button primary" to="/inspections/new">+ Create inspection</Link> : null}
      </section>

      <section className="filter-bar">
        <input
          className="search-input"
          placeholder="Search title, location or address"
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(1) }}
        />
        <select value={status} onChange={(event) => { setStatus(event.target.value as InspectionStatus | ''); setPage(1) }}>
          <option value="">All statuses</option>
          {['DRAFT','ASSIGNED','ACKNOWLEDGED','READY','CANCELLED'].map((item) => <option key={item}>{item}</option>)}
        </select>
        <select value={priority} onChange={(event) => { setPriority(event.target.value as InspectionPriority | ''); setPage(1) }}>
          <option value="">All priorities</option>
          {['LOW','MEDIUM','HIGH','CRITICAL'].map((item) => <option key={item}>{item}</option>)}
        </select>
        <select value={inspectorId} onChange={(event) => { setInspectorId(event.target.value); setPage(1) }}>
          <option value="">All inspectors</option>
          {inspectors.data?.items.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
        </select>
      </section>

      <section className="table-panel">
        {query.isLoading ? <div className="loading-block">Loading inspections…</div> : null}
        {query.isError ? <div className="notice error">{query.error.message}</div> : null}
        {query.data?.items.length === 0 ? <div className="empty-state"><h3>No inspections found</h3><p>Create an inspection or change the active filters.</p></div> : null}
        {query.data?.items.length ? (
          <div className="table-scroll"><table><thead><tr><th>Inspection</th><th>Type</th><th>Location</th><th>Inspector</th><th>Priority</th><th>Deadline</th><th>Status</th><th>Created</th></tr></thead><tbody>
            {query.data.items.map((inspection) => (
              <tr key={inspection.id}>
                <td><Link className="table-link" to={`/inspections/${inspection.id}`}>{inspection.title}</Link>{inspection.isOverdue ? <small className="overdue">Overdue</small> : null}</td>
                <td>{inspection.inspectionType.replace('_', ' ')}</td>
                <td>{inspection.locationName || inspection.locationAddress || `${inspection.expectedLatitude.toFixed(4)}, ${inspection.expectedLongitude.toFixed(4)}`}</td>
                <td>{inspection.activeAssignment?.inspector.name ?? 'Unassigned'}</td>
                <td><StatusBadge value={inspection.priority} /></td>
                <td>{formatDate(inspection.deadline)}</td>
                <td><StatusBadge value={inspection.status} /></td>
                <td>{new Intl.DateTimeFormat().format(new Date(inspection.createdAt))}</td>
              </tr>
            ))}
          </tbody></table></div>
        ) : null}
        {query.data && query.data.totalPages > 1 ? (
          <div className="pagination">
            <button className="button ghost" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
            <span>Page {query.data.page} of {query.data.totalPages}</span>
            <button className="button ghost" disabled={page >= query.data.totalPages} onClick={() => setPage((value) => value + 1)}>Next</button>
          </div>
        ) : null}
      </section>
    </>
  )
}
