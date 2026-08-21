import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getLatestVerificationSession } from '../lib/api'
import { getStoredUser } from '../lib/auth'
import {
  getSessionVerification,
  recalculateSessionVerification,
  submitInspectionReview,
  type ReviewDecision,
} from '../lib/verificationApi'
import {
  contributionText,
  displayScore,
  signalLabel,
  signalStatusLabel,
  verdictLabel,
  verdictMessage,
} from '../lib/verification'

function percentage(value?: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

function words(value: string) {
  return value.replace(/_/g, ' ')
}

function verdictBadgeClass(verdict?: string | null) {
  if (verdict === 'VERIFIED') return 'badge badge-ready'
  if (verdict === 'FLAGGED') return 'badge badge-critical'
  if (verdict === 'REVIEW_REQUIRED') return 'badge badge-high'
  return 'badge'
}

export function VerificationReportPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canReview = role === 'ADMIN' || role === 'REVIEWER'
  const canRecalculate = role === 'ADMIN'
  const queryClient = useQueryClient()
  const [reviewReason, setReviewReason] = useState('')

  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })
  const verification = useQuery({
    queryKey: ['siteproof-verification', session.data?.id],
    queryFn: () => getSessionVerification(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return ['PENDING', 'WAITING_FOR_SIGNALS', 'CALCULATING'].includes(status ?? '') ? 3000 : false
    },
  })

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ['siteproof-verification', session.data?.id] })
    queryClient.invalidateQueries({ queryKey: ['inspection', inspectionId] })
    queryClient.invalidateQueries({ queryKey: ['inspections'] })
    queryClient.invalidateQueries({ queryKey: ['inspection-summary'] })
    queryClient.invalidateQueries({ queryKey: ['receipts', session.data?.id] })
  }

  const recalculate = useMutation({
    mutationFn: () => recalculateSessionVerification(session.data!.id),
    onSuccess: refresh,
  })
  const review = useMutation({
    mutationFn: (decision: ReviewDecision) =>
      submitInspectionReview(inspectionId, session.data!.id, decision, reviewReason),
    onSuccess: () => {
      setReviewReason('')
      refresh()
    },
  })

  if (!session.data) return null
  if (verification.isLoading) {
    return <article className="panel"><p className="eyebrow">AUTOMATED VERIFICATION</p><p>Preparing explainable verification result…</p></article>
  }
  if (verification.isError) {
    return <article className="panel"><p className="eyebrow">AUTOMATED VERIFICATION</p><div className="notice error">{verification.error.message}</div></article>
  }
  if (!verification.data) return null

  const data = verification.data
  if (data.status !== 'COMPLETED' || !data.verdict) {
    return (
      <article className="panel">
        <p className="eyebrow">AUTOMATED VERIFICATION · CURRENT STATE</p>
        <h3>{words(data.status)}</h3>
        <p className="muted">The trust engine is waiting for the required evidence set. No premature verdict or score is issued.</p>
        {canRecalculate ? (
          <button className="button ghost" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
            {recalculate.isPending ? 'Rechecking…' : 'Recalculate current engine'}
          </button>
        ) : null}
      </article>
    )
  }

  const score = displayScore(data.score)
  return (
    <article className="panel">
      <p className="eyebrow">AUTOMATED VERIFICATION · IMMUTABLE RESULT</p>
      <div className="badge-row">
        <span className={verdictBadgeClass(data.verdict)}>{verdictLabel(data.verdict)}</span>
        <span className="badge">CONFIDENCE {percentage(data.confidence)}</span>
        <span className="badge">{data.policy?.engineVersion ?? 'ENGINE UNKNOWN'}</span>
      </div>

      <div className="definition-grid">
        <div>
          <span>Final verdict</span>
          <strong className="large-text">{verdictLabel(data.verdict)}</strong>
          <small>{verdictMessage(data.verdict)}</small>
        </div>
        <div>
          <span>Verification score</span>
          <strong className="large-text">{score ?? '—'} / 100</strong>
          <small>Deterministic policy score before hard-rule constraints.</small>
        </div>
        <div>
          <span>Overall confidence</span>
          <strong className="large-text">{percentage(data.confidence)}</strong>
          <small>Reliability of the evidence used by the current engine.</small>
        </div>
        <div>
          <span>Engine & policy</span>
          <strong>{data.policy?.engineVersion ?? '—'}</strong>
          <small>{data.policy?.name ?? 'Policy'} · {data.policy?.version ?? '—'}</small>
        </div>
      </div>

      {data.hardRules.length ? (
        <div className="notice error">
          <strong>DETERMINISTIC POLICY OVERRIDE</strong>
          <p>{data.hardRules.join(' · ')}</p>
          <small>Automatic VERIFIED status was blocked by one or more hard rules.</small>
        </div>
      ) : (
        <div className="notice"><strong>No hard-rule override triggered.</strong> The verdict is based on the weighted evidence policy shown below.</div>
      )}

      <div className="callout">
        <strong>SCORE BREAKDOWN</strong>
        <p className="muted">Signal scores are normalized to 0–1 before weighting. Confidence is shown independently from score.</p>
        {data.signals.map((signal) => (
          <div className="challenge-row" key={signal.type}>
            <div>
              <strong>{signalLabel(signal.type)}</strong>
              <small>{signalStatusLabel(signal.status)}{signal.required ? ' · required' : ' · supporting'}</small>
            </div>
            <div>
              <strong>{contributionText(signal.contribution, signal.weight)}</strong>
              <small>confidence {percentage(signal.confidence)}</small>
            </div>
            <small>{signal.reasonSummary}</small>
          </div>
        ))}
      </div>

      <div className="callout">
        <strong>WHY THIS RESULT</strong>
        {data.summary ? <p>{data.summary}</p> : null}
        {data.summaryReasons.map((reason) => <p key={reason}>• {reason}</p>)}
        {data.warnings.map((warning) => <p key={warning}>⚠ {warning}</p>)}
      </div>

      {data.limitations.length ? (
        <div className="callout">
          <strong>LIMITATIONS</strong>
          {data.limitations.map((item) => <p className="muted" key={item}>{item}</p>)}
        </div>
      ) : null}

      {canReview ? (
        <div className="callout">
          <strong>REVIEWER DECISION · SEPARATE AUDIT EVENT</strong>
          <p className="muted">A reviewer decision never overwrites the automated result or its signed receipt. It is recorded as a separate operational action.</p>
          {data.latestReview ? (
            <p><strong>Latest reviewer action:</strong> {words(data.latestReview.decision)} · {data.latestReview.reason || 'No reviewer note supplied.'}</p>
          ) : null}
          <textarea
            rows={3}
            placeholder="Reviewer note (required for reject or recapture)"
            value={reviewReason}
            onChange={(event) => setReviewReason(event.target.value)}
          />
          <div className="badge-row">
            <button className="button primary" disabled={review.isPending} onClick={() => review.mutate('APPROVED')}>Accept verification</button>
            <button className="button danger" disabled={review.isPending || reviewReason.trim().length < 8} onClick={() => review.mutate('REJECTED')}>Reject</button>
            <button className="button ghost" disabled={review.isPending || reviewReason.trim().length < 8} onClick={() => review.mutate('RECAPTURE_REQUIRED')}>Request recapture</button>
          </div>
          {review.error ? <div className="notice error">{review.error.message}</div> : null}
        </div>
      ) : null}

      {canRecalculate ? (
        <div className="callout">
          <strong>ADMINISTRATOR</strong>
          <p className="muted">Recalculation is idempotent for the same policy and engine. When the engine version changes, historical results and receipts remain preserved.</p>
          <button className="button ghost" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
            {recalculate.isPending ? 'Rechecking…' : 'Recalculate current engine'}
          </button>
          {recalculate.error ? <div className="notice error">{recalculate.error.message}</div> : null}
        </div>
      ) : null}
    </article>
  )
}
