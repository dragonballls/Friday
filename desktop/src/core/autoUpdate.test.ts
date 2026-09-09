import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { watchForUpdates } from './autoUpdate'

describe('watchForUpdates', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('establishes a baseline without reloading on the first check', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => '<script src="/assets/app.123.js"></script>',
    }) as typeof fetch
    const onUpdate = vi.fn()

    const stop = watchForUpdates({ intervalMs: 60_000, onUpdate })
    await Promise.resolve()
    await Promise.resolve()

    expect(onUpdate).not.toHaveBeenCalled()
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    stop()
  })

  it('detects a changed asset fingerprint on the next poll', async () => {
    const responses = [
      '<script src="/assets/app.123.js"></script>',
      '<script src="/assets/app.456.js"></script>',
    ]
    globalThis.fetch = vi.fn().mockImplementation(async () => ({
      ok: true,
      text: async () => responses.shift() ?? '<script src="/assets/app.456.js"></script>',
    })) as typeof fetch
    const onUpdate = vi.fn()

    const stop = watchForUpdates({ intervalMs: 1_000, onUpdate })
    await Promise.resolve()
    await Promise.resolve()
    await vi.advanceTimersByTimeAsync(1_000)

    expect(onUpdate).toHaveBeenCalledTimes(1)
    stop()
  })

  it('uses the one-second default polling interval', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => '<script src="/assets/app.123.js"></script>',
    }) as typeof fetch
    const onUpdate = vi.fn()

    const stop = watchForUpdates({ onUpdate })
    await Promise.resolve()
    await Promise.resolve()

    await vi.advanceTimersByTimeAsync(999)
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    stop()
  })

  it('clamps an invalid polling interval to a safe minimum', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => '<script src="/assets/app.123.js"></script>',
    }) as typeof fetch
    const onUpdate = vi.fn()

    const stop = watchForUpdates({ intervalMs: -1, onUpdate })
    await Promise.resolve()
    await Promise.resolve()

    await vi.advanceTimersByTimeAsync(999)
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    stop()
  })

  it('falls back to the one-second default for non-finite values', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => '<script src="/assets/app.123.js"></script>',
    }) as typeof fetch
    const onUpdate = vi.fn()

    const stop = watchForUpdates({ intervalMs: Number.NaN, onUpdate })
    await Promise.resolve()
    await Promise.resolve()

    await vi.advanceTimersByTimeAsync(999)
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    stop()
  })

  it('stops polling and event listeners when cleaned up', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => '<link href="/assets/app.123.css">',
    }) as typeof fetch
    const onUpdate = vi.fn()

    const stop = watchForUpdates({ intervalMs: 1_000, onUpdate })
    await Promise.resolve()
    await Promise.resolve()
    stop()

    await vi.advanceTimersByTimeAsync(5_000)
    window.dispatchEvent(new Event('online'))
    document.dispatchEvent(new Event('visibilitychange'))

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    expect(onUpdate).not.toHaveBeenCalled()
  })
})
