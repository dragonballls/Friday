const POLL_INTERVAL = 60_000
const ASSET_PATTERN = /(?:src|href)="([^"]+\.(?:js|css))"/g

function fingerprintOf(html: string): string {
  const assets = [...html.matchAll(ASSET_PATTERN)].map((m) => m[1])
  return assets.sort().join('|')
}

async function fetchFingerprint(): Promise<string | null> {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}index.html?_=${Date.now()}`, {
      cache: 'no-store',
    })
    if (!res.ok) return null
    return fingerprintOf(await res.text())
  } catch {
    return null
  }
}

export interface UpdateWatcherOptions {
  intervalMs?: number
  // Defaults to a full reload; overridable so callers can defer or prompt.
  onUpdate?: () => void
}

/**
 * Watch the served index.html for a new build and pick it up without the user
 * reloading. Checks on an interval, whenever the tab becomes visible, and
 * whenever the network comes back. Returns an unsubscribe function.
 */
export function watchForUpdates(options: UpdateWatcherOptions = {}): () => void {
  const intervalMs = options.intervalMs ?? POLL_INTERVAL
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
      if (baseline === null) {
        baseline = current
        return
      }
      if (current !== baseline) {
        baseline = current
        onUpdate()
      }
    } finally {
      checking = false
    }
  }

  function onVisibilityChange() {
    if (document.visibilityState === 'visible') void check()
  }

  function onOnline() {
    void check()
  }

  const timer = setInterval(() => void check(), intervalMs)
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('online', onOnline)
  void check()

  return () => {
    stopped = true
    clearInterval(timer)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('online', onOnline)
  }
}
