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
    mutationFn: (decision: ReviewDecision) => submitInspectionReview(inspectionId, session.data!.id, decision, reviewReason),
    onSuccess: () => {
      setReviewReason('')
      refresh()
    },
  })

  if (!session.data) return null
  if (verification.isLoading) {
    return <article className="panel"><p className="eyebrow">Verification</p><p>Preparing result…</p></article>
  }
  if (verification.isError) {
    return <article className="panel"><p className="eyebrow">Verification</p><div className="notice error">{verification.error.message}</div></article>
  }
  if (!verification.data) return null

  const data = verification.data
  if (data.status !== 'COMPLETED' || !data.verdict) {
    return (
      <article className="panel">
        <p className="eyebrow">Verification</p>
        <h2>{words(data.status)}</h2>
        <p className="muted">Waiting for the evidence needed to calculate a result.</p>
        {canRecalculate ? (
          <button className="button ghost" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
            {recalculate.isPending ? 'Checking…' : 'Check again'}
          </button>
        ) : null}
      </article>
    )
  }

  const score = displayScore(data.score)

  return (
    <article className="panel verification-summary-panel">
      <div className="verification-summary-heading">
        <div>
          <p className="eyebrow">Verification</p>
          <h2>{verdictLabel(data.verdict)}</h2>
          <p className="muted">{verdictMessage(data.verdict)}</p>
        </div>
        <span className={verdictBadgeClass(data.verdict)}>{verdictLabel(data.verdict)}</span>
      </div>

      <div className="verification-key-metrics">
        <div><span>Score</span><strong>{score ?? '—'} / 100</strong></div>
        <div><span>Confidence</span><strong>{percentage(data.confidence)}</strong></div>
        <div><span>Engine</span><strong>{data.policy?.engineVersion ?? '—'}</strong></div>
      </div>

      {data.hardRules.length ? (
        <div className="notice error">
          <strong>Policy rule triggered</strong>
          <p>{data.hardRules.join(' · ')}</p>
        </div>
      ) : null}

      {canReview ? (
        <div className="review-decision-box">
          <div>
            <strong>Reviewer decision</strong>
            <p className="muted">Reviewer actions are stored separately from the automated result.</p>
          </div>
          {data.latestReview ? (
            <p><strong>{words(data.latestReview.decision)}</strong>{data.latestReview.reason ? ` · ${data.latestReview.reason}` : ''}</p>
          ) : null}
          <textarea
            rows={2}
            placeholder="Add a note for reject or recapture"
            value={reviewReason}
            onChange={(event) => setReviewReason(event.target.value)}
          />
          <div className="review-decision-actions">
            <button className="button primary" disabled={review.isPending} onClick={() => review.mutate('APPROVED')}>Accept</button>
            <button className="button ghost" disabled={review.isPending || reviewReason.trim().length < 8} onClick={() => review.mutate('RECAPTURE_REQUIRED')}>Recapture</button>
            <button className="button danger" disabled={review.isPending || reviewReason.trim().length < 8} onClick={() => review.mutate('REJECTED')}>Reject</button>
          </div>
          {review.error ? <div className="notice error">{review.error.message}</div> : null}
        </div>
      ) : null}

      <details className="evidence-details">
        <summary>How this result was calculated</summary>
        <div className="evidence-details-content">
          {data.summary ? <p>{data.summary}</p> : null}

          <div className="signal-breakdown-list">
            {data.signals.map((signal) => (
              <div className="signal-breakdown-row" key={signal.type}>
                <div>
                  <strong>{signalLabel(signal.type)}</strong>
                  <small>{signalStatusLabel(signal.status)} · {signal.required ? 'required' : 'supporting'}</small>
                </div>
                <div>
                  <strong>{contributionText(signal.contribution, signal.weight)}</strong>
                  <small>{percentage(signal.confidence)} confidence</small>
                </div>
                <p>{signal.reasonSummary}</p>
              </div>
            ))}
          </div>

          {data.summaryReasons.length ? (
            <div>
              <strong>Key reasons</strong>
              {data.summaryReasons.map((reason) => <p key={reason}>• {reason}</p>)}
            </div>
          ) : null}

          {data.warnings.length ? (
            <div>
              <strong>Warnings</strong>
              {data.warnings.map((warning) => <p key={warning}>• {warning}</p>)}
            </div>
          ) : null}

          {data.limitations.length ? (
            <div>
              <strong>Limitations</strong>
              {data.limitations.map((item) => <p className="muted" key={item}>{item}</p>)}
            </div>
          ) : null}
        </div>
      </details>

      {canRecalculate ? (
        <details className="evidence-details admin-details">
          <summary>Admin tools</summary>
          <div className="evidence-details-content">
            <p className="muted">Recalculate using the current verification engine. Previous results stay in history.</p>
            <button className="button ghost" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
              {recalculate.isPending ? 'Checking…' : 'Recalculate'}
            </button>
            {recalculate.error ? <div className="notice error">{recalculate.error.message}</div> : null}
          </div>
        </details>
      ) : null}
    </article>
  )
}
