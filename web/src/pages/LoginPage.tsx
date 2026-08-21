import { type FormEvent, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { login } from '../lib/api'
import { setSession } from '../lib/auth'

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    mutationFn: () => login(email.trim(), password),
    onSuccess(data) {
      setSession(data.accessToken, data.user)
      navigate('/', { replace: true })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <main className="login-page">
      <section className="login-visual" aria-label="About SiteProof">
        <div className="login-copy">
          <p className="eyebrow">Field verification</p>
          <h1>SiteProof</h1>
          <p>Capture field evidence, verify where it came from and keep a clear record of every decision.</p>
          <div className="signal-grid" aria-label="SiteProof workflow">
            <span>Assigned work</span>
            <span>Live capture</span>
            <span>Verification</span>
            <span>Review history</span>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={submit} aria-busy={mutation.isPending}>
          <img className="login-brand-logo" src="/siteproof-icon.svg" alt="" aria-hidden="true" />
          <div>
            <p className="eyebrow">Welcome back</p>
            <h2>Sign in</h2>
          </div>
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" minLength={8} required />
          </label>
          {mutation.isError ? <p className="form-error" role="alert">{mutation.error.message}</p> : null}
          <button className="button primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Signing in…' : 'Sign in'}</button>
          <small className="muted">Use your SiteProof account.</small>
        </form>
      </section>
    </main>
  )
}
