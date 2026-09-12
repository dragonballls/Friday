import type { FormEvent } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { streamAutopilot, streamChat, checkHealth } from './core/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface SpeechRecognitionResultEventLike {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}

interface SpeechRecognitionLike {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionResultEventLike) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
}

const DEFAULT_SELF_CODING_GOAL =
  'Continue improving Friday toward a JARVIS-class AI assistant. Inspect the current workspace, identify the highest-value safe improvement, implement it, verify it, and leave the workspace in a working state.'

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: 'Good evening. I’m Friday. I’m ready to talk and improve myself.' },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [codingBusy, setCodingBusy] = useState(false)
  const [codingGoal, setCodingGoal] = useState(DEFAULT_SELF_CODING_GOAL)
  const [codingLog, setCodingLog] = useState<string[]>([])
  const [online, setOnline] = useState(false)
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const autoCodingStarted = useRef(false)

  const SpeechRecognitionCtor = useMemo(
    () => window.SpeechRecognition || window.webkitSpeechRecognition,
    [],
  )

  useEffect(() => {
    checkHealth().then(() => setOnline(true)).catch(() => setOnline(false))
  }, [])

  useEffect(() => {
    return () => recognitionRef.current?.stop()
  }, [])

  const speak = (text: string) => {
    if (!('speechSynthesis' in window) || !text.trim()) return
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
    setMessages(prev => [...prev, { role: 'user', content: message }, { role: 'assistant', content: '' }])
    setBusy(true)

    streamChat(
      { message, session_id: 'default', persona: 'jarvis' },
      (chunk) => {
        const content = String(chunk?.content ?? '')
        if (!content) return
        setMessages(prev => {
          const next = [...prev]
          const last = next[next.length - 1]
          next[next.length - 1] = { ...last, content: last.content + content }
          return next
        })
      },
      (err) => {
        const text = `I encountered an error: ${String(err?.message ?? err ?? 'unknown error')}`
        setMessages(prev => {
          const next = [...prev]
          next[next.length - 1] = { role: 'assistant', content: text }
          return next
        })
        setOnline(false)
      },
      () => {
        setBusy(false)
        setOnline(true)
        setMessages(prev => {
          const text = prev[prev.length - 1]?.content || ''
          if (text.trim()) speak(text)
          return prev
        })
      },
    )
  }

  const toggleListening = () => {
    if (!SpeechRecognitionCtor) return

    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      return
    }

    const recognition = new SpeechRecognitionCtor()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results as any)
        .map((result: any) => result[0]?.transcript ?? '')
        .join(' ')
        .trim()
      if (transcript) {
        setInput(transcript)
        window.setTimeout(() => sendMessage(), 0)
      }
    }
    recognition.onend = () => setListening(false)
    recognition.onerror = () => setListening(false)
    recognitionRef.current = recognition
    setListening(true)
    recognition.start()
  }

  const runSelfCoding = (goal: string) => {
    if (!goal || codingBusy) return
    setCodingLog([`Starting self-coding task: ${goal}`])
    setCodingBusy(true)

    streamAutopilot(
      { goal, session_id: 'default' },
      (chunk) => {
        const content = String(chunk?.content ?? '')
        if (content) setCodingLog(prev => [...prev, content])
      },
      (err) => {
        setCodingLog(prev => [...prev, `Error: ${String(err?.message ?? err ?? 'unknown error')}`])
      },
      () => setCodingBusy(false),
    )
  }

  useEffect(() => {
    if (!online || autoCodingStarted.current) return
    autoCodingStarted.current = true
    runSelfCoding(DEFAULT_SELF_CODING_GOAL)
  }, [online])

  const startSelfCoding = (event?: FormEvent) => {
    event?.preventDefault()
    runSelfCoding(codingGoal.trim())
  }

  return (
    <main className="friday-shell">
      <header className="friday-header">
        <div>
          <div className="eyebrow">FRIDAY</div>
          <h1>Your AI assistant.</h1>
        </div>
        <div className={`status ${online ? 'online' : ''}`}>
          <span /> {online ? 'ONLINE' : 'CONNECTING'}
        </div>
      </header>

      <section className="conversation card">
        <div className="section-title">Conversation</div>
        <div className="messages">
          {messages.map((message, index) => (
            <div key={`${index}-${message.role}`} className={`message ${message.role}`}>
              <span className="message-label">{message.role === 'assistant' ? 'FRIDAY' : 'YOU'}</span>
              <div>{message.content || '…'}</div>
            </div>
          ))}
        </div>
        <form className="composer" onSubmit={sendMessage}>
          <input
            value={input}
            onChange={event => setInput(event.target.value)}
            placeholder="Talk to Friday…"
            disabled={busy}
            autoFocus
          />
          <button type="button" className={listening ? 'active' : ''} onClick={toggleListening} disabled={!SpeechRecognitionCtor}>
            {listening ? 'Stop' : 'Voice'}
          </button>
          <button type="submit" disabled={busy || !input.trim()}>{busy ? 'Thinking…' : 'Send'}</button>
        </form>
      </section>

      <section className="self-code card">
        <div className="section-title">Self-coding</div>
        <p className="muted">Friday starts a safe improvement run automatically and stays available for conversation.</p>
        <form className="composer" onSubmit={startSelfCoding}>
          <input
            value={codingGoal}
            onChange={event => setCodingGoal(event.target.value)}
            placeholder="What should Friday build or improve?"
            disabled={codingBusy}
          />
          <button type="submit" disabled={codingBusy || !codingGoal.trim()}>{codingBusy ? 'Working…' : 'Run again'}</button>
        </form>
        <div className="coding-log" aria-live="polite">
          {codingLog.length === 0 ? <span className="muted">No coding task running.</span> : codingLog.map((line, index) => <div key={index}>{line}</div>)}
        </div>
      </section>
    </main>
  )
}

export default App
