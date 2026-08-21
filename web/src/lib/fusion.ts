import type { ConsistencyStatus, FusionAnalysisStatus, FusionCurvePoint } from './fusionApi'

export function fusionAnalysisLabel(status: FusionAnalysisStatus): string {
  if (status === 'COMPLETE') return 'Cross-signal analysis complete'
  if (status === 'FAILED') return 'Cross-signal processing failed'
  if (status === 'PROCESSING') return 'Comparing sensor and camera motion…'
  return 'Waiting for both motion sources'
}

export function consistencyLabel(status: ConsistencyStatus): string {
  if (status === 'CONSISTENT') return '✓ CONSISTENT'
  if (status === 'PARTIALLY_CONSISTENT') return '◐ PARTIALLY CONSISTENT'
  if (status === 'MISMATCH') return '⚠ MISMATCH'
  return '— INCONCLUSIVE'
}

export function curvePath(
  points: FusionCurvePoint[],
  width = 600,
  height = 150,
  padding = 12,
): string {
  if (points.length === 0) return ''
  const finite = points.filter(
    (point) => Number.isFinite(point.timeMs) && Number.isFinite(point.value),
  )
  if (finite.length === 0) return ''

  const minTime = Math.min(...finite.map((point) => point.timeMs))
  const maxTime = Math.max(...finite.map((point) => point.timeMs))
  const timeSpan = Math.max(1, maxTime - minTime)
  const innerWidth = Math.max(1, width - padding * 2)
  const innerHeight = Math.max(1, height - padding * 2)

  return finite
    .map((point, index) => {
      const x = padding + ((point.timeMs - minTime) / timeSpan) * innerWidth
      const normalized = Math.max(0, Math.min(1, point.value))
      const y = height - padding - normalized * innerHeight
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}
