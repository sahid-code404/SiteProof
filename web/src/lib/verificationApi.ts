import { API_BASE_URL } from './api'
import { clearSession, getToken } from './auth'

export type VerificationProcessingStatus =
  | 'PENDING'
  | 'WAITING_FOR_SIGNALS'
  | 'CALCULATING'
  | 'COMPLETED'
  | 'FAILED'

export type VerificationVerdict =
  | 'VERIFIED'
  | 'REVIEW_REQUIRED'
  | 'FLAGGED'
  | 'INCONCLUSIVE'

export type VerificationSignalType =
  | 'LOCATION'
  | 'SESSION_TIME'
  | 'CHALLENGE_COMPLETION'
  | 'SENSOR_QUALITY'
  | 'VISUAL_MOTION'
  | 'SCENE_CONTINUITY'
  | 'VISUAL_INERTIAL_CONSISTENCY'

export type VerificationSignalStatus =
  | 'PASS'
  | 'PARTIAL'
  | 'FAIL'
  | 'INCONCLUSIVE'
  | 'UNAVAILABLE'

export type ReviewDecision = 'APPROVED' | 'REJECTED' | 'RECAPTURE_REQUIRED'

export type VerificationSignalItem = {
  type: VerificationSignalType
  status: VerificationSignalStatus
  score: number
  confidence: number
  weight: number
  contribution: number
  required: boolean
  reasonSummary: string
  reasons: string[]
  metrics: Record<string, unknown>
  sourceAlgorithmVersion?: string | null
}

export type VerificationResponse = {
  resultId?: string | null
  sessionId: string
  inspectionId: string
  status: VerificationProcessingStatus
  score?: number | null
  confidence?: number | null
  verdict?: VerificationVerdict | null
  policy?: {
    id: string
    name: string
    version: string
    engineVersion: string
  } | null
  signals: VerificationSignalItem[]
  hardRules: string[]
  summary?: string | null
  summaryReasons: string[]
  warnings: string[]
  limitations: string[]
  calculatedAt?: string | null
  latestReview?: {
    id: string
    decision: ReviewDecision
    reason: string
    reviewerUserId: string
    createdAt: string
  } | null
}

export type ReviewQueueItem = {
  inspectionId: string
  sessionId: string
  resultId: string
  title: string
  locationName?: string | null
  locationAddress?: string | null
  latitude: number
  longitude: number
  inspectorName?: string | null
  inspectionStatus: string
  verdict: VerificationVerdict
  score?: number | null
  confidence?: number | null
  engineVersion: string
  calculatedAt?: string | null
  captureEndedAt?: string | null
  latestReview?: {
    id: string
    decision: ReviewDecision
    reason: string
    reviewerUserId: string
    createdAt: string
  } | null
}

export type ReviewQueueResponse = {
  items: ReviewQueueItem[]
  total: number
}

async function verificationRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
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
      // Keep the HTTP fallback when the response is not JSON.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function getSessionVerification(sessionId: string): Promise<VerificationResponse> {
  return verificationRequest(`/sessions/${sessionId}/verification`)
}

export function getReviewQueue(params: URLSearchParams): Promise<ReviewQueueResponse> {
  const query = params.toString()
  return verificationRequest(`/review-queue${query ? `?${query}` : ''}`)
}

export function recalculateSessionVerification(sessionId: string): Promise<VerificationResponse> {
  return verificationRequest(`/sessions/${sessionId}/verification/recalculate`, { method: 'POST' })
}

export function submitInspectionReview(
  inspectionId: string,
  sessionId: string,
  decision: ReviewDecision,
  reason: string,
): Promise<{ id: string; decision: ReviewDecision; reason: string; reviewerUserId: string; createdAt: string }> {
  return verificationRequest(`/inspections/${inspectionId}/review`, {
    method: 'POST',
    body: JSON.stringify({ sessionId, decision, reason }),
  })
}