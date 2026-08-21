import { useQuery } from '@tanstack/react-query'
import {
  getLatestVerificationSession,
  getSessionChallenges,
  getSessionEvidence,
  getSessionVisualAnalysis,
  type ChallengeTimelineItem,
  type VisualChallengeAnalysis,
} from '../lib/api'
import { getSessionFusionAnalysis, type FusionChallengeAnalysis } from '../lib/fusionApi'
import { consistencyLabel, fusionAnalysisLabel } from '../lib/fusion'
import { getStoredUser } from '../lib/auth'
import { FusionMotionChart } from './FusionMotionChart'

function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function formatDuration(ms?: number | null) {
  if (!ms) return '—'
  return `${Math.round(ms / 1000)} sec`
}

function challengeLabel(type: ChallengeTimelineItem['type']) {
  return {
    ROTATE_RIGHT: 'Rotate right',
    ROTATE_LEFT: 'Rotate left',
    TILT_UP: 'Tilt up',
    TILT_DOWN: 'Tilt down',
  }[type]
}

function resultLabel(result?: ChallengeTimelineItem['result'] | null) {
  if (result === 'PASS') return 'Pass'
  if (result === 'FAIL') return 'Fail'
  if (result === 'INCONCLUSIVE') return 'Inconclusive'
  return 'In progress'
}

function visualStatus(value: VisualChallengeAnalysis['status']) {
  if (value === 'SUCCESS') return 'Motion found'
  if (value === 'INCONCLUSIVE') return 'Inconclusive'
  if (value === 'FAILED') return 'Failed'
  if (value === 'PROCESSING') return 'Processing'
  return 'Pending'
}

function metricNumber(value: unknown, digits = 1) {
  return typeof value === 'number' ? value.toFixed(digits) : '—'
}

function percentage(value: unknown) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

function signedMilliseconds(value?: number | null) {
  if (typeof value !== 'number') return '—'
  return `${value >= 0 ? '+' : ''}${Math.round(value)} ms`
}

function fusionChallengeTitle(analysis: FusionChallengeAnalysis, challenges: ChallengeTimelineItem[]) {
  const challenge = challenges.find((item) => item.id === analysis.challengeId)
  return challenge ? `${challenge.sequenceNumber}. ${challengeLabel(challenge.type)}` : challengeLabel(analysis.challengeType)
}

function evidenceState(value: boolean) {
  return value ? 'Received' : 'Waiting'
}

