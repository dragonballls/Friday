import type { FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { checkHealth, streamAutopilot, streamChat } from './core/api'

const SELF_CODING_GOAL =
  'Continue improving Jarvis. Inspect the current Jarvis workspace, identify the highest-value safe improvement, implement it, verify it, preserve existing working behavior, and leave the workspace in a working state. Work incrementally and keep durable progress in the workspace so another run can continue after interruption.'

const SELF_CODING_RESTART_MS = 1_500
const SELF_CODING_RETRY_MS = 10_000

function App() {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [response, setResponse] = useState('')
  const codingTimerRef = useRef<number | null>(null)
  const codingControllerRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (codingTimerRef.current !== null) {
        window.clearTimeout(codingTimerRef.current)
        codingTimerRef.current = null
      }
      codingControllerRef.current?.abort()
      codingControllerRef.current = null
    }
  }, [])

  const speak = (text: string) => {
    if (!text.trim() || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.94
    utterance.pitch = 0.95
    window.speechSynthesis.speak(utterance)
  }

  const sendMessage = (event?: FormEvent) => {
    event?.preventDefault()
    const message = input.trim()
    if (!message || busy) return

    setInput('')
    setResponse('')
    setBusy(true)

    let fullResponse = ''
    streamChat(
      { message, session_id: 'default', persona: 'jarvis' },
      (chunk) => {
        const content = String(chunk?.content ?? '')
        if (!content) return
        fullResponse += content
        if (mountedRef.current) setResponse(fullResponse)
      },
      (err) => {
        const text = `I encountered an error: ${String(err?.message ?? err ?? 'unknown error')}`
        fullResponse = text
        if (mountedRef.current) setResponse(text)
      },
      () => {
        if (!mountedRef.current) return
        setBusy(false)
        if (fullResponse.trim()) speak(fullResponse)
      },
    )
  }

  useEffect(() => {
    let cancelled = false

    const runSelfCoding = () => {
      if (cancelled) return

      const sessionId = `jarvis-self-coding-${Date.now()}`
      codingControllerRef.current = streamAutopilot(
        {
          goal: SELF_CODING_GOAL,
          session_id: sessionId,
        },
        () => {
          // Self-coding output stays non-visual. Durable progress belongs in the workspace.
        },
        () => {
          codingControllerRef.current = null
          scheduleNext(SELF_CODING_RETRY_MS)
        },
        () => {
          codingControllerRef.current = null
          scheduleNext(SELF_CODING_RESTART_MS)
        },
      )
    }

    const scheduleNext = (delay: number) => {
      if (cancelled) return
      if (codingTimerRef.current !== null) window.clearTimeout(codingTimerRef.current)
      codingTimerRef.current = window.setTimeout(runSelfCoding, delay)
    }

    const boot = async () => {
      try {
        await checkHealth()
        if (!cancelled) runSelfCoding()
      } catch {
        scheduleNext(SELF_CODING_RETRY_MS)
      }
    }

    void boot()

    return () => {
      cancelled = true
      if (codingTimerRef.current !== null) {
        window.clearTimeout(codingTimerRef.current)
        codingTimerRef.current = null
      }
      codingControllerRef.current?.abort()
      codingControllerRef.current = null
    }
  }, [])

  return (
    <main className="jarvis-shell">
      <form className="jarvis-bar" onSubmit={sendMessage}>
        <input
          className="jarvis-input"
          aria-label="Chat with Jarvis"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={busy ? 'Jarvis is thinking…' : 'Talk to Jarvis…'}
          autoFocus
          disabled={busy}
          autoComplete="off"
          spellCheck={false}
        />
      </form>

      <div className="jarvis-sr-only" aria-live="polite">
        {response}
      </div>
    </main>
  )
}

export default App
