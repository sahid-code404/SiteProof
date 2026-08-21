import type { FusionCurvePoint } from '../lib/fusionApi'
import { curvePath } from '../lib/fusion'

export function FusionMotionChart({
  sensor,
  visual,
}: {
  sensor: FusionCurvePoint[]
  visual: FusionCurvePoint[]
}) {
  const width = 600
  const height = 150
  const sensorPath = curvePath(sensor, width, height)
  const visualPath = curvePath(visual, width, height)

  if (!sensorPath && !visualPath) {
    return <small className="muted">Motion curves unavailable for this challenge.</small>
  }

  return (
    <div>
      <small>Normalized motion shape · solid sensor / dashed camera</small>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Normalized gyroscope and visual motion timeline"
        style={{ width: '100%', minHeight: 120 }}
      >
        <line x1="12" y1={height - 12} x2={width - 12} y2={height - 12} stroke="currentColor" opacity="0.25" />
        {sensorPath ? (
          <path d={sensorPath} fill="none" stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke" />
        ) : null}
        {visualPath ? (
          <path
            d={visualPath}
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeDasharray="8 6"
            opacity="0.7"
            vectorEffect="non-scaling-stroke"
          />
        ) : null}
      </svg>
    </div>
  )
}
