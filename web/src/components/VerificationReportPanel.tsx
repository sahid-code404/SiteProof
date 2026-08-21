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
    return <article className="panel"><p className="eyebrow">SITEPROOF VERIFICATION</p><p>Preparing explainable verification result…</p></article>
  }
  if (verification.isError) {
    return <article className="panel"><p className="eyebrow">SITEPROOF VERIFICATION</p><div className="notice error">{verification.error.message}</div></article>
  }
  if (!verification.data) return null

  const data = verification.data
  if (data.status !== 'COMPLETED' || !data.verdict) {
    return (
      <article className="panel">
        <p className="eyebrow">SITEPROOF VERIFICATION</p>
        <h3>{words(data.status)}</h3>
        <p className="muted">The trust engine waits for required upstream evidence. It does not issue a premature score.</p>
        {canRecalculate ? (
          <button className="button ghost" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
            {recalculate.isPending ? 'Rechecking…' : 'Recalculate current version'}
          </button>
        ) : null}
      </article>
    )
  }

  const score = displayScore(data.score)
  return (
    <article className="panel">
      <p className="eyebrow">SITEPROOF VERIFICATION · EXPLAINABLE RESULT</p>
      <div className="definition-grid">
        <div>
          <span>Verification Score</span>
          <strong className="large-text">{score ?? '—'} / 100</strong>
          <small>Raw deterministic policy score; hard rules constrain verdict separately.</small>
        </div>
        <div>
          <span>Verdict</span>
          <strong className="large-text">{verdictLabel(data.verdict)}</strong>
          <small>{verdictMessage(data.verdict)}</small>
        </div>
        <div>
          <span>Overall confidence</span>
          <strong>{percentage(data.confidence)}</strong>
          <small>Reliability of the evidence used for this assessment.</small>
        </div>
        <div>
          <span>Policy</span>
          <strong>{data.policy?.name ?? '—'}</strong>
          <small>Policy {data.policy?.version ?? '—'} · {data.policy?.engineVersion ?? '—'}</small>
        </div>
      </div>

      {data.hardRules.length ? (
        <div className="notice error">
          <strong>Policy Override</strong>
          <p>{data.hardRules.join(' · ')}</p>
          <small>Automatic VERIFIED status was blocked by deterministic policy rules.</small>
        </div>
      ) : null}

      <div className="callout">
        <strong>SCORE BREAKDOWN</strong>
        <p className="muted">Signal scores are normalized to 0–1 before configured weighting. Confidence is shown separately.</p>
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
          <strong>HUMAN REVIEW DECISION</strong>
          <p className="muted">Human operational approval remains distinct from the automated SiteProof verdict.</p>
          {data.latestReview ? (
            <p><strong>Latest:</strong> {words(data.latestReview.decision)} · {data.latestReview.reason || 'No reviewer note supplied.'}</p>
          ) : null}
          <textarea
            rows={3}
            placeholder="Reviewer note (required for reject or recapture)"
            value={reviewReason}
            onChange={(event) => setReviewReason(event.target.value)}
          />
          <div className="badge-row">
            <button className="button primary" disabled={review.isPending} onClick={() => review.mutate('APPROVED')}>Approve</button>
            <button className="button danger" disabled={review.isPending || reviewReason.trim().length < 8} onClick={() => review.mutate('REJECTED')}>Reject</button>
            <button className="button ghost" disabled={review.isPending || reviewReason.trim().length < 8} onClick={() => review.mutate('RECAPTURE_REQUIRED')}>Request recapture</button>
          </div>
          {review.error ? <div className="notice error">{review.error.message}</div> : null}
        </div>
      ) : null}

      {canRecalculate ? (
        <div className="callout">
          <strong>ADMINISTRATOR</strong>
          <p className="muted">Same policy + engine calculation is idempotent. Historical results are preserved when a future policy or engine version changes.</p>
          <button className="button ghost" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
            {recalculate.isPending ? 'Rechecking…' : 'Recalculate current version'}
          </button>
          {recalculate.error ? <div className="notice error">{recalculate.error.message}</div> : null}
        </div>
      ) : null}
    </article>
  )
}
