import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchEvidenceBlob,
  getLatestVerificationSession,
  getSessionChallenges,
  getSessionEvidence,
  getSessionVisualAnalysis,
  type ChallengeTimelineItem,
  type EvidenceFile,
  type VisualChallengeAnalysis,
} from '../lib/api'
import {
  getSessionFusionAnalysis,
  type FusionChallengeAnalysis,
} from '../lib/fusionApi'
import { consistencyLabel, fusionAnalysisLabel } from '../lib/fusion'
import { getStoredUser } from '../lib/auth'
import { FusionMotionChart } from './FusionMotionChart'

function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function formatTime(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { timeStyle: 'medium' }).format(new Date(value))
}

function formatDuration(ms?: number | null) {
  if (!ms) return '—'
  return `${Math.round(ms / 1000)} sec`
}

function evidenceMark(value: boolean) {
  return value ? '✓ Received' : 'Waiting'
}

function challengeLabel(type: ChallengeTimelineItem['type']) {
  return {
    ROTATE_RIGHT: 'Rotate Right',
    ROTATE_LEFT: 'Rotate Left',
    TILT_UP: 'Tilt Up',
    TILT_DOWN: 'Tilt Down',
  }[type]
}

function resultMark(result?: ChallengeTimelineItem['result'] | null) {
  if (result === 'PASS') return '✓ PASS'
  if (result === 'FAIL') return '✕ FAIL'
  if (result === 'INCONCLUSIVE') return '⚠ INCONCLUSIVE'
  return 'In progress'
}

function visualStatus(value: VisualChallengeAnalysis['status']) {
  if (value === 'SUCCESS') return '✓ Visual motion detected'
  if (value === 'INCONCLUSIVE') return '⚠ Visual analysis inconclusive'
  if (value === 'FAILED') return '✕ Visual processing failed'
  if (value === 'PROCESSING') return 'Processing video…'
  return 'Waiting for video analysis'
}

function metricNumber(value: unknown, digits = 1) {
  return typeof value === 'number' ? value.toFixed(digits) : '—'
}

