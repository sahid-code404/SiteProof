import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { getPublicReceipt } from '../lib/receiptApi'
import { integrityLabel, receiptIsHealthy } from '../lib/receipt'

export function PublicReceiptPage() {
  const { token = '' } = useParams()
  const receipt = useQuery({ queryKey: ['public-receipt', token], queryFn: () => getPublicReceipt(token), retry: false })

  if (receipt.isLoading) {
    return (
      <main className="public-receipt-page">
        <div className="public-receipt-card" role="status">
          <span className="brand-mark large" aria-hidden="true">SP</span>
          <h1>Checking receipt…</h1>
        </div>
      </main>
    )
  }

  if (receipt.isError || !receipt.data) {
    return (
      <main className="public-receipt-page">
        <div className="public-receipt-card">
          <span className="brand-mark large" aria-hidden="true">SP</span>
          <p className="eyebrow">Receipt check</p>
          <h1>Receipt unavailable</h1>
          <p>{receipt.error?.message ?? 'This receipt could not be checked.'}</p>
          <Link className="button ghost" to="/login">Go to SiteProof</Link>
        </div>
      </main>
    )
  }

  const data = receipt.data
  const healthy = receiptIsHealthy(data.signatureValid, data.receiptStatus, data.integrityState)

  return (
    <main className="public-receipt-page">
      <article className="public-receipt-card">
        <div className="public-receipt-brand">
          <span className="brand-mark large" aria-hidden="true">SP</span>
          <span>SiteProof</span>
        </div>

        <p className="eyebrow">Receipt check</p>
        <h1>{data.receiptNumber}</h1>

        <div className={healthy ? 'public-receipt-state valid' : 'public-receipt-state invalid'}>
          <strong>{healthy ? 'Receipt valid' : integrityLabel(data.integrityState)}</strong>
          <span>{healthy ? 'Signature and receipt status are valid.' : 'This receipt needs attention.'}</span>
        </div>

        <div className="public-receipt-grid">
          <div><span>Signature</span><strong>{data.signatureValid ? 'Valid' : 'Invalid'}</strong></div>
          <div><span>Status</span><strong>{data.receiptStatus}</strong></div>
          <div><span>Issued</span><strong>{new Date(data.issuedAt).toLocaleString()}</strong></div>
          {data.verdict ? <div><span>Result</span><strong>{integrityLabel(data.verdict)}</strong>{data.score ? <small>{data.score} / 100</small> : null}</div> : null}
        </div>

        <p className="muted public-receipt-note">This public view does not expose private inspection data, coordinates or inspector details.</p>
        <Link className="button ghost" to="/login">Open SiteProof</Link>
      </article>
    </main>
  )
}
