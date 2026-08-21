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
  const seconds = Math.round(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return minutes ? `${minutes}m ${remainder}s` : `${seconds}s`
}

function formatBytes(value?: number | null) {
  if (!value) return '—'
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${value} B`
}

function shortHash(value?: string | null) {
  if (!value) return '—'
  return `${value.slice(0, 10)}…${value.slice(-8)}`
}

export function EvidenceVideoPanel({ inspectionId }: { inspectionId: string }) {
  const session = useQuery({
    queryKey: ['verification-session', inspectionId],
    queryFn: () => getLatestVerificationSession(inspectionId),
    refetchInterval: 5000,
  })
  const evidence = useQuery({
    queryKey: ['verification-evidence', session.data?.id],
    queryFn: () => getSessionEvidence(session.data!.id),
    enabled: Boolean(session.data?.id),
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

  async function loadVideo() {
    if (!video?.downloadPath) return
    setLoadingVideo(true)
    setVideoError(null)
    try {
      const blob = await fetchEvidenceBlob(video.downloadPath)
      if (videoUrl) URL.revokeObjectURL(videoUrl)
      setVideoUrl(URL.createObjectURL(blob))
    } catch (error) {
      setVideoError(error instanceof Error ? error.message : 'Could not load the video')
    } finally {
      setLoadingVideo(false)
    }
  }

  if (session.isLoading) {
    return <article className="panel evidence-video-panel" aria-busy="true"><p className="eyebrow">Video</p><div className="video-skeleton" role="status">Loading capture…</div></article>
  }
  if (session.isError) {
    return (
      <article className="panel evidence-video-panel">
        <p className="eyebrow">Video</p>
        <div className="notice error" role="alert">
          <strong>Could not load the capture</strong>
          <p>{session.error.message}</p>
          <button className="button ghost" type="button" onClick={() => session.refetch()}>Try again</button>
        </div>
      </article>
    )
  }
  if (!session.data) return null

  const item = session.data

  return (
    <article className="panel evidence-video-panel" aria-busy={loadingVideo || evidence.isLoading}>
      <div className="evidence-video-heading">
        <div>
          <p className="eyebrow">Video</p>
          <h2>Captured video</h2>
          <p className="muted">Load the recorded field video when you need to review it.</p>
        </div>
        <span className="secure-chip">{item.status.replace(/_/g, ' ')}</span>
      </div>

      <div className="video-summary-grid">
        <div><span>Captured</span><strong>{formatDate(item.captureEndedAt)}</strong></div>
        <div><span>Duration</span><strong>{formatDuration(item.captureDurationMs)}</strong></div>
        <div><span>Integrity</span><strong>{video?.hashVerified ? 'Verified' : video ? 'Pending' : '—'}</strong></div>
      </div>

      {evidence.isLoading ? <div className="video-skeleton" role="status">Loading video details…</div> : null}
      {evidence.isError ? (
        <div className="notice error" role="alert">
          <strong>Could not load video details</strong>
          <p>{evidence.error.message}</p>
          <button className="button ghost" type="button" onClick={() => evidence.refetch()}>Try again</button>
        </div>
      ) : null}

      {!evidence.isLoading && !evidence.isError && !video ? (
        <div className="video-empty-state">
          <strong>No video available</strong>
          <p>This capture does not have a downloadable video.</p>
        </div>
      ) : null}

      {video && !videoUrl && !videoError ? (
        <div className="video-poster-state">
          <div className="video-play-mark" aria-hidden="true">▶</div>
          <strong>Video ready</strong>
          <span>{formatDuration(item.captureDurationMs)}</span>
          <button className="button primary" type="button" onClick={loadVideo} disabled={loadingVideo}>
            {loadingVideo ? 'Loading…' : 'Load video'}
          </button>
        </div>
      ) : null}

      {videoError ? (
        <div className="notice error" role="alert">
          <strong>Video unavailable</strong>
          <p>{videoError}</p>
          <button className="button ghost" type="button" onClick={loadVideo} disabled={loadingVideo}>{loadingVideo ? 'Trying again…' : 'Try again'}</button>
        </div>
      ) : null}

      {videoUrl ? (
        <div className="video-player-shell">
          <video className="evidence-video-player" src={videoUrl} controls preload="metadata" playsInline aria-label="Captured field video" />
          <div className="video-player-caption">
            <span>{video?.filename}</span>
            <button className="button ghost" type="button" onClick={loadVideo} disabled={loadingVideo}>Reload</button>
          </div>
        </div>
      ) : null}

      {video ? (
        <details className="evidence-details">
          <summary>File details</summary>
          <div className="evidence-details-content receipt-detail-list">
            <div><span>File</span><strong>{video.filename}</strong></div>
            <div><span>Size</span><strong>{formatBytes(video.sizeBytes)}</strong></div>
            <div><span>SHA-256</span><strong className="mono-value" title={video.sha256 ?? undefined}>{shortHash(video.sha256)}</strong></div>
            <div><span>Hash check</span><strong>{video.hashVerified ? 'Verified' : 'Pending'}</strong></div>
          </div>
        </details>
      ) : null}
    </article>
  )
}