function percentage(value?: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

function signedMilliseconds(value?: number | null) {
  if (typeof value !== 'number') return '—'
  return `${value >= 0 ? '+' : ''}${Math.round(value)} ms`
}

function fusionChallengeTitle(
  analysis: FusionChallengeAnalysis,
  challenges: ChallengeTimelineItem[],
) {
  const challenge = challenges.find((item) => item.id === analysis.challengeId)
  return challenge
    ? `Challenge ${challenge.sequenceNumber} — ${challengeLabel(challenge.type)}`
    : challengeLabel(analysis.challengeType)
}

export function VerificationSessionPanel({ inspectionId }: { inspectionId: string }) {
  const role = getStoredUser()?.role
  const canReviewVisual = role === 'ADMIN' || role === 'REVIEWER'
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
    enabled: canReviewVisual && Boolean(session.data?.id) && ['UPLOADED', 'PROCESSING'].includes(session.data?.status ?? ''),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'PROCESSING' || status === 'PENDING' ? 3000 : false
    },
  })
  const fusion = useQuery({
    queryKey: ['fusion-analysis', session.data?.id],
    queryFn: () => getSessionFusionAnalysis(session.data!.id),
    enabled: canReviewVisual && Boolean(session.data?.id) && ['UPLOADED', 'PROCESSING'].includes(session.data?.status ?? ''),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'PROCESSING' || status === 'PENDING' ? 3000 : false
    },
  })
  const video = useMemo(
    () => evidence.data?.items.find((item: EvidenceFile) => item.type === 'VIDEO' && item.downloadPath),
    [evidence.data],
  )
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [videoError, setVideoError] = useState<string | null>(null)
  const [loadingVideo, setLoadingVideo] = useState(false)

  useEffect(() => () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl)
  }, [videoUrl])

  async function previewVideo() {
    if (!video?.downloadPath) return
    setLoadingVideo(true)
    setVideoError(null)
    try {
      const blob = await fetchEvidenceBlob(video.downloadPath)
      if (videoUrl) URL.revokeObjectURL(videoUrl)
      setVideoUrl(URL.createObjectURL(blob))
    } catch (error) {
      setVideoError(error instanceof Error ? error.message : 'Unable to load evidence video')
    } finally {
      setLoadingVideo(false)
    }
  }

  if (session.isLoading) return <article className="panel"><p className="eyebrow">VERIFICATION SESSION</p><p className="muted">Checking for evidence…</p></article>
  if (session.isError) return <article className="panel"><p className="eyebrow">VERIFICATION SESSION</p><div className="notice error">{session.error.message}</div></article>
  if (!session.data) return <article className="panel"><p className="eyebrow">VERIFICATION SESSION</p><p className="muted">No live evidence session has been started.</p></article>

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
    <article className="panel">
      <p className="eyebrow">VERIFICATION SESSION</p>
      <div className="definition-grid">
        <div><span>Status</span><strong>{item.status}</strong><small>{['UPLOADED', 'PROCESSING'].includes(item.status) ? 'Evidence received · cross-signal analysis remains separate from final authenticity' : 'Live capture/challenge/upload in progress'}</small></div>
        <div><span>Captured</span><strong>{formatDate(item.captureEndedAt)}</strong><small>Duration: {formatDuration(item.captureDurationMs)}</small></div>
      </div>

      <div className="callout">
        <strong>LIVE CHALLENGES · SENSOR EVIDENCE</strong>
        {challenges.isLoading ? <p>Loading challenge timeline…</p> : null}
        {latestAttempts.length === 0 && !challenges.isLoading ? <p className="muted">No challenge has been issued yet.</p> : null}
        {latestAttempts.map((challenge) => (
          <div key={`${challenge.sequenceNumber}-${challenge.attemptNumber}`} className="challenge-row">
            <div>
              <strong>{challenge.sequenceNumber}. {challengeLabel(challenge.type)}</strong>
              <small>Target ≈ {Math.round(challenge.parameters.targetDegrees)}° · {resultMark(challenge.result)}</small>
            </div>
            <div>
              <strong>{challenge.score == null ? '—' : `${Math.round(challenge.score * 100)}%`}</strong>
              <small>Attempt {challenge.attemptNumber}</small>
            </div>
            {challenge.result ? (
              <div className="challenge-metrics">
                <small>Gyroscope: {metricNumber(challenge.metrics.observedGyroDegrees)}°</small>
                <small>Rotation vector: {metricNumber(challenge.metrics.observedRotationVectorDegrees)}°</small>
                <small>Sensor agreement: {typeof challenge.metrics.sensorAgreement === 'number' ? `${Math.round(challenge.metrics.sensorAgreement * 100)}%` : '—'}</small>
                <small>Movement duration: {metricNumber(challenge.metrics.movementDurationMs, 0)} ms</small>
              </div>
            ) : null}
          </div>
        ))}
        {latestAttempts.length > 0 ? (
          <p><strong>Challenge completion:</strong> {passCount} Pass · {failCount} Fail · {inconclusiveCount} Inconclusive</p>
        ) : null}
      </div>

      {challengeItems.length > 0 ? (
        <div className="callout">
          <strong>Challenge event timeline</strong>
          {challengeItems.map((challenge) => (
            <p key={`timeline-${challenge.id}`}>
              {formatTime(challenge.issuedAt)} · Challenge {challenge.sequenceNumber} issued · {challengeLabel(challenge.type)}
              {challenge.startedAt ? ` · started ${formatTime(challenge.startedAt)}` : ''}
              {challenge.completedAt ? ` · ${resultMark(challenge.result)} ${formatTime(challenge.completedAt)}` : ''}
            </p>
          ))}
        </div>
      ) : null}

      {canReviewVisual && ['UPLOADED', 'PROCESSING'].includes(item.status) ? (
        <div className="callout visual-analysis-panel">
          <strong>VISUAL MOTION ANALYSIS · CAMERA EVIDENCE</strong>
          <p className="muted">Deterministic OpenCV camera-side evidence. It remains an independent input to Phase 6 rather than ground truth.</p>
          {visual.isLoading ? <p>Analyzing challenge video windows…</p> : null}
          {visual.isError ? <div className="notice error">{visual.error.message}</div> : null}
          {visual.data && visual.data.challenges.length === 0 ? <p className="muted">Visual analysis has not produced challenge results yet.</p> : null}
          {visual.data?.challenges.map((analysis) => (
            <div className="challenge-row visual-result-row" key={`visual-${analysis.challengeId}`}>
              <div>
                <strong>{challengeLabel(analysis.challengeType)}</strong>
                <small>{visualStatus(analysis.status)} · quality {analysis.visualQuality}</small>
              </div>
              <div>
                <strong>{analysis.visualDirection}</strong>
                <small>{analysis.estimatedRotationDegrees == null ? 'Magnitude unavailable' : `Estimated movement ≈ ${analysis.estimatedRotationDegrees.toFixed(1)}°`}</small>
              </div>
              <div className="challenge-metrics">
                <small>Visual confidence: {Math.round(analysis.confidence * 100)}%</small>
                <small>Scene continuity: {Math.round(analysis.sceneContinuityScore * 100)}%</small>
                <small>Tracked features: {analysis.trackedFeatureCount}</small>
                <small>RANSAC inliers: {Math.round(analysis.inlierRatio * 100)}%</small>
                <small>Duplicate frames: {Math.round(analysis.duplicateFrameRatio * 100)}%</small>
                <small>Freeze: {analysis.freezeDurationMs} ms</small>
              </div>
              {analysis.reasons.length ? <small>{analysis.reasons.join(' ')}</small> : null}
            </div>
          ))}
          {visual.data ? <small>Algorithm: {visual.data.analysisVersion} · overall visual-analysis status: {visual.data.status}</small> : null}
        </div>
      ) : null}

      {canReviewVisual && ['UPLOADED', 'PROCESSING'].includes(item.status) ? (
        <div className="callout">
          <strong>CROSS-SIGNAL ANALYSIS · PHYSICAL VS CAMERA</strong>
          <p className="muted">
            Phase 6 deterministically compares backend-derived phone motion with camera-side motion. A consistency result is not a final authenticity verdict.
          </p>
          {fusion.isLoading ? <p>Waiting for cross-signal analysis…</p> : null}
          {fusion.isError ? <div className="notice error">{fusion.error.message}</div> : null}
          {fusion.data ? <p><strong>{fusionAnalysisLabel(fusion.data.status)}</strong> · algorithm {fusion.data.fusionVersion}</p> : null}
          {fusion.data?.status === 'PENDING' && fusion.data.challenges.length === 0 ? (
            <p className="muted">Fusion starts only after both Phase 4 sensor analysis and Phase 5 visual analysis are available.</p>
          ) : null}

          {fusion.data?.challenges.map((analysis) => (
            <div className="challenge-row visual-result-row" key={`fusion-${analysis.challengeId}`}>
              <div>
                <strong>{fusionChallengeTitle(analysis, latestAttempts)}</strong>
                <small>{consistencyLabel(analysis.consistencyStatus)} · fusion confidence {percentage(analysis.fusionConfidence)}</small>
              </div>
              <div className="definition-grid">
                <div>
                  <span>Sensor motion</span>
                  <strong>{analysis.sensorDirection} · {metricNumber(analysis.sensorAngleDeg)}°</strong>
                  <small>Confidence {percentage(analysis.sensorConfidence)}</small>
                </div>
                <div>
                  <span>Camera motion</span>
                  <strong>{analysis.visualDirection} · {metricNumber(analysis.visualAngleDeg)}°</strong>
                  <small>Confidence {percentage(analysis.visualConfidence)}</small>
                </div>
              </div>
              <div className="challenge-metrics">
                <small>Angle difference: {metricNumber(analysis.angleDifferenceDeg)}°</small>
                <small>Start offset (camera − sensor): {signedMilliseconds(analysis.startOffsetMs)}</small>
                <small>End offset: {signedMilliseconds(analysis.endOffsetMs)}</small>
                <small>Best curve correlation: {metricNumber(analysis.motionCurveCorrelation, 2)}</small>
                <small>Best limited lag: {signedMilliseconds(analysis.bestLagMs)}</small>
                <small>Cross-signal consistency: {percentage(analysis.consistencyScore)}</small>
              </div>
              <FusionMotionChart sensor={analysis.sensorCurve} visual={analysis.visualCurve} />
              {analysis.mismatchReasons.length ? (
                <small><strong>Detected:</strong> {analysis.mismatchReasons.join(' · ')}</small>
              ) : null}
              {analysis.explanations.length ? <small>{analysis.explanations.join(' ')}</small> : null}
            </div>
          ))}

          {fusion.data?.status === 'COMPLETE' ? (
            <p>
              <strong>Challenge consistency summary:</strong>{' '}
              {fusion.data.summary.consistent} Consistent · {fusion.data.summary.partiallyConsistent} Partial ·{' '}
              {fusion.data.summary.mismatch} Mismatch · {fusion.data.summary.inconclusive} Inconclusive
              {fusion.data.summary.meanConsistencyScore == null ? '' : ` · Mean ${percentage(fusion.data.summary.meanConsistencyScore)}`}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="definition-grid">
        <div><span>Video</span><strong>{evidenceMark(item.evidence.video)}</strong></div>
        <div><span>Motion sensors</span><strong>{evidenceMark(item.evidence.sensorData)}</strong></div>
        <div><span>Location data</span><strong>{evidenceMark(item.evidence.locationData)}</strong></div>
        <div><span>Manifest</span><strong>{evidenceMark(item.evidence.manifest)}</strong></div>
      </div>
      {item.sensorSummary ? (
        <div className="callout">
          <strong>Capture metadata</strong>
          <p>Accelerometer: {item.sensorSummary.accelerometerSamples} samples · Gyroscope: {item.sensorSummary.gyroscopeSamples} · Rotation vector: {item.sensorSummary.rotationVectorSamples} · Location: {item.locationSummary?.locationSamples ?? 0}</p>
        </div>
      ) : null}
      <p className="muted">
        <strong>Final authenticity:</strong> Not yet calculated. Phase 6 measures sensor-camera consistency only; the overall SiteProof trust score and VERIFIED / REVIEW REQUIRED decision belong to Phase 7.
      </p>
      {video ? <button className="button ghost" onClick={previewVideo} disabled={loadingVideo}>{loadingVideo ? 'Loading evidence…' : 'Preview captured video'}</button> : null}
      {videoError ? <div className="notice error">{videoError}</div> : null}
      {videoUrl ? <video className="evidence-video" src={videoUrl} controls preload="metadata" /> : null}
    </article>
  )
}
