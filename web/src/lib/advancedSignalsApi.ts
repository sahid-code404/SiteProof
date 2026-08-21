import { API_BASE_URL } from './api'
import { clearSession, getToken } from './auth'

export type AdvancedSignals = {
  sessionId: string
  algorithmVersion: string
  processStatus: string
  environmentStatus: string
  environmentConsistencyScore: number | null
  environmentRiskScore: number
  environmentConfidence: number
  statisticalAnomalyStatus: string
  statisticalAnomalyScore: number
  statisticalAnomalyConfidence: number
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

export function getAdvancedSignals(sessionId: string): Promise<AdvancedSignals | null> {
  return request(`/sessions/${sessionId}/advanced-signals`)
}

export function analyzeAdvancedSignals(sessionId: string): Promise<AdvancedSignals> {
  return request(`/sessions/${sessionId}/advanced-signals/analyze`, { method: 'POST' })
}
