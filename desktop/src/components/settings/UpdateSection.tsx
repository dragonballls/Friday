import { useCallback, useEffect, useState } from 'react'

const POLL_INTERVAL = 60_000
const ASSET_PATTERN = /(?:src|href)="([^"]+\.(?:js|css))"/g

function fingerprintOf(html: string): string {
  return [...html.matchAll(ASSET_PATTERN)].map(match => match[1]).sort().join('|')
}

async function fetchFingerprint(): Promise<string | null> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}index.html?_=${Date.now()}`, { cache: 'no-store' })
    if (!response.ok) return null
    return fingerprintOf(await response.text())
  } catch {
    return null
  }
}

export function UpdateSection() {
  const [status, setStatus] = useState<'checking' | 'current' | 'available' | 'offline'>('checking')
  const [baseline, setBaseline] = useState<string | null>(null)

  const check = useCallback(async () => {
    setStatus('checking')
    const current = await fetchFingerprint()
    if (!current) {
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

  return (
    <div className="py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm" style={{ color: '#ccc' }}>Updates</div>
          <div className="text-[11px] mt-1" style={{ color: '#666' }}>
            {status === 'checking' && 'Checking for the latest build…'}
            {status === 'current' && 'Friday is up to date.'}
            {status === 'available' && 'A newer build is available.'}
            {status === 'offline' && 'Update check unavailable; Friday will retry automatically.'}
          </div>
        </div>
        {status === 'available' ? (
          <button
            onClick={reload}
            className="px-3 py-1 rounded-lg text-xs transition-all hover:bg-white/[.05]"
            style={{ color: '#00a8ff', border: '1px solid rgba(0,168,255,0.2)' }}
          >
            Update now
          </button>
        ) : (
          <button
            onClick={() => void check()}
            disabled={status === 'checking'}
            className="px-3 py-1 rounded-lg text-xs transition-all hover:bg-white/[.05] disabled:opacity-40"
            style={{ color: '#888', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            Check now
          </button>
        )}
      </div>
    </div>
  )
}
