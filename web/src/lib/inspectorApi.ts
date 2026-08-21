import { clearSession, getToken } from './auth'
import { API_BASE_URL, type Inspector, type Page } from './api'

type ErrorBody = { error?: { message?: string } }

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
      // Use the HTTP fallback message.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export type InspectorCreatePayload = {
  fullName: string
  email: string
  password: string
  employeeCode?: string
  phone?: string
}

export type InspectorUpdatePayload = {
  fullName?: string
  employeeCode?: string | null
  phone?: string | null
  active?: boolean
}

export function listInspectors(search = '', active?: boolean): Promise<Page<Inspector>> {
  const params = new URLSearchParams({ page: '1', pageSize: '100' })
  if (search.trim()) params.set('search', search.trim())
  if (typeof active === 'boolean') params.set('active', String(active))
  return request(`/inspectors?${params.toString()}`)
}

export function createInspector(payload: InspectorCreatePayload): Promise<Inspector> {
  return request('/inspectors', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateInspector(id: string, payload: InspectorUpdatePayload): Promise<Inspector> {
  return request(`/inspectors/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function resetInspectorPassword(id: string, password: string): Promise<void> {
  return request(`/inspectors/${id}/password`, {
    method: 'PUT',
    body: JSON.stringify({ password }),
  })
}
