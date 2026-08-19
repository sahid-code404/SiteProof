import { clearSession, getToken, type AuthUser } from './auth'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const BACKEND_BASE_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

export type InspectionStatus =
  | 'DRAFT'
  | 'ASSIGNED'
  | 'ACKNOWLEDGED'
  | 'READY'
  | 'SESSION_STARTED'
  | 'EVIDENCE_UPLOADING'
  | 'PROCESSING'
  | 'CANCELLED'
export type InspectionPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type InspectionType = 'ROAD_REPAIR' | 'INFRASTRUCTURE' | 'CONSTRUCTION' | 'UTILITY' | 'GENERAL'

export type Inspector = {
  id: string
  userId: string
  name: string
  email: string
  employeeCode?: string | null
  phone?: string | null
  active: boolean
}

export type Assignment = {
  id: string
  inspector: Inspector
  status: 'ACTIVE' | 'REASSIGNED' | 'CANCELLED'
  assignedAt: string
  acknowledgedAt?: string | null
  unassignedAt?: string | null
  reason?: string | null
}

export type Inspection = {
  id: string
  title: string
  description?: string | null
  inspectionType: InspectionType
  status: InspectionStatus
  expectedLatitude: number
  expectedLongitude: number
  allowedRadiusMeters: number
  locationName?: string | null
  locationAddress?: string | null
  deadline: string
  priority: InspectionPriority
  instructions?: string | null
  createdAt: string
  updatedAt: string
  cancelledAt?: string | null
  isOverdue: boolean
  activeAssignment?: Assignment | null
}

export type InspectionDetail = Inspection & {
  assignmentHistory: Assignment[]
  createdByName: string
}

export type Page<T> = {
  items: T[]
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export type DashboardSummary = {
  total: number
  draft: number
  assigned: number
  acknowledged: number
  ready: number
  cancelled: number
  dueToday: number
  overdue: number
  highPriority: number
}

export type InspectionPayload = {
  title: string
  description?: string
  inspectionType: InspectionType
  location: { latitude: number; longitude: number; name?: string; address?: string }
  allowedRadiusMeters: number
  deadline: string
  priority: InspectionPriority
  instructions?: string
}

export type VerificationSessionStatus =
  | 'CREATED'
  | 'CAPTURING'
  | 'CHALLENGES_IN_PROGRESS'
  | 'CHALLENGES_COMPLETED'
  | 'CHALLENGE_FAILED'
  | 'CAPTURE_COMPLETED'
  | 'UPLOADING'
  | 'UPLOADED'
  | 'PROCESSING'
  | 'ABORTED'
  | 'EXPIRED'
  | 'UPLOAD_FAILED'

export type SensorSummary = {
  accelerometerSamples: number
  gyroscopeSamples: number
  rotationVectorSamples: number
  magnetometerSamples: number
}

export type LocationSummary = {
  locationSamples: number
  bestAccuracyMeters?: number | null
  firstRelativeTimestampNs?: number | null
  lastRelativeTimestampNs?: number | null
}

export type EvidencePresence = {
  video: boolean
  sensorData: boolean
  locationData: boolean
  sessionMetadata: boolean
  manifest: boolean
}

export type VerificationSession = {
  id: string
  inspectionId: string
  inspectorId: string
  status: VerificationSessionStatus
  createdAt: string
  captureStartedAt?: string | null
  captureEndedAt?: string | null
  uploadedAt?: string | null
  expiresAt: string
  captureDurationMs?: number | null
  manifestSha256?: string | null
  sensorSummary?: SensorSummary | null
  locationSummary?: LocationSummary | null
  evidence: EvidencePresence
}

export type ChallengeType = 'ROTATE_LEFT' | 'ROTATE_RIGHT' | 'TILT_UP' | 'TILT_DOWN'
export type ChallengeResult = 'PASS' | 'FAIL' | 'INCONCLUSIVE'

export type ChallengeTimelineItem = {
  id: string
  sequenceNumber: number
  attemptNumber: number
  type: ChallengeType
  status: string
  result?: ChallengeResult | null
  parameters: { targetDegrees: number; minDegrees: number; maxDegrees: number }
  issuedAt: string
  startedAt?: string | null
  completedAt?: string | null
  expiresAt: string
  score?: number | null
  sensorScore?: number | null
  failureReason?: string | null
  reasons: string[]
  metrics: Record<string, unknown>
  sensorQuality: Record<string, unknown>
}

export type ChallengeListResponse = {
  sessionId: string
  totalRequired: number
  items: ChallengeTimelineItem[]
}

export type VisualAnalysisStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'INCONCLUSIVE' | 'FAILED'
export type VisualDirection = 'LEFT' | 'RIGHT' | 'UP' | 'DOWN' | 'MIXED' | 'NONE'
export type VisualQuality = 'GOOD' | 'FAIR' | 'POOR'

export type VisualChallengeAnalysis = {
  challengeId: string
  challengeType: ChallengeType
  analysisVersion: string
  status: VisualAnalysisStatus
  visualDirection: VisualDirection
  estimatedRotationDegrees?: number | null
  translationX?: number | null
  translationY?: number | null
  scaleChange?: number | null
  motionStartMs?: number | null
  motionEndMs?: number | null
  featureCount: number
  trackedFeatureCount: number
  inlierRatio: number
  confidence: number
  sceneContinuityScore: number
  duplicateFrameRatio: number
  freezeDurationMs: number
  invalidFrameRatio: number
  visualQuality: VisualQuality
  reasons: string[]
  diagnostics: Record<string, unknown>
}

export type VisualAnalysisResponse = {
  sessionId: string
  status: VisualAnalysisStatus
  analysisVersion: string
  challenges: VisualChallengeAnalysis[]
}

export type EvidenceFile = {
  id: string
  type: 'VIDEO' | 'SENSOR_DATA' | 'LOCATION_DATA' | 'SESSION_METADATA' | 'MANIFEST' | 'THUMBNAIL'
  filename: string
  mimeType: string
  sizeBytes: number
  sha256: string
  uploadStatus: 'PENDING' | 'UPLOADING' | 'UPLOADED' | 'FAILED'
  hashVerified: boolean
  uploadedAt?: string | null
  downloadPath?: string | null
}

type ErrorBody = { error?: { code?: string; message?: string } }

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  if (response.status === 401 && token) clearSession()
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as ErrorBody
      message = body.error?.message ?? message
    } catch {
      // Keep the HTTP fallback message.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function getBackendHealth(): Promise<{ status: string; service: string }> {
  const response = await fetch(`${BACKEND_BASE_URL}/health`)
  if (!response.ok) throw new Error('Backend health check failed')
  return response.json()
}

