import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { watchForUpdates } from '../core/autoUpdate'

const html = (hash: string) => `<link href="/assets/index-${hash}.css"><script src="/assets/index-${hash}.js"></script>`

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('watchForUpdates', () => {
  it('establishes a baseline without reloading', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, text: async () => html('a') } as Response)
    const update = vi.fn()
    const stop = watchForUpdates({ intervalMs: 1000, onUpdate: update })
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(3000)
    expect(update).not.toHaveBeenCalled()
    stop()
  })

  it('reloads once when the asset fingerprint changes', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, text: async () => html('a') } as Response)
    const update = vi.fn()
    const stop = watchForUpdates({ intervalMs: 1000, onUpdate: update })
    await vi.advanceTimersByTimeAsync(0)
    vi.mocked(fetch).mockResolvedValue({ ok: true, text: async () => html('b') } as Response)
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(3000)
    expect(update).toHaveBeenCalledTimes(1)
    stop()
  })

  it('checks when the tab becomes visible', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, text: async () => html('a') } as Response)
    const update = vi.fn()
    const stop = watchForUpdates({ intervalMs: 600_000, onUpdate: update })
    await vi.advanceTimersByTimeAsync(0)
    vi.mocked(fetch).mockResolvedValue({ ok: true, text: async () => html('b') } as Response)
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(update).toHaveBeenCalledTimes(1)
    stop()
  })

  it('ignores failed responses', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('offline'))
    const update = vi.fn()
    const stop = watchForUpdates({ intervalMs: 1000, onUpdate: update })
    await vi.advanceTimersByTimeAsync(2000)
    expect(update).not.toHaveBeenCalled()
    stop()
  })
})
