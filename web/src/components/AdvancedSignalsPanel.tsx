import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analyzeAdvancedSignals, getAdvancedSignals } from '../lib/advancedSignalsApi'
import { getLatestVerificationSession } from '../lib/api'
import { getStoredUser } from '../lib/auth'

function percent(value: number | null) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

function words(value: string) {
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
    return <article className="panel"><p className="eyebrow">Environment checks</p><p>Loading environment analysis…</p></article>
  }
  if (signals.isError) {
    return <article className="panel"><p className="eyebrow">Environment checks</p><div className="notice error">{signals.error.message}</div></article>
  }
  if (!signals.data) {
    return (
      <article className="panel">
        <p className="eyebrow">Environment checks</p>
        <h3>Not analyzed yet</h3>
        <p className="muted">Compares the capture environment and looks for unusual signal patterns.</p>
        {canAnalyze ? <button className="button ghost" disabled={analyze.isPending} onClick={() => analyze.mutate()}>{analyze.isPending ? 'Analyzing…' : 'Run analysis'}</button> : null}
        {analyze.error ? <div className="notice error">{analyze.error.message}</div> : null}
      </article>
    )
  }

  const data = signals.data
  return (
    <article className="panel">
      <p className="eyebrow">Environment checks</p>
      <div className="definition-grid">
        <div>
          <span>Continuity</span>
          <strong>{words(data.environmentStatus)}</strong>
          <small>{percent(data.environmentConsistencyScore)} consistency</small>
        </div>
        <div>
          <span>Environment risk</span>
          <strong>{percent(data.environmentRiskScore)}</strong>
          <small>{percent(data.environmentConfidence)} confidence</small>
        </div>
        <div>
          <span>Anomaly check</span>
          <strong>{words(data.statisticalAnomalyStatus)}</strong>
          <small>{percent(data.statisticalAnomalyScore)} anomaly score</small>
        </div>
        <div>
          <span>Method</span>
          <strong>Deterministic</strong>
          <small>{data.algorithmVersion}</small>
        </div>
      </div>

      <details className="evidence-details">
        <summary>Privacy & observations</summary>
        <div className="evidence-details-content">
          <p className="muted">Wi-Fi network names and raw BSSIDs are not stored. Session-scoped identifiers are used only for capture-to-capture comparison.</p>
          {data.reasonCodes.length ? <p><strong>Observations:</strong> {data.reasonCodes.map(words).join(' · ')}</p> : <p>No elevated environment warning found.</p>}
          {data.reasons.slice(0, 5).map((reason) => <p className="muted" key={reason}>• {reason}</p>)}
        </div>
      </details>

      {canAnalyze ? <button className="button ghost" disabled={analyze.isPending} onClick={() => analyze.mutate()}>{analyze.isPending ? 'Analyzing…' : 'Run again'}</button> : null}
      {analyze.error ? <div className="notice error">{analyze.error.message}</div> : null}
    </article>
  )
}
