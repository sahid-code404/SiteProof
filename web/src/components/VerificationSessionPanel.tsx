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
import { getStoredUser } from '../lib/auth'

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
        <div><span>Status</span><strong>{item.status}</strong><small>{['UPLOADED', 'PROCESSING'].includes(item.status) ? 'Evidence received · visual analysis is separate from final authenticity' : 'Live capture/challenge/upload in progress'}</small></div>
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
          <p className="muted">Deterministic OpenCV analysis only. Sensor-camera consistency is intentionally not calculated until Phase 6.</p>
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
      <p className="muted"><strong>Final authenticity:</strong> Not yet calculated. Phase 5 adds camera-side visual motion evidence but does not compare it with sensor-derived movement.</p>
      {video ? <button className="button ghost" onClick={previewVideo} disabled={loadingVideo}>{loadingVideo ? 'Loading evidence…' : 'Preview captured video'}</button> : null}
      {videoError ? <div className="notice error">{videoError}</div> : null}
      {videoUrl ? <video className="evidence-video" src={videoUrl} controls preload="metadata" /> : null}
    </article>
  )
}
