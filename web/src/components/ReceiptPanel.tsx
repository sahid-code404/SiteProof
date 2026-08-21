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

export function ReceiptPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canIssue = role === 'ADMIN'
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
    return <article className="panel"><p className="eyebrow">SIGNED RECEIPT · AUDIT CHAIN</p><p>Checking cryptographic receipt history…</p></article>
  }
  if (receipts.isError) {
    return <article className="panel"><p className="eyebrow">SIGNED RECEIPT · AUDIT CHAIN</p><div className="notice error">{receipts.error.message}</div></article>
  }
  if (!current) {
    return (
      <article className="panel">
        <p className="eyebrow">SIGNED RECEIPT · AUDIT CHAIN</p>
        <h3>Not issued yet</h3>
        <p className="muted">A signed receipt is created only after a completed verification result and successful server-side evidence re-hash. Historical decisions are never rewritten.</p>
        {canIssue ? <button className="button ghost" disabled={issue.isPending} onClick={() => issue.mutate()}>{issue.isPending ? 'Sealing…' : 'Issue receipt'}</button> : null}
        {issue.error ? <div className="notice error">{issue.error.message}</div> : null}
      </article>
    )
  }

  return (
    <article className="panel">
      <p className="eyebrow">SIGNED RECEIPT · CURRENT AUDIT STATE</p>
      <div className="badge-row">
        <span className={verdictBadgeClass(current.verdict)}>{current.verdict.replace(/_/g, ' ')}</span>
        <span className={receiptStatusBadgeClass(current.status)}>{current.status}</span>
        <span className={current.signatureValid ? 'badge badge-ready' : 'badge badge-critical'}>{current.signatureValid ? 'SIGNATURE VALID' : 'SIGNATURE INVALID'}</span>
      </div>
      <div className="definition-grid">
        <div><span>Receipt</span><strong>{current.receiptNumber}</strong><small>{current.receiptType.replace(/_/g, ' ')}</small></div>
        <div><span>Engine</span><strong>{current.engineVersion}</strong><small>Policy {current.policyVersion}</small></div>
        <div><span>Score</span><strong>{current.score.toFixed(2)} / 100</strong><small>Confidence {Math.round(current.confidence * 100)}%</small></div>
        <div><span>Signature</span><strong>{current.signatureValid ? '✓ VALID' : '⚠ INVALID'}</strong><small>{integrityLabel(current.signatureState)}</small></div>
        <div><span>Evidence manifest</span><strong>{shortHash(current.manifestSha256, 8)}</strong><small>SHA-256 sealed manifest</small></div>
        <div><span>Issued</span><strong>{new Date(current.issuedAt).toLocaleString()}</strong><small>Signed payload is immutable after issuance.</small></div>
      </div>

      {current.status === 'REVOKED' ? <div className="notice error"><strong>RECEIPT REVOKED</strong><p>{current.revocationReason}</p></div> : null}
      {current.lastEvidenceIntegrity && current.lastEvidenceIntegrity !== 'MATCH' ? <div className="notice error"><strong>EVIDENCE INTEGRITY FAILURE</strong><p>Current stored evidence does not match the sealed manifest: {current.lastEvidenceIntegrity}.</p></div> : null}

      <div className="badge-row">
        <Link className="button primary" to={`/receipts/${current.id}`}>Open current receipt</Link>
        <button className="button ghost" disabled={deepCheck.isPending} onClick={() => deepCheck.mutate()}>{deepCheck.isPending ? 'Re-hashing…' : 'Verify integrity'}</button>
      </div>
      {deepCheck.data ? <div className={deepCheck.data.state === 'MATCH' ? 'notice' : 'notice error'}>Evidence deep-check: <strong>{deepCheck.data.state}</strong> · {deepCheck.data.files.length} sealed objects checked.</div> : null}
      {deepCheck.error ? <div className="notice error">{deepCheck.error.message}</div> : null}

      {receipts.data && receipts.data.length > 1 ? (
        <div className="callout">
          <strong>RECEIPT HISTORY · IMMUTABLE</strong>
          <p className="muted">Older engine decisions remain preserved. Superseded means replaced by a newer signed decision, not deleted or edited.</p>
          {receipts.data.map((item, index) => (
            <div className="challenge-row" key={item.id}>
              <div>
                <strong>{index === 0 ? 'Current' : 'Previous'} · {item.receiptNumber}</strong>
                <small>{item.engineVersion} · {new Date(item.issuedAt).toLocaleString()}</small>
              </div>
              <div className="badge-row">
                <span className={verdictBadgeClass(item.verdict)}>{item.verdict.replace(/_/g, ' ')}</span>
                <span className={receiptStatusBadgeClass(item.status)}>{item.status}</span>
              </div>
              <small>{item.signatureValid ? '✓ Signature valid' : `⚠ ${integrityLabel(item.signatureState)}`} · score {item.score.toFixed(2)} · confidence {Math.round(item.confidence * 100)}%</small>
              <Link className="button ghost" to={`/receipts/${item.id}`}>View receipt</Link>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  )
}
