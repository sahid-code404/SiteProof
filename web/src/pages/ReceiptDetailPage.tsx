import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { getStoredUser } from '../lib/auth'
import { getReceipt, revokeReceipt, verifyEvidence } from '../lib/receiptApi'
import { integrityLabel, shortHash } from '../lib/receipt'

export function ReceiptDetailPage() {
  const { id = '' } = useParams()
  const role = getStoredUser()?.role
  const canRevoke = role === 'ADMIN'
  const queryClient = useQueryClient()
  const [reason, setReason] = useState('')
  const receipt = useQuery({ queryKey: ['receipt-detail', id], queryFn: () => getReceipt(id) })
  const verify = useMutation({ mutationFn: () => verifyEvidence(id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['receipt-detail', id] }) })
  const revoke = useMutation({ mutationFn: () => revokeReceipt(id, reason), onSuccess: () => { setReason(''); queryClient.invalidateQueries({ queryKey: ['receipt-detail', id] }) } })

  if (receipt.isLoading) return <div className="loading-block">Loading signed receipt…</div>
  if (receipt.isError || !receipt.data) return <div className="notice error">{receipt.error?.message ?? 'Receipt not found'}</div>
  const data = receipt.data

  function downloadPortableReceipt() {
    const portable = { payload: data.canonicalPayload, payloadSha256: data.payloadSha256, signature: data.signature, algorithm: data.signatureAlgorithm, signingKeyId: data.signingKeyId }
    const blob = new Blob([JSON.stringify(portable, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${data.receiptNumber}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return <>
    <section className="page-heading split-heading"><div><p className="eyebrow">SITEPROOF RECEIPT</p><h1>{data.receiptNumber}</h1><p>Cryptographic record of the sealed evidence manifest and exact verification result.</p></div><div className="badge-row"><button className="button ghost" onClick={() => window.print()}>Print</button><button className="button ghost" onClick={downloadPortableReceipt}>Download JSON</button></div></section>
    {data.status === 'REVOKED' ? <div className="notice error"><strong>RECEIPT REVOKED</strong><p>{data.revocationReason}</p></div> : null}
    <article className="panel">
      <div className="definition-grid">
        <div><span>Verification</span><strong className="large-text">{data.verdict.replace(/_/g, ' ')}</strong><small>{data.score.toFixed(2)} / 100 · confidence {Math.round(data.confidence * 100)}%</small></div>
        <div><span>Signature</span><strong>{data.signatureValid ? '✓ VALID' : '⚠ INVALID'}</strong><small>{integrityLabel(data.signatureState)}</small></div>
        <div><span>Receipt integrity</span><strong>{integrityLabel(data.integrityState)}</strong><small>Lifecycle status: {data.status}</small></div>
        <div><span>Evidence integrity</span><strong>{data.lastEvidenceIntegrity ?? 'NOT CHECKED'}</strong><small>{data.lastEvidenceCheckAt ? `Checked ${new Date(data.lastEvidenceCheckAt).toLocaleString()}` : 'Run a deep storage re-hash below.'}</small></div>
        <div><span>Manifest SHA-256</span><strong>{shortHash(data.manifestSha256)}</strong><small>{data.manifestSha256}</small></div>
        <div><span>Payload SHA-256</span><strong>{shortHash(data.payloadSha256)}</strong><small>{data.payloadSha256}</small></div>
        <div><span>Policy / engine</span><strong>{data.policyVersion}</strong><small>{data.engineVersion}</small></div>
        <div><span>Signing key</span><strong>{data.signingKeyId}</strong><small>{data.signatureAlgorithm}</small></div>
      </div>
      <div className="badge-row"><button className="button primary" disabled={verify.isPending} onClick={() => verify.mutate()}>{verify.isPending ? 'Re-hashing evidence…' : 'Verify current evidence'}</button>{data.lookupToken ? <Link className="button ghost" to={`/verify/${data.lookupToken}`}>Open public verification</Link> : null}</div>
      {verify.data ? <div className={verify.data.state === 'MATCH' ? 'callout' : 'notice error'}><strong>Deep evidence check: {verify.data.state}</strong>{verify.data.files.map((file) => <p key={file.evidenceFileId}>{file.type}: {file.state} · expected {shortHash(file.expectedSha256, 7)}{file.observedSha256 ? ` · observed ${shortHash(file.observedSha256, 7)}` : ''}</p>)}</div> : null}
      {verify.error ? <div className="notice error">{verify.error.message}</div> : null}
      <details className="callout"><summary><strong>Canonical signed payload</strong></summary><pre className="receipt-code">{JSON.stringify(data.canonicalPayload, null, 2)}</pre></details>
      <div className="callout"><strong>SECURITY SCOPE</strong><p className="muted">This receipt confirms integrity of the SiteProof verification record and sealed evidence manifest at issuance. It is not an absolute guarantee against every possible capture spoofing or fraud technique.</p></div>
      {canRevoke && data.status !== 'REVOKED' ? <div className="callout"><strong>ADMINISTRATIVE REVOCATION</strong><p className="muted">Revocation preserves the signed record and its cryptographic history.</p><textarea rows={3} placeholder="Reason for revocation" value={reason} onChange={(event) => setReason(event.target.value)} /><button className="button danger" disabled={reason.trim().length < 3 || revoke.isPending} onClick={() => revoke.mutate()}>{revoke.isPending ? 'Revoking…' : 'Revoke receipt'}</button>{revoke.error ? <div className="notice error">{revoke.error.message}</div> : null}</div> : null}
    </article>
  </>
}
