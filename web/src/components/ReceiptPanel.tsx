import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getLatestVerificationSession } from '../lib/api'
import { getStoredUser } from '../lib/auth'
import { getSessionReceipt, issueSessionReceipt, verifyEvidence } from '../lib/receiptApi'
import { integrityLabel, shortHash } from '../lib/receipt'

export function ReceiptPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canIssue = role === 'ADMIN'
  const queryClient = useQueryClient()
  const session = useQuery({ queryKey: ['verification-session', inspectionId], queryFn: () => getLatestVerificationSession(inspectionId), refetchInterval: 5000 })
  const receipt = useQuery({ queryKey: ['receipt', session.data?.id], queryFn: () => getSessionReceipt(session.data!.id), enabled: Boolean(session.data?.id), refetchInterval: (query) => query.state.data ? false : 5000 })
  const issue = useMutation({ mutationFn: () => issueSessionReceipt(session.data!.id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['receipt', session.data?.id] }) })
  const deepCheck = useMutation({ mutationFn: () => verifyEvidence(receipt.data!.id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['receipt', session.data?.id] }) })

  if (!session.data) return null
  if (receipt.isLoading) return <article className="panel"><p className="eyebrow">CRYPTOGRAPHIC RECEIPT</p><p>Checking sealing status…</p></article>
  if (receipt.isError) return <article className="panel"><p className="eyebrow">CRYPTOGRAPHIC RECEIPT</p><div className="notice error">{receipt.error.message}</div></article>
  if (!receipt.data) {
    return <article className="panel"><p className="eyebrow">CRYPTOGRAPHIC RECEIPT</p><h3>Not issued yet</h3><p className="muted">A receipt is created only after a completed Phase 7 result and successful server-side evidence re-hash. Signing may also be disabled in local development.</p>{canIssue ? <button className="button ghost" disabled={issue.isPending} onClick={() => issue.mutate()}>{issue.isPending ? 'Sealing…' : 'Issue receipt'}</button> : null}{issue.error ? <div className="notice error">{issue.error.message}</div> : null}</article>
  }
  const data = receipt.data
  return <article className="panel">
    <p className="eyebrow">CRYPTOGRAPHIC RECEIPT · PHASE 8</p>
    <div className="definition-grid">
      <div><span>Receipt</span><strong>{data.receiptNumber}</strong><small>{data.receiptType.replace(/_/g, ' ')}</small></div>
      <div><span>Lifecycle</span><strong>{integrityLabel(data.status)}</strong><small>Cryptographic validity is evaluated separately.</small></div>
      <div><span>Signature</span><strong>{data.signatureValid ? '✓ VALID' : '⚠ INVALID'}</strong><small>{integrityLabel(data.signatureState)}</small></div>
      <div><span>Evidence manifest</span><strong>{shortHash(data.manifestSha256, 8)}</strong><small>SHA-256 · sealed server manifest</small></div>
      <div><span>Signing key</span><strong>{data.signingKeyId}</strong><small>{data.signatureAlgorithm}</small></div>
      <div><span>Issued</span><strong>{new Date(data.issuedAt).toLocaleString()}</strong><small>Receipt payload is immutable after issuance.</small></div>
    </div>
    {data.status === 'REVOKED' ? <div className="notice error"><strong>RECEIPT REVOKED</strong><p>{data.revocationReason}</p></div> : null}
    {data.lastEvidenceIntegrity && data.lastEvidenceIntegrity !== 'MATCH' ? <div className="notice error"><strong>EVIDENCE INTEGRITY FAILURE</strong><p>Current stored evidence does not match the sealed manifest: {data.lastEvidenceIntegrity}.</p></div> : null}
    <div className="badge-row"><Link className="button primary" to={`/receipts/${data.id}`}>View receipt</Link><button className="button ghost" disabled={deepCheck.isPending} onClick={() => deepCheck.mutate()}>{deepCheck.isPending ? 'Re-hashing…' : 'Verify integrity'}</button></div>
    {deepCheck.data ? <div className={deepCheck.data.state === 'MATCH' ? 'notice' : 'notice error'}>Evidence deep-check: <strong>{deepCheck.data.state}</strong> · {deepCheck.data.files.length} sealed objects checked.</div> : null}
    {deepCheck.error ? <div className="notice error">{deepCheck.error.message}</div> : null}
  </article>
}
