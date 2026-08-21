import { API_BASE_URL } from './api'
import { clearSession, getToken } from './auth'

export type AdvancedSecurity = {
  sessionId: string
  algorithmVersion: string
  processStatus: string
  overallRisk: 'LOW' | 'MODERATE' | 'HIGH' | 'INCONCLUSIVE' | string
  confidence: number
  locationRiskScore: number
  sensorAnomalyScore: number
  replayRiskScore: number
  evidenceReuseScore: number
  deviceIntegrityStatus: string
  deviceRiskScore: number
  reasonCodes: string[]
  reasons: string[]
  metrics: Record<string, unknown>
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
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

export function getAdvancedSecurity(sessionId: string): Promise<AdvancedSecurity | null> {
  return request(`/sessions/${sessionId}/advanced-security`)
}

export function analyzeAdvancedSecurity(sessionId: string): Promise<AdvancedSecurity> {
  return request(`/sessions/${sessionId}/advanced-security/analyze`, { method: 'POST' })
}
