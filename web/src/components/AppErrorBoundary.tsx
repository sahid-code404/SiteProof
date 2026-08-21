import { Component, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { hasError: boolean }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <main className="app-error-page" role="alert">
        <div className="app-error-card">
          <span className="brand-mark large" aria-hidden="true">SP</span>
          <p className="eyebrow">SITEPROOF RECOVERY</p>
          <h1>This screen could not be displayed.</h1>
          <p>The current evidence has not been changed. Reload the application to restore the control desk.</p>
          <button className="button primary" type="button" onClick={() => window.location.reload()}>
            Reload SiteProof
          </button>
        </div>
      </main>
    )
  }
}
