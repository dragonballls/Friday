import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearToastHistory, clearToasts, getToastHistory, getToasts, toast } from '../core/ToastStore'

describe('ToastStore activity history', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    clearToasts()
    clearToastHistory()
  })

  afterEach(() => {
    clearToasts()
    clearToastHistory()
    vi.useRealTimers()
  })

  it('keeps dismissed notifications in bounded activity history', () => {
    toast('success', 'Saved', 1000)
    expect(getToasts()).toHaveLength(1)
    expect(getToastHistory()).toHaveLength(1)

    vi.advanceTimersByTime(1000)
    expect(getToasts()).toHaveLength(0)
    expect(getToastHistory()[0].message).toBe('Saved')
  })

  it('keeps only the newest 50 history entries', () => {
    for (let i = 0; i < 55; i += 1) toast('info', `Event ${i}`, 0)
    expect(getToastHistory()).toHaveLength(50)
    expect(getToastHistory()[0].message).toBe('Event 54')
    expect(getToastHistory()[49].message).toBe('Event 5')
  })
})
