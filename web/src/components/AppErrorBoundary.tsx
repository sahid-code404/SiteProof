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
          <div className="error-orbit" aria-hidden="true">SP</div>
          <p className="eyebrow">Recovery mode</p>
          <h1>SiteProof hit an unexpected problem</h1>
          <p>Your saved inspection data has not been changed. Reload the workspace to reconnect and continue.</p>
          <button className="button primary" type="button" onClick={() => window.location.reload()}>
            Reload workspace
          </button>
        </div>
      </main>
    )
  }
}
