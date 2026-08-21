import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analyzeAdvancedSecurity, getAdvancedSecurity } from '../lib/advancedSecurityApi'
import { getLatestVerificationSession } from '../lib/api'
import { getStoredUser } from '../lib/auth'

function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

function riskText(value: string) {
  return value.replace(/_/g, ' ')
}

function SignalCard({ label, risk }: { label: string; risk: number }) {
  return <div><span>{label}</span><strong>{percent(risk)} risk</strong></div>
}

export function AdvancedSecurityPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canAnalyze = role === 'ADMIN' || role === 'REVIEWER'
  const queryClient = useQueryClient()
  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })
  const security = useQuery({
    queryKey: ['advanced-security', session.data?.id],
    queryFn: () => getAdvancedSecurity(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: (query) => query.state.data ? false : 5000,
  })
  const analyze = useMutation({
    mutationFn: () => analyzeAdvancedSecurity(session.data!.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['advanced-security', session.data?.id] }),
  })

  if (!session.data) return null
  if (security.isLoading) {
    return <article className="panel"><p className="eyebrow">ADVANCED SECURITY · PHASE 9</p><p>Checking anti-spoofing analysis…</p></article>
  }
  if (security.isError) {
    return <article className="panel"><p className="eyebrow">ADVANCED SECURITY · PHASE 9</p><div className="notice error">{security.error.message}</div></article>
  }
  if (!security.data) {
    return <article className="panel">
      <p className="eyebrow">ADVANCED SECURITY · PHASE 9</p>
      <h3>Not analyzed yet</h3>
      <p className="muted">Checks location spoof indicators, sensor-stream anomalies, replay artifacts, exact evidence reuse, and available device-integrity metadata.</p>
      {canAnalyze ? <button className="button ghost" disabled={analyze.isPending} onClick={() => analyze.mutate()}>{analyze.isPending ? 'Analyzing…' : 'Run security analysis'}</button> : null}
      {analyze.error ? <div className="notice error">{analyze.error.message}</div> : null}
    </article>
  }

  const data = security.data
  return <article className="panel">
    <p className="eyebrow">ADVANCED SECURITY · PHASE 9</p>
    <div className="definition-grid">
      <div><span>Overall anti-spoofing risk</span><strong className="large-text">{riskText(data.overallRisk)}</strong><small>Confidence {percent(data.confidence)}</small></div>
      <div><span>Device integrity</span><strong>{riskText(data.deviceIntegrityStatus)}</strong><small>{percent(data.deviceRiskScore)} local risk</small></div>
      <SignalCard label="Location spoof risk" risk={data.locationRiskScore} />
      <SignalCard label="Sensor anomaly risk" risk={data.sensorAnomalyScore} />
      <SignalCard label="Replay / recapture risk" risk={data.replayRiskScore} />
      <SignalCard label="Exact evidence reuse" risk={data.evidenceReuseScore} />
    </div>
    {data.reasonCodes.length ? <div className="callout"><strong>Security observations</strong><p>{data.reasonCodes.map(riskText).join(' · ')}</p></div> : <div className="callout"><strong>No material anti-spoofing warning detected.</strong></div>}
    {data.reasons.slice(0, 5).map((reason) => <p className="muted" key={reason}>• {reason}</p>)}
    <div className="badge-row"><span className="badge">{data.algorithmVersion}</span>{canAnalyze ? <button className="button ghost" disabled={analyze.isPending} onClick={() => analyze.mutate()}>{analyze.isPending ? 'Re-analyzing…' : 'Re-run analysis'}</button> : null}</div>
    {analyze.error ? <div className="notice error">{analyze.error.message}</div> : null}
  </article>
}
