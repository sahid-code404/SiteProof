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
      <section className="login-visual">
        <div className="login-copy">
          <p className="eyebrow">FIELD EVIDENCE, WITH CONTEXT</p>
          <h1>SiteProof</h1>
          <p>Coordinate inspections, assign field teams and preserve an auditable trail before live verification begins.</p>
          <div className="signal-grid">
            <span>01 · Location</span><span>02 · Assignment</span><span>03 · Audit</span><span>04 · Readiness</span>
          </div>
        </div>
      </section>
      <section className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <span className="brand-mark large">SP</span>
          <div><p className="eyebrow">AUTHORIZED ACCESS</p><h2>Sign in to the control desk</h2></div>
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" minLength={8} required /></label>
          {mutation.isError ? <p className="form-error">{mutation.error.message}</p> : null}
          <button className="button primary" disabled={mutation.isPending}>{mutation.isPending ? 'Signing in…' : 'Sign in'}</button>
          <small className="muted">Credentials are verified by the SiteProof backend. No demo data is stored in the browser.</small>
        </form>
      </section>
    </main>
  )
}
