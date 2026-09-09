import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Friday crashed a component:', error, info.componentStack)
    window.dispatchEvent(new CustomEvent('friday:app-error', {
      detail: { message: error.stack || error.message || String(error) },
    }))
  }

  private reset = () => {
    this.setState({ hasError: false, message: '' })
  }

  render() {
    if (!this.state.hasError) return this.props.children

    if (this.props.fallback) return this.props.fallback

    return (
      <div role="alert" style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'grid', placeItems: 'center', padding: 24, background: '#0a0a0c', color: '#f0f0f0' }}>
        <div style={{ width: 'min(560px, 100%)', padding: 28, borderRadius: 18, border: '1px solid rgba(239,68,68,.28)', background: 'rgba(255,255,255,.04)', textAlign: 'center' }}>
          <div style={{ fontSize: 28 }} aria-hidden="true">⚠</div>
          <h1 style={{ marginTop: 12, fontSize: 18 }}>Friday hit an unexpected error</h1>
          <p style={{ marginTop: 8, color: '#a0a0a8', fontSize: 13 }}>The interface failed to render. The error below can be used to diagnose the exact component.</p>
          <details style={{ marginTop: 14, textAlign: 'left' }} open>
            <summary style={{ cursor: 'pointer', color: '#fca5a5', fontSize: 12 }}>Technical details</summary>
            <pre style={{ marginTop: 8, maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#c0c0c8', fontSize: 11 }}>{this.state.message || 'An unexpected error occurred.'}</pre>
          </details>
          <button type="button" onClick={this.reset} style={{ marginTop: 18, border: 0, borderRadius: 10, padding: '9px 18px', background: 'linear-gradient(135deg, #f59e0b, #ffd166)', color: '#000', cursor: 'pointer', fontWeight: 600 }}>Try again</button>
          <button type="button" onClick={() => window.location.reload()} style={{ marginTop: 10, marginLeft: 8, border: '1px solid rgba(255,255,255,.12)', borderRadius: 10, padding: '9px 18px', background: 'rgba(255,255,255,.05)', color: '#ddd', cursor: 'pointer' }}>Reload page</button>
        </div>
      </div>
    )
  }
}

export function AppErrorFallback() {
  return (
    <div role="alert" style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'grid', placeItems: 'center', background: '#0a0a0c', color: '#f0f0f0' }}>
      <div style={{ width: 'min(28rem,calc(100vw - 2rem))', padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 28 }} aria-hidden="true">⚠</div>
        <h1 style={{ marginTop: 12, fontSize: 16 }}>Friday hit an unexpected error</h1>
        <button type="button" onClick={() => window.location.reload()} style={{ marginTop: 16, border: 0, borderRadius: 10, padding: '9px 18px', background: 'linear-gradient(135deg, #f59e0b, #ffd166)', color: '#000', cursor: 'pointer', fontWeight: 600 }}>Reload app</button>
      </div>
    </div>
  )
}