export function VerificationSessionPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canReviewAnalysis = role === 'ADMIN' || role === 'REVIEWER'

  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })

  const evidence = useQuery({
    queryKey: ['verification-evidence', session.data?.id],
    queryFn: () => getSessionEvidence(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: ['UPLOADED', 'PROCESSING'].includes(session.data?.status ?? '') ? false : 5000,
  })

  const challenges = useQuery({
    queryKey: ['verification-challenges', session.data?.id],
    queryFn: () => getSessionChallenges(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: ['UPLOADED', 'PROCESSING'].includes(session.data?.status ?? '') ? false : 2000,
  })

  const visual = useQuery({
    queryKey: ['visual-analysis', session.data?.id],
    queryFn: () => getSessionVisualAnalysis(session.data!.id),
    enabled: canReviewAnalysis && Boolean(session.data?.id) && ['UPLOADED', 'PROCESSING'].includes(session.data?.status ?? ''),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'PROCESSING' || status === 'PENDING' ? 3000 : false
    },
  })

  const fusion = useQuery({
    queryKey: ['fusion-analysis', session.data?.id],
    queryFn: () => getSessionFusionAnalysis(session.data!.id),
    enabled: canReviewAnalysis && Boolean(session.data?.id) && ['UPLOADED', 'PROCESSING'].includes(session.data?.status ?? ''),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'PROCESSING' || status === 'PENDING' ? 3000 : false
    },
  })

  if (session.isLoading) return <article className="panel"><p className="eyebrow">Capture details</p><p className="muted">Loading capture…</p></article>
  if (session.isError) return <article className="panel"><p className="eyebrow">Capture details</p><div className="notice error">{session.error.message}</div></article>
  if (!session.data) return <article className="panel"><p className="eyebrow">Capture details</p><p className="muted">No live capture has been started.</p></article>

  const item = session.data
  const challengeItems = challenges.data?.items ?? []
  const latestAttempts = Array.from(
    challengeItems.reduce((map, challenge) => {
      const existing = map.get(challenge.sequenceNumber)
      if (!existing || challenge.attemptNumber > existing.attemptNumber) map.set(challenge.sequenceNumber, challenge)
      return map
    }, new Map<number, ChallengeTimelineItem>()).values(),
  ).sort((a, b) => a.sequenceNumber - b.sequenceNumber)

  const passCount = latestAttempts.filter((challenge) => challenge.result === 'PASS').length
  const failCount = latestAttempts.filter((challenge) => challenge.result === 'FAIL').length
  const inconclusiveCount = latestAttempts.filter((challenge) => challenge.result === 'INCONCLUSIVE').length

  return (
    <article className="panel capture-details-panel">
      <p className="eyebrow">Capture details</p>

      <div className="verification-key-metrics">
        <div><span>Status</span><strong>{item.status.replace(/_/g, ' ')}</strong></div>
        <div><span>Captured</span><strong>{formatDate(item.captureEndedAt)}</strong></div>
        <div><span>Duration</span><strong>{formatDuration(item.captureDurationMs)}</strong></div>
      </div>

      <div className="capture-evidence-strip">
        <span>Video <strong>{evidenceState(item.evidence.video)}</strong></span>
        <span>Motion <strong>{evidenceState(item.evidence.sensorData)}</strong></span>
        <span>Location <strong>{evidenceState(item.evidence.locationData)}</strong></span>
        <span>Manifest <strong>{evidenceState(item.evidence.manifest)}</strong></span>
      </div>

      <section className="capture-analysis-section">
        <div className="capture-analysis-heading">
          <div>
            <strong>Movement steps</strong>
            <p className="muted">{passCount} passed · {failCount} failed · {inconclusiveCount} inconclusive</p>
          </div>
        </div>

        {challenges.isLoading ? <p className="muted">Loading movement steps…</p> : null}
        {!challenges.isLoading && latestAttempts.length === 0 ? <p className="muted">No movement step has been recorded yet.</p> : null}

        {latestAttempts.map((challenge) => (
          <details className="capture-step" key={`${challenge.sequenceNumber}-${challenge.attemptNumber}`}>
            <summary>
              <span><strong>{challenge.sequenceNumber}. {challengeLabel(challenge.type)}</strong><small>Target {Math.round(challenge.parameters.targetDegrees)}° · attempt {challenge.attemptNumber}</small></span>
              <span>{resultLabel(challenge.result)}</span>
            </summary>
            {challenge.result ? (
              <div className="capture-step-details">
                <span>Score <strong>{challenge.score == null ? '—' : percentage(challenge.score)}</strong></span>
                <span>Gyroscope <strong>{metricNumber(challenge.metrics.observedGyroDegrees)}°</strong></span>
                <span>Rotation <strong>{metricNumber(challenge.metrics.observedRotationVectorDegrees)}°</strong></span>
                <span>Sensor match <strong>{percentage(challenge.metrics.sensorAgreement)}</strong></span>
                <span>Duration <strong>{metricNumber(challenge.metrics.movementDurationMs, 0)} ms</strong></span>
              </div>
            ) : null}
          </details>
        ))}
      </section>

      {canReviewAnalysis && ['UPLOADED', 'PROCESSING'].includes(item.status) ? (
        <section className="capture-analysis-section">
          <div className="capture-analysis-heading">
            <div>
              <strong>Camera motion</strong>
              <p className="muted">Checks whether the video shows the requested movement.</p>
            </div>
            {visual.data ? <span className="badge">{visual.data.status}</span> : null}
          </div>

          {visual.isLoading ? <p className="muted">Analyzing video…</p> : null}
          {visual.isError ? <div className="notice error">{visual.error.message}</div> : null}
          {visual.data && visual.data.challenges.length === 0 ? <p className="muted">No camera-motion result yet.</p> : null}

          {visual.data?.challenges.map((analysis) => (
            <details className="capture-step" key={`visual-${analysis.challengeId}`}>
              <summary>
                <span><strong>{challengeLabel(analysis.challengeType)}</strong><small>{analysis.visualDirection} · {percentage(analysis.confidence)} confidence</small></span>
                <span>{visualStatus(analysis.status)}</span>
              </summary>
              <div className="capture-step-details">
                <span>Estimated movement <strong>{analysis.estimatedRotationDegrees == null ? '—' : `${analysis.estimatedRotationDegrees.toFixed(1)}°`}</strong></span>
                <span>Scene continuity <strong>{percentage(analysis.sceneContinuityScore)}</strong></span>
                <span>Tracked features <strong>{analysis.trackedFeatureCount}</strong></span>
                <span>Duplicate frames <strong>{percentage(analysis.duplicateFrameRatio)}</strong></span>
                <span>Freeze <strong>{analysis.freezeDurationMs} ms</strong></span>
              </div>
              {analysis.reasons.length ? <p className="muted">{analysis.reasons.join(' ')}</p> : null}
            </details>
          ))}
        </section>
      ) : null}

      {canReviewAnalysis && ['UPLOADED', 'PROCESSING'].includes(item.status) ? (
        <section className="capture-analysis-section">
          <div className="capture-analysis-heading">
            <div>
              <strong>Sensor & camera match</strong>
              <p className="muted">Compares phone motion with motion seen in the video.</p>
            </div>
            {fusion.data ? <span className="badge">{fusionAnalysisLabel(fusion.data.status)}</span> : null}
          </div>

          {fusion.isLoading ? <p className="muted">Comparing signals…</p> : null}
          {fusion.isError ? <div className="notice error">{fusion.error.message}</div> : null}
          {fusion.data?.status === 'PENDING' && fusion.data.challenges.length === 0 ? <p className="muted">Waiting for sensor and camera analysis.</p> : null}

          {fusion.data?.challenges.map((analysis) => (
            <details className="capture-step" key={`fusion-${analysis.challengeId}`}>
              <summary>
                <span><strong>{fusionChallengeTitle(analysis, latestAttempts)}</strong><small>{percentage(analysis.consistencyScore)} consistency</small></span>
                <span>{consistencyLabel(analysis.consistencyStatus)}</span>
              </summary>
              <div className="capture-step-details">
                <span>Sensor <strong>{analysis.sensorDirection} · {metricNumber(analysis.sensorAngleDeg)}°</strong></span>
                <span>Camera <strong>{analysis.visualDirection} · {metricNumber(analysis.visualAngleDeg)}°</strong></span>
                <span>Angle difference <strong>{metricNumber(analysis.angleDifferenceDeg)}°</strong></span>
                <span>Start offset <strong>{signedMilliseconds(analysis.startOffsetMs)}</strong></span>
                <span>End offset <strong>{signedMilliseconds(analysis.endOffsetMs)}</strong></span>
                <span>Correlation <strong>{metricNumber(analysis.motionCurveCorrelation, 2)}</strong></span>
              </div>
              <FusionMotionChart sensor={analysis.sensorCurve} visual={analysis.visualCurve} />
              {analysis.mismatchReasons.length ? <p className="muted">{analysis.mismatchReasons.join(' · ')}</p> : null}
            </details>
          ))}

          {fusion.data?.status === 'COMPLETE' ? (
            <p className="muted">
              {fusion.data.summary.consistent} consistent · {fusion.data.summary.partiallyConsistent} partial · {fusion.data.summary.mismatch} mismatch · {fusion.data.summary.inconclusive} inconclusive
              {fusion.data.summary.meanConsistencyScore == null ? '' : ` · mean ${percentage(fusion.data.summary.meanConsistencyScore)}`}
            </p>
          ) : null}
        </section>
      ) : null}

      {item.sensorSummary ? (
        <details className="evidence-details">
          <summary>Sample counts</summary>
          <div className="evidence-details-content receipt-detail-list">
            <div><span>Accelerometer</span><strong>{item.sensorSummary.accelerometerSamples}</strong></div>
            <div><span>Gyroscope</span><strong>{item.sensorSummary.gyroscopeSamples}</strong></div>
            <div><span>Rotation vector</span><strong>{item.sensorSummary.rotationVectorSamples}</strong></div>
            <div><span>Location</span><strong>{item.locationSummary?.locationSamples ?? 0}</strong></div>
          </div>
        </details>
      ) : null}

      {evidence.isError ? <div className="notice error">{evidence.error.message}</div> : null}
    </article>
  )
}
