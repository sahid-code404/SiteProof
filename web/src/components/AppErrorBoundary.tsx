import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { failed: boolean; message?: string }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(error: Error): State {
    return { failed: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('SiteProof UI failure', error, info)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <main className="fatal-error-page">
        <section className="fatal-error-card" role="alert">
          <img className="login-brand-logo" src="/siteproof-icon.svg" alt="" aria-hidden="true" />
          <p className="eyebrow">Recovery</p>
          <h1>SiteProof could not open this screen</h1>
          <p>{this.state.message || 'An unexpected interface error occurred.'}</p>
          <p className="muted">Your server data has not been changed. Reload the workspace to retry the screen.</p>
          <button className="button primary" type="button" onClick={() => window.location.reload()}>Reload workspace</button>
        </section>
      </main>
    )
  }
}
