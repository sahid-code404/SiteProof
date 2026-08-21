import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analyzeAdvancedSignals, getAdvancedSignals } from '../lib/advancedSignalsApi'
import { getLatestVerificationSession } from '../lib/api'
import { getStoredUser } from '../lib/auth'

function percent(value: number | null) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

function label(value: string) {
  return value.replace(/_/g, ' ')
}

export function AdvancedSignalsPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canAnalyze = role === 'ADMIN' || role === 'REVIEWER'
  const queryClient = useQueryClient()
  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })
  const signals = useQuery({
    queryKey: ['advanced-signals', session.data?.id],
    queryFn: () => getAdvancedSignals(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: (query) => query.state.data ? false : 5000,
  })
  const analyze = useMutation({
    mutationFn: () => analyzeAdvancedSignals(session.data!.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['advanced-signals', session.data?.id] }),
  })

  if (!session.data) return null
  if (signals.isLoading) {
    return <article className="panel"><p className="eyebrow">ADVANCED SIGNALS · PHASE 10</p><p>Checking environment and anomaly intelligence…</p></article>
  }
  if (signals.isError) {
    return <article className="panel"><p className="eyebrow">ADVANCED SIGNALS · PHASE 10</p><div className="notice error">{signals.error.message}</div></article>
  }
  if (!signals.data) {
    return <article className="panel">
      <p className="eyebrow">ADVANCED SIGNALS · PHASE 10</p>
      <h3>Not analyzed yet</h3>
      <p className="muted">Adds privacy-preserving Wi-Fi continuity and deterministic statistical anomaly scoring. Wi-Fi is supporting evidence only and cannot fail verification by itself.</p>
      {canAnalyze ? <button className="button ghost" disabled={analyze.isPending} onClick={() => analyze.mutate()}>{analyze.isPending ? 'Analyzing…' : 'Run advanced signals'}</button> : null}
      {analyze.error ? <div className="notice error">{analyze.error.message}</div> : null}
    </article>
  }

  const data = signals.data
  return <article className="panel">
    <p className="eyebrow">ADVANCED SIGNALS · PHASE 10</p>
    <div className="definition-grid">
      <div>
        <span>Environment continuity</span>
        <strong>{label(data.environmentStatus)}</strong>
        <small>{percent(data.environmentConsistencyScore)} consistency · confidence {percent(data.environmentConfidence)}</small>
      </div>
      <div>
        <span>Environment risk</span>
        <strong>{percent(data.environmentRiskScore)}</strong>
        <small>Supporting evidence only</small>
      </div>
      <div>
        <span>Statistical anomaly</span>
        <strong>{label(data.statisticalAnomalyStatus)}</strong>
        <small>{percent(data.statisticalAnomalyScore)} anomaly · confidence {percent(data.statisticalAnomalyConfidence)}</small>
      </div>
      <div>
        <span>Model type</span>
        <strong>Deterministic</strong>
        <small>No trained black-box model</small>
      </div>
    </div>
    <div className="callout">
      <strong>Privacy boundary</strong>
      <p>SSID and raw BSSID are never stored. Nearby access points are session-scoped SHA-256 identifiers used only to compare the start and end of this live capture.</p>
    </div>
    {data.reasonCodes.length ? <div className="callout"><strong>Advanced observations</strong><p>{data.reasonCodes.map(label).join(' · ')}</p></div> : <div className="callout"><strong>No elevated advanced-signal warning detected.</strong></div>}
    {data.reasons.slice(0, 5).map((reason) => <p className="muted" key={reason}>• {reason}</p>)}
    <div className="badge-row"><span className="badge">{data.algorithmVersion}</span>{canAnalyze ? <button className="button ghost" disabled={analyze.isPending} onClick={() => analyze.mutate()}>{analyze.isPending ? 'Re-analyzing…' : 'Re-run analysis'}</button> : null}</div>
    {analyze.error ? <div className="notice error">{analyze.error.message}</div> : null}
  </article>
}
