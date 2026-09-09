import { afterEach, describe, expect, it } from 'vitest'
import { state, useStore } from './StateManager'

describe('StateManager session invariants', () => {
  afterEach(() => {
    state.set({
      sessions: [{ id: 'default', title: 'New session', messages: [], createdAt: Date.now() }],
      activeSessionId: 'default',
    })
  })

  it('never leaves the store without a session', () => {
    state.set({ sessions: [], activeSessionId: 'missing' })

    const current = useStore.getState()
    expect(current.sessions).toHaveLength(1)
    expect(current.activeSessionId).toBe(current.sessions[0].id)
    expect(state.activeSession.id).toBe(current.activeSessionId)
  })

  it('repairs an active session id that no longer exists', () => {
    state.set({
      sessions: [
        { id: 'one', title: 'One', messages: [], createdAt: 1 },
        { id: 'two', title: 'Two', messages: [], createdAt: 2 },
      ],
      activeSessionId: 'deleted',
    })

    const current = useStore.getState()
    expect(current.activeSessionId).toBe('one')
    expect(state.activeSession.id).toBe('one')
  })

  it('keeps message updates safe after an empty-session write', () => {
    state.set({ sessions: [] })
    state.updateMessages(messages => [
      ...messages,
      { id: 'm1', role: 'user', content: 'hello' },
    ])

    const current = useStore.getState()
    expect(current.sessions).toHaveLength(1)
    expect(current.sessions[0].messages).toHaveLength(1)
    expect(current.sessions[0].messages[0].content).toBe('hello')
  })
})
