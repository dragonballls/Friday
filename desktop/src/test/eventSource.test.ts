import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { connectEventSource } from '../core/api'

class FakeEventSource {
  static instances: FakeEventSource[] = []
  onmessage: ((msg: { data: string }) => void) | null = null
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  url: string

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  close() {
    this.closed = true
  }
}

function latest() {
  return FakeEventSource.instances[FakeEventSource.instances.length - 1]
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('connectEventSource', () => {
  it('delivers parsed events and ignores malformed payloads', () => {
    const onEvent = vi.fn()
    const stop = connectEventSource(onEvent)

    latest().onmessage?.({ data: JSON.stringify({ type: 'metrics', data: { cpu: 1 } }) })
    latest().onmessage?.({ data: 'not json' })

    expect(onEvent).toHaveBeenCalledTimes(1)
    expect(onEvent).toHaveBeenCalledWith({ type: 'metrics', data: { cpu: 1 } })
    stop()
  })

  it('does not report a drop until the grace period elapses', () => {
    const onError = vi.fn()
    const onStatus = vi.fn()
    const stop = connectEventSource(vi.fn(), onError, onStatus)

    latest().onopen?.()
    onStatus.mockClear()
    latest().onerror?.()

    vi.advanceTimersByTime(3000)
    expect(onStatus).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()

    vi.advanceTimersByTime(2000)
    expect(onStatus).toHaveBeenCalledWith(false)
    expect(onError).toHaveBeenCalledTimes(1)
    stop()
  })

  it('reports a reconnect that lands inside the grace period as uninterrupted', () => {
    const onError = vi.fn()
    const onStatus = vi.fn()
    const stop = connectEventSource(vi.fn(), onError, onStatus)

    latest().onopen?.()
    latest().onerror?.()
    vi.advanceTimersByTime(1000)
    latest().onopen?.()
    vi.advanceTimersByTime(10000)

    expect(onError).not.toHaveBeenCalled()
    expect(onStatus).toHaveBeenCalledTimes(2)
    expect(onStatus).not.toHaveBeenCalledWith(false)
    stop()
  })

  it('backs off exponentially between retries', () => {
    const stop = connectEventSource(vi.fn())

    latest().onerror?.()
    expect(FakeEventSource.instances).toHaveLength(1)
    vi.advanceTimersByTime(1000)
    expect(FakeEventSource.instances).toHaveLength(2)

    latest().onerror?.()
    vi.advanceTimersByTime(1000)
    expect(FakeEventSource.instances).toHaveLength(2)
    vi.advanceTimersByTime(1000)
    expect(FakeEventSource.instances).toHaveLength(3)
    stop()
  })

  it('retries immediately when the tab becomes visible again', () => {
    const stop = connectEventSource(vi.fn())

    latest().onerror?.()
    vi.advanceTimersByTime(1000)
    latest().onerror?.()
    expect(FakeEventSource.instances).toHaveLength(2)

    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))

    expect(FakeEventSource.instances).toHaveLength(3)
    stop()
  })

  it('retries immediately when the network comes back', () => {
    const stop = connectEventSource(vi.fn())

    latest().onerror?.()
    expect(FakeEventSource.instances).toHaveLength(1)

    window.dispatchEvent(new Event('online'))

    expect(FakeEventSource.instances).toHaveLength(2)
    stop()
  })

  it('stops retrying and detaches listeners once closed', () => {
    const onStatus = vi.fn()
    const stop = connectEventSource(vi.fn(), vi.fn(), onStatus)

    latest().onerror?.()
    stop()

    window.dispatchEvent(new Event('online'))
    vi.advanceTimersByTime(60000)

    expect(FakeEventSource.instances).toHaveLength(1)
    expect(onStatus).not.toHaveBeenCalled()
  })
})
