import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { watchForUpdates } from '../core/autoUpdate'

function html(hash: string) {
  return `<!doctype html><html><head><link href="/assets/index-${hash}.css"></head>` +
    `<body><script type="module" src="/assets/index-${hash}.js"></script></body></html>`
}

let fetchMock: ReturnType<typeof vi.fn>

function serve(body: string) {
  fetchMock.mockResolvedValue({ ok: true, text: async () => body })
}

async function flush() {
  await vi.advanceTimersByTimeAsync(0)
}

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('watchForUpdates', () => {
  it('does not fire while the build is unchanged', async () => {
    serve(html('aaa'))
    const onUpdate = vi.fn()
    const stop = watchForUpdates({ intervalMs: 1000, onUpdate })

    await flush()
    await vi.advanceTimersByTimeAsync(5000)

    expect(fetchMock).toHaveBeenCalled()
    expect(onUpdate).not.toHaveBeenCalled()
    stop()
  })

  it('fires once when the built assets change', async () => {
    serve(html('aaa'))
    const onUpdate = vi.fn()
    const stop = watchForUpdates({ intervalMs: 1000, onUpdate })
    await flush()

    serve(html('bbb'))
    await vi.advanceTimersByTimeAsync(1000)
    expect(onUpdate).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(3000)
    expect(onUpdate).toHaveBeenCalledTimes(1)
    stop()
  })

  it('checks as soon as the tab becomes visible again', async () => {
    serve(html('aaa'))
    const onUpdate = vi.fn()
    const stop = watchForUpdates({ intervalMs: 600_000, onUpdate })
    await flush()

    serve(html('bbb'))
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await flush()

    expect(onUpdate).toHaveBeenCalledTimes(1)
    stop()
  })

  it('ignores failed and empty responses', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))
    const onUpdate = vi.fn()
    const stop = watchForUpdates({ intervalMs: 1000, onUpdate })
    await flush()

    serve(html('aaa'))
    await vi.advanceTimersByTimeAsync(1000)
    serve(html('bbb'))
    await vi.advanceTimersByTimeAsync(1000)

    // The first successful response becomes the baseline, so only the real
    // change reports an update.
    expect(onUpdate).toHaveBeenCalledTimes(1)
    stop()
  })

  it('stops polling once unsubscribed', async () => {
    serve(html('aaa'))
    const onUpdate = vi.fn()
    const stop = watchForUpdates({ intervalMs: 1000, onUpdate })
    await flush()
    stop()

    serve(html('bbb'))
    await vi.advanceTimersByTimeAsync(10_000)
    window.dispatchEvent(new Event('online'))
    await flush()

    expect(onUpdate).not.toHaveBeenCalled()
  })
})
