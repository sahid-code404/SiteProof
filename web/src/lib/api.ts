const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const BACKEND_BASE_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

export async function getBackendHealth(): Promise<{ status: string; service: string }> {
  const response = await fetch(`${BACKEND_BASE_URL}/health`)
  if (!response.ok) throw new Error('Backend health check failed')
  return response.json()
}

export { API_BASE_URL }
