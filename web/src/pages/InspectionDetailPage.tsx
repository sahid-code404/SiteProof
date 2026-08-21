import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { AdvancedSecurityPanel } from '../components/AdvancedSecurityPanel'
import { AdvancedSignalsPanel } from '../components/AdvancedSignalsPanel'
import { EvidenceVideoPanel } from '../components/EvidenceVideoPanel'
import { ReceiptPanel } from '../components/ReceiptPanel'
import { SiteMap } from '../components/SiteMap'
import { StatusBadge } from '../components/StatusBadge'
import { VerificationReportPanel } from '../components/VerificationReportPanel'
import { VerificationSessionPanel } from '../components/VerificationSessionPanel'
import { assignInspection, cancelInspection, getInspection, getInspectors, reassignInspection } from '../lib/api'
import { getStoredUser } from '../lib/auth'

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function formatVideoLength(seconds: number) {
  return seconds >= 60 ? `${Math.floor(seconds / 60)} min ${seconds % 60 ? `${seconds % 60} sec` : ''}`.trim() : `${seconds} sec`
}

export function InspectionDetailPage() {
  const { id = '' } = useParams()
  const user = getStoredUser()
  const canManage = user?.role === 'ADMIN'
  const canReview = user?.role === 'ADMIN' || user?.role === 'REVIEWER'
  const queryClient = useQueryClient()
  const [inspectorId, setInspectorId] = useState('')
  const [reason, setReason] = useState('')
  const [cancelReason, setCancelReason] = useState('')
  const inspection = useQuery({ queryKey: ['inspection', id], queryFn: () => getInspection(id), refetchInterval: 5000 })
  const inspectors = useQuery({ queryKey: ['inspectors', 'active'], queryFn: () => getInspectors() })

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ['inspection', id] })
    queryClient.invalidateQueries({ queryKey: ['inspections'] })
    queryClient.invalidateQueries({ queryKey: ['inspection-summary'] })
    queryClient.invalidateQueries({ queryKey: ['review-workspace'] })
    queryClient.invalidateQueries({ queryKey: ['verification-session', id] })
  }

  const assign = useMutation({ mutationFn: () => assignInspection(id, inspectorId), onSuccess: refresh })
  const reassign = useMutation({ mutationFn: () => reassignInspection(id, inspectorId, reason), onSuccess: refresh })
  const cancel = useMutation({ mutationFn: () => cancelInspection(id, cancelReason), onSuccess: refresh })

  if (inspection.isLoading) return <div className="loading-block">Loading inspection…</div>
  if (inspection.isError || !inspection.data) return <div className="notice error">{inspection.error?.message ?? 'Inspection not found'}</div>

  const item = inspection.data
  const canAssign = canManage && item.status === 'DRAFT'
  const canReassign = canManage && ['ASSIGNED', 'ACKNOWLEDGED', 'READY'].includes(item.status)
  const canCancel = canManage && !['CANCELLED', 'APPROVED', 'REJECTED'].includes(item.status)
  const actionError = assign.error ?? reassign.error ?? cancel.error

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">Inspection · {item.id.slice(0, 8).toUpperCase()}</p>
          <h1>{item.title}</h1>
          <div className="badge-row">
            <StatusBadge value={item.status} />
            <StatusBadge value={item.priority} />
            {item.isOverdue ? <span className="badge badge-overdue">OVERDUE</span> : null}
          </div>
        </div>
        <div className="heading-actions">
          {canReview ? <Link className="button ghost" to="/review">Back to review</Link> : null}
          {canManage && ['DRAFT', 'ASSIGNED', 'ACKNOWLEDGED', 'READY'].includes(item.status) ? <Link className="button ghost" to={`/inspections/${id}/edit`}>Edit</Link> : null}
        </div>
      </section>

      <div className="detail-grid">
        <section className="detail-main">
          <VerificationReportPanel inspectionId={id} />
          <ReceiptPanel inspectionId={id} />
          <EvidenceVideoPanel inspectionId={id} />

          <article className="panel">
            <p className="eyebrow">Site</p>
            <h2>Location</h2>
            <SiteMap latitude={item.expectedLatitude} longitude={item.expectedLongitude} radius={item.allowedRadiusMeters} />
            <div className="definition-grid">
              <div><span>Site</span><strong>{item.locationName || 'Unnamed site'}</strong><small>{item.locationAddress || 'No address provided'}</small></div>
              <div><span>Capture area</span><strong>{item.allowedRadiusMeters} m radius</strong><small>{item.expectedLatitude.toFixed(6)}, {item.expectedLongitude.toFixed(6)}</small></div>
              <div><span>Required video</span><strong>{formatVideoLength(item.captureDurationSeconds)}</strong><small>One continuous capture through the movement checks</small></div>
            </div>
          </article>

          <article className="panel">
            <p className="eyebrow">Instructions</p>
            <h2>{item.inspectionType.replace('_', ' ')}</h2>
            {item.description ? <p>{item.description}</p> : null}
            <div className="callout"><strong>Inspector notes</strong><p>{item.instructions || 'No additional instructions.'}</p></div>
          </article>

          <details className="panel technical-evidence">
            <summary><span><strong>Technical evidence</strong><small>Security signals, sensor details and capture diagnostics</small></span></summary>
            <div className="technical-evidence-content"><AdvancedSecurityPanel inspectionId={id} /><AdvancedSignalsPanel inspectionId={id} /><VerificationSessionPanel inspectionId={id} /></div>
          </details>

          <article className="panel">
            <p className="eyebrow">History</p>
            <h2>Assignments</h2>
            {item.assignmentHistory.length ? (
              <div className="timeline">
                {item.assignmentHistory.map((assignment) => (
                  <div className="timeline-item" key={assignment.id}>
                    <span className="timeline-dot" />
                    <div><strong>{assignment.inspector.name}</strong><p>{assignment.status.replace(/_/g, ' ')} · {formatDate(assignment.assignedAt)}</p>{assignment.reason ? <small>{assignment.reason}</small> : null}</div>
                  </div>
                ))}
              </div>
            ) : <p className="muted">No assignment history yet.</p>}
          </article>
        </section>

        <aside className="detail-side">
          <article className="panel compact">
            <p className="eyebrow">Schedule</p>
            <span className="label">Deadline</span><strong>{formatDate(item.deadline)}</strong>
            <span className="label">Video length</span><strong>{formatVideoLength(item.captureDurationSeconds)}</strong>
            <span className="label">Created by</span><strong>{item.createdByName}</strong>
            <span className="label">Updated</span><strong>{formatDate(item.updatedAt)}</strong>
          </article>

          <article className="panel compact">
            <p className="eyebrow">Assigned to</p>
            {item.activeAssignment ? <><strong className="large-text">{item.activeAssignment.inspector.name}</strong><span>{item.activeAssignment.inspector.email}</span></> : <p className="muted">Unassigned</p>}
          </article>

          {(canAssign || canReassign) ? (
            <article className="panel compact">
              <p className="eyebrow">{canAssign ? 'Assign inspector' : 'Reassign inspector'}</p>
              <select value={inspectorId} onChange={(event) => setInspectorId(event.target.value)}>
                <option value="">Select inspector</option>
                {inspectors.data?.items.map((person) => <option key={person.id} value={person.id}>{person.name} · {person.employeeCode || person.email}</option>)}
              </select>
              {canReassign ? <textarea rows={3} placeholder="Reason" value={reason} onChange={(event) => setReason(event.target.value)} /> : null}
              <button className="button primary" disabled={!inspectorId || (canReassign && reason.trim().length < 3) || assign.isPending || reassign.isPending} onClick={() => canAssign ? assign.mutate() : reassign.mutate()}>{canAssign ? 'Assign' : 'Reassign'}</button>
            </article>
          ) : null}

          {canCancel ? (
            <details className="panel compact danger-panel danger-details">
              <summary>Cancel inspection</summary>
              <textarea rows={3} placeholder="Reason for cancellation" value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} />
              <button className="button danger" disabled={cancelReason.trim().length < 3 || cancel.isPending} onClick={() => cancel.mutate()}>{cancel.isPending ? 'Cancelling…' : 'Cancel inspection'}</button>
            </details>
          ) : null}

          {actionError ? <div className="notice error">{actionError.message}</div> : null}
        </aside>
      </div>
    </>
  )
}
