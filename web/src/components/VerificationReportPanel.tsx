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
  roundedSiteProofScore,
  scoreContribution,
  verificationSignalLabel,
  verificationVerdictDescription,
  verificationVerdictLabel,
} from '../lib/verification'

function percentage(value?: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

export function VerificationReportPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canReview = role === 'ADMIN' || role === 'REVIEWER'
  const canRecalculate = role === 'ADMIN'
  const queryClient = useQueryClient()
  const [decision, setDecision] = useState<ReviewDecision>('APPROVED')
  const [reason, setReason] = useState('')

  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })
  const verification = useQuery({
    queryKey: ['siteproof-verification', session.data?.id],
    queryFn: () => getSessionVerification(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: 5000,
  })

  const recalculate = useMutation({
    mutationFn: () => recalculateSessionVerification(session.data!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['siteproof-verification', session.data?.id] })
    },
  })
  const review = useMutation({
    mutationFn: () => submitInspectionReview(inspectionId, session.data!.id, decision, reason),
    onSuccess: () => {
      setReason('')
      queryClient.invalidateQueries({ queryKey: ['siteproof-verification', session.data?.id] })
    },
  })

  if (!session.data) return null
  if (verification.isLoading) {
    return <article className="panel"><p className="eyebrow">SITEPROOF VERIFICATION</p><p className="muted">Waiting for the explainable verification engine…</p></article>
  }
  if (verification.isError) {
    return <article className="panel"><p className="eyebrow">SITEPROOF VERIFICATION</p><div className="notice error">{verification.error.message}</div></article>
  }
  if (!verification.data) return null

  const result = verification.data
  if (!result.detailed) {
    return (
      <article className="panel">
        <p className="eyebrow">VERIFICATION RESULT</p>
        <h3>{result.summary ?? 'Verification submitted'}</h3>
        <p className="muted">Detailed scoring and anti-spoofing diagnostics are available only to authorized reviewers.</p>
      </article>
    )
  }

  const score = roundedSiteProofScore(result.score)
  return (
    <article className="panel">
      <p className="eyebrow">SITEPROOF VERIFICATION · EXPLAINABLE TRUST ENGINE</p>
      <div className="definition-grid">
        <div>
          <span>SiteProof score</span>
          <strong className="large-text">{score == null ? '—' : `${score} / 100`}</strong>
          <small>Raw weighted evidence score; policy overrides constrain verdict rather than hiding score changes.</small>
        </div>
        <div>
          <span>Automated verdict</span>
          <strong className="large-text">{verificationVerdictLabel(result.verdict)}</strong>
          <small>{verificationVerdictDescription(result.verdict)}</small>
        </div>
        <div>
          <span>Overall evidence confidence</span>
          <strong>{percentage(result.confidence)}</strong>
          <small>Kept separate from the evidence-satisfaction score.</small>
        </div>
        <div>
          <span>Policy / engine</span>
          <strong>{result.policy ? `${result.policy.name} · v${result.policy.version}` : '—'}</strong>
          <small>{result.engineVersion ?? '—'} · calculation revision {result.calculationRevision ?? '—'}</small>
        </div>
      </div>

      {result.status !== 'COMPLETED' ? (
        <div className="callout">
          <strong>{result.status.replaceAll('_', ' ')}</strong>
          <p>{result.summary ?? 'Verification is waiting for upstream evidence.'}</p>
        </div>
      ) : null}

      {result.hardRules.length ? (
        <div className="callout">
          <strong>POLICY OVERRIDE</strong>
          <p>⚠ {result.hardRules.join(' · ')}</p>
          <small>Automatic VERIFIED status was constrained by a deterministic hard security rule.</small>
        </div>
      ) : null}

      {result.signals.length ? (
        <div className="callout">
          <strong>SCORE BREAKDOWN</strong>
          {result.signals.map((signal) => (
            <div className="challenge-row" key={signal.type}>
              <div>
                <strong>{verificationSignalLabel(signal.type)}</strong>
                <small>{signal.status} · {signal.required ? 'required' : 'optional'} · confidence {percentage(signal.confidence)}</small>
              </div>
              <div>
                <strong>{scoreContribution(signal.contribution, signal.effectiveWeight)}</strong>
                <small>signal score {Math.round(signal.score * 100)}%</small>
              </div>
              <small>{signal.reasonSummary}</small>
            </div>
          ))}
        </div>
      ) : null}

      {result.summaryReasons.length ? (
        <div className="callout">
          <strong>WHY THIS RESULT</strong>
          {result.summaryReasons.map((item) => <p key={item}>✓ {item}</p>)}
          {result.warnings.map((item) => <p key={item}>⚠ {item}</p>)}
        </div>
      ) : result.warnings.length ? (
        <div className="callout">
          <strong>VERIFICATION NOTES</strong>
          {result.warnings.map((item) => <p key={item}>⚠ {item}</p>)}
        </div>
      ) : null}

      {result.latestReview ? (
        <div className="callout">
          <strong>HUMAN REVIEW</strong>
          <p>{result.latestReview.decision} · {result.latestReview.reason}</p>
          <small>Human operational decision is stored separately from the automated SiteProof verdict.</small>
        </div>
      ) : null}

      {canReview && result.status === 'COMPLETED' ? (
        <div className="callout">
          <strong>REVIEW DECISION</strong>
          <p className="muted">Preserve the automated verdict and record a separate operational decision.</p>
          <select value={decision} onChange={(event) => setDecision(event.target.value as ReviewDecision)}>
            <option value="APPROVED">Approve</option>
            <option value="REJECTED">Reject</option>
            <option value="RECAPTURE_REQUIRED">Request recapture</option>
          </select>
          <textarea
            rows={3}
            placeholder="Reviewer reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <button
            className="button primary"
            disabled={reason.trim().length < 3 || review.isPending}
            onClick={() => review.mutate()}
          >
            {review.isPending ? 'Saving review…' : 'Record review decision'}
          </button>
          {review.isError ? <div className="notice error">{review.error.message}</div> : null}
        </div>
      ) : null}

      {canRecalculate ? (
        <button className="button ghost" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
          {recalculate.isPending ? 'Scheduling recalculation…' : 'Recalculate with active policy'}
        </button>
      ) : null}
    </article>
  )
}
