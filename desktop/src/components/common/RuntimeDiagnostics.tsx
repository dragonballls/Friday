import { useEffect, useState } from 'react'

interface RuntimeError {
  message: string
  source?: string
}

/** Keeps unexpected browser-side failures visible instead of silently breaking the UI. */
export function RuntimeDiagnostics() {
  const [error, setError] = useState<RuntimeError | null>(null)

  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      setError({
        message: event.error?.message || event.message || 'Unknown browser error',
        source: event.filename ? `${event.filename}:${event.lineno || 0}:${event.colno || 0}` : undefined,
      })
    }
    const onRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason
      setError({
        message: reason?.message || String(reason || 'Unhandled promise rejection'),
      })
    }

    window.addEventListener('error', onError)
    window.addEventListener('unhandledrejection', onRejection)
    return () => {
      window.removeEventListener('error', onError)
      window.removeEventListener('unhandledrejection', onRejection)
    }
  }, [])

  if (!error) return null

  return (
    <aside
      role="alert"
      style={{
        position: 'fixed',
        left: 12,
        right: 12,
        bottom: 12,
        zIndex: 10000,
        padding: '10px 12px',
        border: '1px solid rgba(239,68,68,.35)',
        borderRadius: 10,
        background: 'rgba(20,10,12,.96)',
        color: '#fca5a5',
        font: '12px/1.45 ui-monospace, SFMono-Regular, Consolas, monospace',
        boxShadow: '0 8px 30px rgba(0,0,0,.35)',
      }}
    >
      <strong>Friday runtime error</strong>
      <div style={{ marginTop: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{error.message}</div>
      {error.source && <div style={{ marginTop: 4, color: '#9ca3af' }}>{error.source}</div>}
    </aside>
  )
}
