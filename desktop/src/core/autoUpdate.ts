const POLL_INTERVAL = 60_000
const MIN_POLL_INTERVAL = 1_000
const ASSET_PATTERN = /(?:src|href)="([^"]+\.(?:js|css))"/g

function fingerprintOf(html: string): string {
  return [...html.matchAll(ASSET_PATTERN)].map(m => m[1]).sort().join('|')
}

async function fetchFingerprint(): Promise<string | null> {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}index.html?_=${Date.now()}`, { cache: 'no-store' })
    if (!res.ok) return null
    return fingerprintOf(await res.text())
  } catch {
    return null
  }
}

export interface UpdateWatcherOptions {
  intervalMs?: number
  onUpdate?: () => void
}

export function watchForUpdates(options: UpdateWatcherOptions = {}): () => void {
  const requestedInterval = options.intervalMs ?? POLL_INTERVAL
  const intervalMs = Number.isFinite(requestedInterval)
    ? Math.max(MIN_POLL_INTERVAL, requestedInterval)
    : POLL_INTERVAL
  const onUpdate = options.onUpdate ?? (() => window.location.reload())
  let stopped = false
  let baseline: string | null = null
  let checking = false

  async function check() {
    if (stopped || checking) return
    checking = true
    try {
      const current = await fetchFingerprint()
      if (stopped || current === null || current === '') return
      if (baseline === null) baseline = current
      else if (current !== baseline) {
        baseline = current
        onUpdate()
      }
    } finally {
      checking = false
    }
  }

  const onVisibility = () => {
    if (document.visibilityState === 'visible') void check()
  }
  const onOnline = () => void check()
  const timer = setInterval(() => void check(), intervalMs)

  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('online', onOnline)
  void check()

  return () => {
    stopped = true
    clearInterval(timer)
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('online', onOnline)
  }
}
