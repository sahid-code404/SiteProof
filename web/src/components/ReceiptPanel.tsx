import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getLatestVerificationSession } from '../lib/api'
import { getStoredUser } from '../lib/auth'
import { getSessionReceipts, issueSessionReceipt, verifyEvidence, type Receipt } from '../lib/receiptApi'
import { integrityLabel, shortHash } from '../lib/receipt'

function verdictBadgeClass(verdict: string) {
  if (verdict === 'VERIFIED') return 'badge badge-ready'
  if (verdict === 'FLAGGED') return 'badge badge-critical'
  if (verdict === 'REVIEW_REQUIRED') return 'badge badge-high'
  return 'badge'
}

function receiptStatusBadgeClass(status: Receipt['status']) {
  if (status === 'ISSUED') return 'badge badge-ready'
  if (status === 'REVOKED') return 'badge badge-critical'
  return 'badge badge-acknowledged'
}

function confidenceQuality(value: number) {
  if (value >= 0.90) return 'Very high'
  if (value >= 0.80) return 'High'
  if (value >= 0.70) return 'Good'
  if (value >= 0.55) return 'Moderate'
  return 'Low'
}

function scoreQuality(value: number) {
  if (value >= 85) return 'Strong'
  if (value >= 65) return 'Moderate'
  return 'Weak'
}

export function ReceiptPanel({ inspectionId }: { inspectionId: string }) {
  const canIssue = getStoredUser()?.role === 'ADMIN'
  const queryClient = useQueryClient()
  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })
  const receipts = useQuery({
    queryKey: ['receipts', session.data?.id],
    queryFn: () => getSessionReceipts(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: (query) => query.state.data?.length ? false : 5000,
  })
  const issue = useMutation({
    mutationFn: () => issueSessionReceipt(session.data!.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['receipts', session.data?.id] }),
  })

  const current = receipts.data?.[0]
  const deepCheck = useMutation({
    mutationFn: () => verifyEvidence(current!.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['receipts', session.data?.id] }),
  })

  if (!session.data) return null
  if (receipts.isLoading) {
    return <article className="panel"><p className="eyebrow">Receipt</p><p>Loading signed receipt…</p></article>
  }
  if (receipts.isError) {
    return <article className="panel"><p className="eyebrow">Receipt</p><div className="notice error">{receipts.error.message}</div></article>
  }

  if (!current) {
    return (
      <article className="panel">
        <p className="eyebrow">Receipt</p>
        <h2>Not issued yet</h2>
        <p className="muted">A signed receipt is created after verification is complete.</p>
        {canIssue ? <button className="button ghost" disabled={issue.isPending} onClick={() => issue.mutate()}>{issue.isPending ? 'Issuing…' : 'Issue receipt'}</button> : null}
        {issue.error ? <div className="notice error">{issue.error.message}</div> : null}
      </article>
    )
  }

  return (
    <article className="panel receipt-card">
      <div className="receipt-heading">
        <div>
          <p className="eyebrow">Receipt</p>
          <h2>{current.receiptNumber}</h2>
          <p className="muted">Signed {new Date(current.issuedAt).toLocaleString()}</p>
        </div>
        <div className="badge-row">
          <span className={verdictBadgeClass(current.verdict)}>{current.verdict.replace(/_/g, ' ')}</span>
          <span className={receiptStatusBadgeClass(current.status)}>{current.status}</span>
          <span className={current.signatureValid ? 'badge badge-ready' : 'badge badge-critical'}>{current.signatureValid ? 'SIGNATURE VALID' : 'SIGNATURE INVALID'}</span>
        </div>
      </div>

      <div className="receipt-key-metrics">
        <div><span>Engine</span><strong>{current.engineVersion}</strong></div>
        <div><span>Evidence score</span><strong>{current.score.toFixed(2)} · {scoreQuality(current.score)}</strong></div>
        <div><span>Decision confidence</span><strong>{Math.round(current.confidence * 100)}% · {confidenceQuality(current.confidence)}</strong></div>
      </div>

      {current.status === 'REVOKED' ? <div className="notice error"><strong>Receipt revoked</strong><p>{current.revocationReason}</p></div> : null}
      {current.lastEvidenceIntegrity && current.lastEvidenceIntegrity !== 'MATCH' ? <div className="notice error"><strong>Evidence mismatch</strong><p>{current.lastEvidenceIntegrity}</p></div> : null}

      <div className="receipt-actions">
        <Link className="button primary" to={`/receipts/${current.id}`}>Open receipt</Link>
        <button className="button ghost" disabled={deepCheck.isPending} onClick={() => deepCheck.mutate()}>{deepCheck.isPending ? 'Checking…' : 'Verify evidence'}</button>
      </div>

      {deepCheck.data ? <div className={deepCheck.data.state === 'MATCH' ? 'notice' : 'notice error'}><strong>{deepCheck.data.state}</strong> · {deepCheck.data.files.length} files checked</div> : null}
      {deepCheck.error ? <div className="notice error">{deepCheck.error.message}</div> : null}

      <details className="evidence-details">
        <summary>Receipt details</summary>
        <div className="evidence-details-content receipt-detail-list">
          <div><span>Type</span><strong>{current.receiptType.replace(/_/g, ' ')}</strong></div>
          <div><span>Policy</span><strong>{current.policyVersion}</strong></div>
          <div><span>Manifest</span><strong>{shortHash(current.manifestSha256, 8)}</strong></div>
          <div><span>Signature</span><strong>{integrityLabel(current.signatureState)}</strong></div>
        </div>
      </details>

      {receipts.data && receipts.data.length > 1 ? (
        <details className="evidence-details receipt-history-details">
          <summary>Receipt history ({receipts.data.length})</summary>
          <div className="evidence-details-content receipt-history-list">
            {receipts.data.map((item, index) => (
              <div className="receipt-history-row" key={item.id}>
                <div>
                  <strong>{index === 0 ? 'Current' : 'Previous'} · {item.receiptNumber}</strong>
                  <small>{item.engineVersion} · {new Date(item.issuedAt).toLocaleString()}</small>
                </div>
                <div className="badge-row">
                  <span className={verdictBadgeClass(item.verdict)}>{item.verdict.replace(/_/g, ' ')}</span>
                  <span className={receiptStatusBadgeClass(item.status)}>{item.status}</span>
                </div>
                <Link className="button ghost" to={`/receipts/${item.id}`}>View</Link>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </article>
  )
}
