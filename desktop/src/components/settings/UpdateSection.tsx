import { useCallback, useEffect, useState } from 'react'

const POLL_INTERVAL = 60_000
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
  const [baseline, setBaseline] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)

  const check = useCallback(async () => {
    setStatus('checking')
    const current = await fetchFingerprint()
    if (current === null) {
      setStatus('offline')
      return
    }
    if (baseline === null) {
      setBaseline(current)
      setStatus('current')
      return
    }
    setStatus(current === baseline ? 'current' : 'available')
  }, [baseline])

  useEffect(() => {
    void check()
    const timer = window.setInterval(() => void check(), POLL_INTERVAL)
    return () => window.clearInterval(timer)
  }, [check])

  const reload = () => window.location.reload()
  const label = status === 'checking'
    ? 'Checking…'
    : status === 'available'
      ? 'Update available'
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
            Checks every minute while this page is open.
          </span>
          {status === 'available' ? (
            <button
              type="button"
              onClick={reload}
              className="shrink-0 px-2.5 py-1 rounded-lg text-[10px]"
              style={{ color: '#00a8ff', border: '1px solid rgba(0,168,255,0.2)' }}
            >
              Update now
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void check()}
              disabled={status === 'checking'}
              className="shrink-0 px-2.5 py-1 rounded-lg text-[10px] disabled:opacity-40"
              style={{ color: '#888', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              Check now
            </button>
          )}
        </div>
      )}
    </div>
  )
}