export function login(email: string, password: string): Promise<{ accessToken: string; user: AuthUser }> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function getSummary(): Promise<DashboardSummary> {
  return request('/inspections/summary')
}

export function getInspections(params: URLSearchParams): Promise<Page<Inspection>> {
  const query = params.toString()
  return request(`/inspections${query ? `?${query}` : ''}`)
}

export function getInspection(id: string): Promise<InspectionDetail> {
  return request(`/inspections/${id}`)
}

export function createInspection(payload: InspectionPayload): Promise<Inspection> {
  return request('/inspections', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateInspection(id: string, payload: InspectionPayload): Promise<Inspection> {
  return request(`/inspections/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function assignInspection(id: string, inspectorId: string): Promise<Inspection> {
  return request(`/inspections/${id}/assign`, {
    method: 'POST',
    body: JSON.stringify({ inspectorId }),
  })
}

export function reassignInspection(id: string, inspectorId: string, reason: string): Promise<Inspection> {
  return request(`/inspections/${id}/reassign`, {
    method: 'POST',
    body: JSON.stringify({ inspectorId, reason }),
  })
}

export function cancelInspection(id: string, reason: string): Promise<Inspection> {
  return request(`/inspections/${id}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

export function getInspectors(search = ''): Promise<Page<Inspector>> {
  const params = new URLSearchParams({ page: '1', pageSize: '100', active: 'true' })
  if (search) params.set('search', search)
  return request(`/inspectors?${params.toString()}`)
}

export function getLatestVerificationSession(inspectionId: string): Promise<VerificationSession | null> {
  return request(`/inspections/${inspectionId}/sessions/latest`)
}

export function getSessionChallenges(sessionId: string): Promise<ChallengeListResponse> {
  return request(`/sessions/${sessionId}/challenges`)
}

export function getSessionVisualAnalysis(sessionId: string): Promise<VisualAnalysisResponse> {
  return request(`/sessions/${sessionId}/visual-analysis`)
}

export function retrySessionVisualAnalysis(sessionId: string): Promise<VisualAnalysisResponse> {
  return request(`/sessions/${sessionId}/visual-analysis/retry`, { method: 'POST' })
}

export function getSessionEvidence(sessionId: string): Promise<{ sessionId: string; items: EvidenceFile[] }> {
  return request(`/sessions/${sessionId}/evidence`)
}

export async function fetchEvidenceBlob(downloadPath: string): Promise<Blob> {
  const token = getToken()
  const normalized = downloadPath.replace(/^\/+/, '')
  const response = await fetch(`${API_BASE_URL}/${normalized}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw new Error(`Unable to load evidence (${response.status})`)
  return response.blob()
}

export { API_BASE_URL }
