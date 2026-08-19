import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchEvidenceBlob,
  getLatestVerificationSession,
  getSessionEvidence,
  type EvidenceFile,
} from '../lib/api'

function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function formatDuration(ms?: number | null) {
  if (!ms) return '—'
  return `${Math.round(ms / 1000)} sec`
}

function evidenceMark(value: boolean) {
  return value ? '✓ Received' : 'Waiting'
}

export function VerificationSessionPanel({ inspectionId }: { inspectionId: string }) {
  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })
  const evidence = useQuery({
    queryKey: ['verification-evidence', session.data?.id],
    queryFn: () => getSessionEvidence(session.data!.id),
    enabled: Boolean(session.data?.id),
    refetchInterval: session.data?.status === 'UPLOADED' ? false : 5000,
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
  return (
    <article className="panel">
      <p className="eyebrow">VERIFICATION SESSION</p>
      <div className="definition-grid">
        <div><span>Status</span><strong>{item.status}</strong><small>{item.status === 'UPLOADED' ? 'Awaiting verification analysis' : 'Evidence capture/upload in progress'}</small></div>
        <div><span>Captured</span><strong>{formatDate(item.captureEndedAt)}</strong><small>Duration: {formatDuration(item.captureDurationMs)}</small></div>
      </div>
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
      <p className="muted"><strong>Verification:</strong> Not yet analyzed. Phase 3 does not calculate an authenticity or trust score.</p>
      {video ? <button className="button ghost" onClick={previewVideo} disabled={loadingVideo}>{loadingVideo ? 'Loading evidence…' : 'Preview captured video'}</button> : null}
      {videoError ? <div className="notice error">{videoError}</div> : null}
      {videoUrl ? <video className="evidence-video" src={videoUrl} controls preload="metadata" /> : null}
    </article>
  )
}
