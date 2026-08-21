import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { getPublicReceipt } from '../lib/receiptApi'
import { integrityLabel, receiptIsHealthy } from '../lib/receipt'

export function PublicReceiptPage() {
  const { token = '' } = useParams()
  const receipt = useQuery({ queryKey: ['public-receipt', token], queryFn: () => getPublicReceipt(token), retry: false })
  if (receipt.isLoading) return <div className="login-page"><div className="login-panel"><div className="center-card"><h2>Verifying SiteProof receipt…</h2></div></div></div>
  if (receipt.isError || !receipt.data) return <div className="login-page"><div className="login-panel"><div className="center-card"><p className="eyebrow">SITEPROOF RECEIPT VERIFICATION</p><h2>Receipt unavailable</h2><p>{receipt.error?.message ?? 'The receipt could not be verified.'}</p><Link to="/login">Return to SiteProof</Link></div></div></div>
  const data = receipt.data
  const healthy = receiptIsHealthy(data.signatureValid, data.receiptStatus, data.integrityState)
  return <div className="login-page"><div className="login-visual"><div className="login-copy"><p className="eyebrow">INDEPENDENT RECEIPT CHECK</p><h1>SiteProof</h1><p>A limited public view confirms the cryptographic signature and current receipt lifecycle without exposing private evidence, coordinates, or inspector identity.</p></div></div><div className="login-panel"><article className="panel public-receipt"><p className="eyebrow">SITEPROOF RECEIPT VERIFICATION</p><h2>{data.receiptNumber}</h2><div className={healthy ? 'callout' : 'notice error'}><strong>{healthy ? '✓ Cryptographic receipt valid' : `⚠ ${integrityLabel(data.integrityState)}`}</strong></div><div className="definition-grid"><div><span>Signature</span><strong>{data.signatureValid ? 'VALID' : 'INVALID'}</strong><small>{integrityLabel(data.signatureState)}</small></div><div><span>Status</span><strong>{data.receiptStatus}</strong></div><div><span>Issued</span><strong>{new Date(data.issuedAt).toLocaleString()}</strong></div>{data.verdict ? <div><span>Verification result</span><strong>{integrityLabel(data.verdict)}</strong><small>{data.score ? `${data.score} / 100` : ''}</small></div> : null}</div><p className="muted">Minimal privacy mode intentionally omits private inspection data and may omit score/verdict.</p><Link className="button ghost" to="/login">Open SiteProof</Link></article></div></div>
}
