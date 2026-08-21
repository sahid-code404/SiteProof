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
      setVideoError(error instanceof Error ? error.message : 'Unable to load captured video evidence')
    } finally {
      setLoadingVideo(false)
    }
  }

  if (session.isLoading) {
    return <article className="panel evidence-video-panel" aria-busy="true"><p className="eyebrow">CAPTURED VIDEO EVIDENCE</p><div className="video-skeleton" role="status">Preparing protected evidence…</div></article>
  }
  if (session.isError) {
    return (
      <article className="panel evidence-video-panel">
        <p className="eyebrow">CAPTURED VIDEO EVIDENCE</p>
        <div className="notice error" role="alert">
          <strong>Unable to load capture session</strong>
          <p>{session.error.message}</p>
          <button className="button ghost" type="button" onClick={() => session.refetch()}>Retry session</button>
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
          <p className="eyebrow">CAPTURED VIDEO EVIDENCE</p>
          <h2>Field capture playback</h2>
          <p className="muted">Protected video is loaded on demand with the authenticated evidence endpoint. Playback never changes the sealed evidence object.</p>
        </div>
        <span className="secure-chip">{item.status.replace(/_/g, ' ')}</span>
      </div>

      <div className="video-meta-grid">
        <div><span>Captured</span><strong>{formatDate(item.captureEndedAt)}</strong></div>
        <div><span>Duration</span><strong>{formatDuration(item.captureDurationMs)}</strong></div>
        <div><span>File</span><strong>{video?.filename ?? 'Video unavailable'}</strong></div>
        <div><span>Size</span><strong>{formatBytes(video?.sizeBytes)}</strong></div>
        <div><span>Evidence hash</span><strong className="mono-value video-hash" title={video?.sha256 ?? undefined}>{shortHash(video?.sha256)}</strong></div>
        <div><span>Hash verified</span><strong>{video?.hashVerified ? '✓ Verified' : video ? 'Pending' : '—'}</strong></div>
      </div>

      {evidence.isLoading ? <div className="video-skeleton" role="status">Checking video object…</div> : null}
      {evidence.isError ? (
        <div className="notice error" role="alert">
          <strong>Evidence metadata unavailable</strong>
          <p>{evidence.error.message}</p>
          <button className="button ghost" type="button" onClick={() => evidence.refetch()}>Retry metadata</button>
        </div>
      ) : null}

      {!evidence.isLoading && !evidence.isError && !video ? (
        <div className="video-empty-state">
          <strong>Video evidence unavailable</strong>
          <p>The session exists, but no downloadable VIDEO evidence object is currently available.</p>
        </div>
      ) : null}

      {video && !videoUrl && !videoError ? (
        <div className="video-poster-state">
          <div className="video-play-mark" aria-hidden="true">▶</div>
          <strong>Captured evidence ready</strong>
          <span>{video.filename} · {formatBytes(video.sizeBytes)}</span>
          <button className="button primary" type="button" onClick={loadVideo} disabled={loadingVideo}>
            {loadingVideo ? 'Loading protected video…' : 'Load captured video'}
          </button>
        </div>
      ) : null}

      {videoError ? (
        <div className="notice error" role="alert">
          <strong>Video unavailable</strong>
          <p>{videoError}</p>
          <div className="video-error-actions">
            <button className="button ghost" type="button" onClick={loadVideo} disabled={loadingVideo}>{loadingVideo ? 'Retrying…' : 'Retry video'}</button>
          </div>
        </div>
      ) : null}

      {videoUrl ? (
        <div className="video-player-shell">
          <video className="evidence-video-player" src={videoUrl} controls preload="metadata" playsInline aria-label="Captured field evidence video" />
          <div className="video-player-caption">
            <span>{video?.filename}</span>
            <button className="button ghost" type="button" onClick={loadVideo} disabled={loadingVideo}>Reload protected object</button>
          </div>
        </div>
      ) : null}
    </article>
  )
}
