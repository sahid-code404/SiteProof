import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { getStoredUser } from '../lib/auth'
import { getReceipt, revokeReceipt, verifyEvidence } from '../lib/receiptApi'
import { integrityLabel, shortHash } from '../lib/receipt'

export function ReceiptDetailPage() {
  const { id = '' } = useParams()
  const canRevoke = getStoredUser()?.role === 'ADMIN'
  const queryClient = useQueryClient()
  const [reason, setReason] = useState('')
  const receipt = useQuery({ queryKey: ['receipt-detail', id], queryFn: () => getReceipt(id) })
  const verify = useMutation({
    mutationFn: () => verifyEvidence(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['receipt-detail', id] }),
  })
  const revoke = useMutation({
    mutationFn: () => revokeReceipt(id, reason),
    onSuccess: () => {
      setReason('')
      queryClient.invalidateQueries({ queryKey: ['receipt-detail', id] })
    },
  })

  if (receipt.isLoading) return <div className="loading-block">Loading receipt…</div>
  if (receipt.isError || !receipt.data) return <div className="notice error">{receipt.error?.message ?? 'Receipt not found'}</div>

  const data = receipt.data

  function downloadPortableReceipt() {
    const portable = {
      payload: data.canonicalPayload,
      payloadSha256: data.payloadSha256,
      signature: data.signature,
      algorithm: data.signatureAlgorithm,
      signingKeyId: data.signingKeyId,
    }
    const blob = new Blob([JSON.stringify(portable, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${data.receiptNumber}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <section className="page-heading split-heading">
        <div>
          <p className="eyebrow">Receipt</p>
          <h1>{data.receiptNumber}</h1>
          <p>Signed record for this verification result.</p>
        </div>
        <div className="heading-actions">
          <button className="button ghost" type="button" onClick={() => window.print()}>Print</button>
          <button className="button ghost" type="button" onClick={downloadPortableReceipt}>Download JSON</button>
        </div>
      </section>

      {data.status === 'REVOKED' ? <div className="notice error"><strong>Receipt revoked</strong><p>{data.revocationReason}</p></div> : null}

      <article className="panel receipt-detail-page">
        <div className="receipt-detail-summary">
          <div>
            <span>Result</span>
            <strong>{data.verdict.replace(/_/g, ' ')}</strong>
            <small>{data.score.toFixed(2)} / 100 · {Math.round(data.confidence * 100)}% confidence</small>
          </div>
          <div>
            <span>Signature</span>
            <strong>{data.signatureValid ? 'Valid' : 'Invalid'}</strong>
            <small>{integrityLabel(data.signatureState)}</small>
          </div>
          <div>
            <span>Evidence</span>
            <strong>{data.lastEvidenceIntegrity ?? 'Not checked'}</strong>
            <small>{data.lastEvidenceCheckAt ? new Date(data.lastEvidenceCheckAt).toLocaleString() : 'Run a check below'}</small>
          </div>
        </div>

        <div className="receipt-actions">
          <button className="button primary" disabled={verify.isPending} onClick={() => verify.mutate()}>{verify.isPending ? 'Checking…' : 'Verify evidence'}</button>
          {data.lookupToken ? <Link className="button ghost" to={`/verify/${data.lookupToken}`}>Public view</Link> : null}
        </div>

        {verify.data ? (
          <div className={verify.data.state === 'MATCH' ? 'notice' : 'notice error'}>
            <strong>{verify.data.state}</strong>
            <p>{verify.data.files.length} evidence files checked.</p>
          </div>
        ) : null}
        {verify.error ? <div className="notice error">{verify.error.message}</div> : null}

        <details className="evidence-details">
          <summary>Receipt details</summary>
          <div className="evidence-details-content receipt-detail-list">
            <div><span>Status</span><strong>{data.status}</strong></div>
            <div><span>Engine</span><strong>{data.engineVersion}</strong></div>
            <div><span>Policy</span><strong>{data.policyVersion}</strong></div>
            <div><span>Manifest</span><strong>{shortHash(data.manifestSha256)}</strong></div>
            <div><span>Payload</span><strong>{shortHash(data.payloadSha256)}</strong></div>
            <div><span>Signing key</span><strong>{data.signingKeyId}</strong></div>
          </div>
        </details>

        {verify.data ? (
          <details className="evidence-details">
            <summary>Evidence check details</summary>
            <div className="evidence-details-content">
              {verify.data.files.map((file) => (
                <div className="receipt-file-check" key={file.evidenceFileId}>
                  <strong>{file.type}</strong>
                  <span>{file.state}</span>
                  <small>Expected {shortHash(file.expectedSha256, 7)}{file.observedSha256 ? ` · observed ${shortHash(file.observedSha256, 7)}` : ''}</small>
                </div>
              ))}
            </div>
          </details>
        ) : null}

        <details className="evidence-details">
          <summary>Signed payload</summary>
          <div className="evidence-details-content">
            <pre className="receipt-code">{JSON.stringify(data.canonicalPayload, null, 2)}</pre>
          </div>
        </details>

        <details className="evidence-details">
          <summary>What this receipt proves</summary>
          <div className="evidence-details-content">
            <p className="muted">The receipt confirms the integrity of the SiteProof verification record and the evidence manifest at the time it was issued. It does not claim to prevent every possible form of capture fraud.</p>
          </div>
        </details>

        {canRevoke && data.status !== 'REVOKED' ? (
          <details className="evidence-details danger-details">
            <summary>Revoke receipt</summary>
            <div className="evidence-details-content">
              <textarea rows={3} placeholder="Reason for revocation" value={reason} onChange={(event) => setReason(event.target.value)} />
              <button className="button danger" disabled={reason.trim().length < 3 || revoke.isPending} onClick={() => revoke.mutate()}>{revoke.isPending ? 'Revoking…' : 'Revoke receipt'}</button>
              {revoke.error ? <div className="notice error">{revoke.error.message}</div> : null}
            </div>
          </details>
        ) : null}
      </article>
    </>
  )
}
