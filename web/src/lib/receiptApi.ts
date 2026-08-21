import { API_BASE_URL } from './api'
import { clearSession, getToken } from './auth'

export type ReceiptStatus = 'ISSUED' | 'REVOKED' | 'SUPERSEDED'
export type ReceiptIntegrity = 'VALID' | 'INVALID_SIGNATURE' | 'UNKNOWN_SIGNING_KEY' | 'COMPROMISED_SIGNING_KEY' | 'REVOKED' | 'SUPERSEDED'

export type Receipt = {
  id: string
  receiptNumber: string
  lookupToken?: string | null
  receiptType: string
  status: ReceiptStatus
  integrityState: ReceiptIntegrity | string
  signatureState: string
  signatureValid: boolean
  manifestSha256: string
  payloadSha256: string
  score: number
  verdict: string
  confidence: number
  policyVersion: string
  engineVersion: string
  signatureAlgorithm: string
  signingKeyId: string
  issuedAt: string
  revokedAt?: string | null
  revocationReason?: string | null
  lastEvidenceCheckAt?: string | null
  lastEvidenceIntegrity?: string | null
  canonicalPayload?: Record<string, unknown> | null
  signature?: string | null
}

export type EvidenceIntegrity = {
  receiptId: string
  state: 'MATCH' | 'MISMATCH' | 'MISSING' | 'ERROR'
  checkedAt: string
  files: Array<{
    evidenceFileId: string
    type: string
    state: 'MATCH' | 'MISMATCH' | 'MISSING' | 'ERROR'
    expectedSha256: string
    observedSha256?: string | null
    expectedSizeBytes: number
    observedSizeBytes?: number | null
  }>
}

export type PublicReceipt = {
  receiptId: string
  receiptNumber: string
  signatureValid: boolean
  signatureState: string
  receiptStatus: ReceiptStatus
  integrityState: string
  verdict?: string | null
  score?: string | null
  issuedAt: string
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const token = authenticated ? getToken() : null
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
      // Preserve HTTP fallback.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function getSessionReceipt(sessionId: string): Promise<Receipt | null> {
  return request(`/sessions/${sessionId}/receipt`)
}

export function getSessionReceipts(sessionId: string): Promise<Receipt[]> {
  return request(`/sessions/${sessionId}/receipts`)
}

export function issueSessionReceipt(sessionId: string): Promise<Receipt> {
  return request(`/sessions/${sessionId}/receipt/issue`, { method: 'POST' })
}

export function getReceipt(receiptId: string): Promise<Receipt> {
  return request(`/receipts/${receiptId}`)
}

export function verifyEvidence(receiptId: string): Promise<EvidenceIntegrity> {
  return request(`/receipts/${receiptId}/verify-evidence`, { method: 'POST' })
}

export function revokeReceipt(receiptId: string, reason: string): Promise<Receipt> {
  return request(`/receipts/${receiptId}/revoke`, { method: 'POST', body: JSON.stringify({ reason }) })
}

export function getPublicReceipt(token: string): Promise<PublicReceipt> {
  return request(`/receipts/public/${encodeURIComponent(token)}`, {}, false)
}
