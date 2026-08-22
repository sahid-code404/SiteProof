import { type FormEvent, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { login } from '../lib/api'
import { setSession } from '../lib/auth'

function friendlyLoginError(error: unknown) {
  const raw = error instanceof Error ? error.message : 'Unable to sign in.'
  if (/invalid email or password/i.test(raw)) return 'Email or password is incorrect.'
  if (/validation/i.test(raw)) return 'Check the email address and password, then try again.'
  if (/failed to fetch|network|load failed/i.test(raw)) return 'Cannot reach SiteProof. Check the server or your connection and try again.'
  return raw
}

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: () => login(email.trim(), password),
    onSuccess(data) {
      setSession(data.accessToken, data.user)
      navigate('/', { replace: true })
    },
  })
  const message = useMemo(() => localError ?? (mutation.isError ? friendlyLoginError(mutation.error) : null), [localError, mutation.isError, mutation.error])

  function submit(event: FormEvent) {
    event.preventDefault()
    setLocalError(null)
    const normalized = email.trim()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) {
      setLocalError('Enter a valid email address, for example name@example.com.')
      return
    }
    if (password.length < 8) {
      setLocalError('Password must contain at least 8 characters.')
      return
    }
    mutation.mutate()
  }

  const loading = mutation.isPending

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <form className="login-form" onSubmit={submit} aria-busy={loading} noValidate>
          <div className="login-brand-row">
            <img className="login-brand-logo" src="/siteproof-icon.svg" alt="" aria-hidden="true" />
            <div className="login-brand-copy"><strong>SiteProof</strong><span>Field verification</span></div>
          </div>

          <div>
            <p className="eyebrow">Secure access</p>
            <h1 id="login-title">Sign in</h1>
          </div>
          <p>Open inspections, review evidence and manage verified field work.</p>

          <label>
            Email
            <input
              type="email"
              inputMode="email"
              value={email}
              onChange={(event) => { setEmail(event.target.value); setLocalError(null) }}
              autoComplete="username"
              placeholder="name@example.com"
              disabled={loading}
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => { setPassword(event.target.value); setLocalError(null) }}
              autoComplete="current-password"
              placeholder="Your password"
              disabled={loading}
              required
            />
          </label>

          {message ? <div className="form-error" role="alert"><strong>Sign-in failed.</strong> {message}</div> : null}

          <button className="button primary" type="submit" disabled={loading || !email.trim() || !password}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <div className="login-trust-row" aria-label="Verification capabilities"><span>Location</span><span>Motion</span><span>Evidence</span></div>
          <small className="login-help">Use the account issued by your SiteProof administrator.</small>
        </form>
      </section>
    </main>
  )
}
