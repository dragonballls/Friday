import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/** Prevent a startup/runtime exception from turning the whole desktop into a blank screen. */
export class StartupGuard extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Friday startup render failed:', error, info.componentStack)
    window.dispatchEvent(new CustomEvent('friday:app-error', {
      detail: { message: error.stack || error.message || String(error) },
    }))
  }

  private reload = () => window.location.reload()

  render() {
    if (!this.state.error) return this.props.children

    return (
      <main
        role="alert"
        style={{
          minHeight: '100%',
          display: 'grid',
          placeItems: 'center',
          padding: 24,
          background: 'var(--bg, #0a0a0f)',
          color: 'var(--text, #f0f0f0)',
        }}
      >
        <section
          style={{
            width: 'min(560px, 100%)',
            padding: 28,
            borderRadius: 18,
            border: '1px solid rgba(239,68,68,.28)',
            background: 'rgba(255,255,255,.04)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 28 }} aria-hidden="true">⚠</div>
          <h1 style={{ marginTop: 12, fontSize: 18 }}>Friday could not render the interface</h1>
          <p style={{ marginTop: 8, color: '#a0a0a8', fontSize: 13 }}>
            The local frontend is running, but a UI component failed during startup.
          </p>
          <details style={{ marginTop: 14, textAlign: 'left' }}>
            <summary style={{ cursor: 'pointer', color: '#fca5a5', fontSize: 12 }}>Technical details</summary>
            <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#999', fontSize: 11 }}>
              {this.state.error.message || String(this.state.error)}
            </pre>
          </details>
          <button
            type="button"
            onClick={this.reload}
            style={{ marginTop: 18, border: 0, borderRadius: 10, padding: '9px 18px', background: 'linear-gradient(135deg, var(--gold, #f59e0b), #ffd166)', color: '#000', cursor: 'pointer', fontWeight: 600 }}
          >
            Reload Friday
          </button>
        </section>
      </main>
    )
  }
}
