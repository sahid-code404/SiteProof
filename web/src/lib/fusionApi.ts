import { API_BASE_URL, type ChallengeType } from './api'
import { clearSession, getToken } from './auth'

export type FusionAnalysisStatus = 'PENDING' | 'PROCESSING' | 'COMPLETE' | 'FAILED'
export type ConsistencyStatus =
  | 'CONSISTENT'
  | 'PARTIALLY_CONSISTENT'
  | 'MISMATCH'
  | 'INCONCLUSIVE'
export type MotionDirection = 'LEFT' | 'RIGHT' | 'UP' | 'DOWN' | 'MIXED' | 'NONE'
export type MismatchReason =
  | 'OPPOSITE_DIRECTION'
  | 'VISUAL_WITHOUT_SENSOR_MOTION'
  | 'SENSOR_WITHOUT_VISUAL_MOTION'
  | 'MAGNITUDE_MISMATCH'
  | 'TEMPORAL_MISMATCH'
  | 'DURATION_MISMATCH'
  | 'LOW_SENSOR_QUALITY'
  | 'LOW_VISUAL_QUALITY'
  | 'SCENE_CONTINUITY_ANOMALY'
  | 'CURVE_UNAVAILABLE'

export type FusionCurvePoint = {
  timeMs: number
  value: number
}

export type FusionChallengeAnalysis = {
  challengeId: string
  challengeType: ChallengeType
  fusionVersion: string
  analysisStatus: FusionAnalysisStatus
  consistencyStatus: ConsistencyStatus
  sensorDirection: MotionDirection
  visualDirection: MotionDirection
  sensorAngleDeg?: number | null
  visualAngleDeg?: number | null
  angleDifferenceDeg?: number | null
  relativeAngleError?: number | null
  sensorStartMs?: number | null
  visualStartMs?: number | null
  startOffsetMs?: number | null
  sensorPeakMs?: number | null
  visualPeakMs?: number | null
  sensorEndMs?: number | null
  visualEndMs?: number | null
  endOffsetMs?: number | null
  sensorDurationMs?: number | null
  visualDurationMs?: number | null
  motionCurveCorrelation?: number | null
  bestLagMs?: number | null
  directionScore?: number | null
  magnitudeScore?: number | null
  timingScore?: number | null
  durationScore?: number | null
  correlationScore?: number | null
  rawConsistencyScore?: number | null
  consistencyScore?: number | null
  fusionConfidence?: number | null
  sensorConfidence: number
  visualConfidence: number
  mismatchReasons: MismatchReason[]
  explanations: string[]
  sensorCurve: FusionCurvePoint[]
  visualCurve: FusionCurvePoint[]
  diagnostics: Record<string, unknown>
}

export type FusionSessionSummary = {
  challengeCount: number
  consistent: number
  partiallyConsistent: number
  mismatch: number
  inconclusive: number
  meanConsistencyScore?: number | null
  strongContradictionDetected: boolean
}

export type FusionAnalysisResponse = {
  sessionId: string
  status: FusionAnalysisStatus
  fusionVersion: string
  challenges: FusionChallengeAnalysis[]
  summary: FusionSessionSummary
}

async function fusionRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  if (response.status === 401 && token) clearSession()
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { error?: { message?: string } }
      message = body.error?.message ?? message
    } catch {
      // Keep the HTTP fallback.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function getSessionFusionAnalysis(sessionId: string): Promise<FusionAnalysisResponse> {
  return fusionRequest(`/sessions/${sessionId}/fusion-analysis`)
}

export function retrySessionFusionAnalysis(sessionId: string): Promise<FusionAnalysisResponse> {
  return fusionRequest(`/sessions/${sessionId}/fusion-analysis/retry`, { method: 'POST' })
}
