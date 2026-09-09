import { useCallback, useEffect, useRef, useState } from 'react'

const POLL_INTERVAL = 1_000
const MIN_POLL_INTERVAL = 1_000
const ASSET_PATTERN = /(?:src|href)="([^"]+\.(?:js|css))"/g

type UpdateStatus = 'checking' | 'current' | 'available' | 'offline'

function fingerprintOf(html: string): string {
  return [...html.matchAll(ASSET_PATTERN)].map(match => match[1]).sort().join('|')
}

async function fetchFingerprint(): Promise<string | null> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}index.html?_=${Date.now()}`, {
      cache: 'no-store',
      headers: { Accept: 'text/html' },
    })
    if (!response.ok) return null
    const fingerprint = fingerprintOf(await response.text())
    return fingerprint || null
  } catch {
    return null
  }
}

export function UpdateSection() {
  const [status, setStatus] = useState<UpdateStatus>('checking')
  const [expanded, setExpanded] = useState(false)
  const baselineRef = useRef<string | null>(null)
  const checkingRef = useRef(false)

  const check = useCallback(async () => {
    if (checkingRef.current) return
    checkingRef.current = true
    setStatus('checking')
    try {
      const current = await fetchFingerprint()
      if (current === null) {
        setStatus('offline')
        return
      }
      if (baselineRef.current === null) {
        baselineRef.current = current
        setStatus('current')
        return
      }
      if (current !== baselineRef.current) {
        baselineRef.current = current
        setStatus('available')
        window.location.reload()
        return
      }
      setStatus('current')
    } finally {
      checkingRef.current = false
    }
  }, [])

  useEffect(() => {
    void check()
    const timer = window.setInterval(() => void check(), Math.max(MIN_POLL_INTERVAL, POLL_INTERVAL))
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void check()
    }
    const onOnline = () => void check()
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('online', onOnline)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('online', onOnline)
    }
  }, [check])

  const label = status === 'checking'
    ? 'Checking…'
    : status === 'available'
      ? 'Update available — reloading…'
      : status === 'offline'
        ? 'Update check offline'
        : 'Friday is up to date'

  return (
    <div className="py-2">
      <button
        type="button"
        onClick={() => setExpanded(value => !value)}
        className="w-full flex items-center justify-between gap-3 text-left"
        aria-expanded={expanded}
        aria-label="Update status"
      >
        <span className="text-[11px]" style={{ color: status === 'available' ? '#00a8ff' : '#777' }}>
          {label}
        </span>
        <span className="text-[10px]" style={{ color: '#555' }}>{expanded ? '−' : '+'}</span>
      </button>

      {expanded && (
        <div className="pt-2 flex items-center justify-between gap-2">
          <span className="text-[10px]" style={{ color: '#555' }}>
            Checks every second while this page is open.
          </span>
          <button
            type="button"
            onClick={() => void check()}
            disabled={status === 'checking'}
            className="shrink-0 px-2.5 py-1 rounded-lg text-[10px] disabled:opacity-40"
            style={{ color: '#888', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            Check now
          </button>
        </div>
      )}
    </div>
  )
}
