export type AuthUser = {
  id: string
  organizationId: string
  email: string
  fullName: string
  role: 'ADMIN' | 'INSPECTOR' | 'REVIEWER'
}

const TOKEN_KEY = 'siteproof.accessToken'
const USER_KEY = 'siteproof.user'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getStoredUser(): AuthUser | null {
  const value = localStorage.getItem(USER_KEY)
  if (!value) return null
  try {
    return JSON.parse(value) as AuthUser
  } catch {
    clearSession()
    return null
  }
}
