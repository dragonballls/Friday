import { useEffect, useMemo, useRef, useState } from 'react'
import { streamAutopilot } from './core/api'
import { useVoiceInput } from './hooks/useVoiceInput'

type Activity = { time: string; type: string; text: string }

function textFromEvent(ev: any): string {
  if (typeof ev?.content === 'string') return ev.content
  if (typeof ev?.message === 'string') return ev.message
  if (typeof ev?.text === 'string') return ev.text
  if (typeof ev?.description === 'string') return ev.description
  if (typeof ev?.task?.description === 'string') return ev.task.description
  if (Array.isArray(ev?.tools)) return `Tools: ${ev.tools.map((t: any) => t.name || t.tool || 'tool').join(', ')}`
  return JSON.stringify(ev)
}

function stamp() {
  return new Date().toLocaleTimeString([], { hour12: false })
}

export default function App() {
  const [goal, setGoal] = useState('')
  const [activity, setActivity] = useState<Activity[]>([])
  const [running, setRunning] = useState(false)
  const [apiOnline, setApiOnline] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { isSupported, status, finalTranscript, startListening, stopListening, resetTranscript, error: voiceError } = useVoiceInput()

  const activityText = useMemo(() => activity.map(a => `[${a.time}] ${a.type}: ${a.text}`).join('\n'), [activity])

  useEffect(() => {
    let active = true
    const check = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8080/api/v1/health', { cache: 'no-store' })
        if (active) setApiOnline(response.ok)
      } catch {
        if (active) setApiOnline(false)
      }
    }
    void check()
    const timer = window.setInterval(check, 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  useEffect(() => {
    if (finalTranscript.trim() && status === 'idle') {
      setGoal(finalTranscript.trim())
      resetTranscript()
    }
  }, [finalTranscript, status, resetTranscript])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activity])

  const add = (type: string, text: string) => setActivity(prev => [...prev, { time: stamp(), type, text }].slice(-500))

  const start = () => {
    const text = goal.trim()
    if (!text || running) return
    setError('')
    setRunning(true)
    add('REQUEST', text)
    add('AGENT', 'Starting a real coding run…')
    abortRef.current = streamAutopilot(
      { goal: text },
      (ev: any) => add(String(ev?.type || 'EVENT').toUpperCase(), textFromEvent(ev)),
      (err: any) => {
        const message = err?.message || 'Coding run failed.'
        setError(message)
        add('ERROR', message)
      },
      () => {
        setRunning(false)
        add('STATUS', 'Coding run ended. The activity feed above is the runtime record.')
        abortRef.current = null
      },
    )
  }

  const stop = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
    add('STOP', 'Stopped by user.')
  }

  const toggleVoice = () => {
    if (status === 'listening') stopListening()
    else {
      resetTranscript()
      startListening('en-US', false)
    }
  }

  return (
    <div className="barebones">
      <header className="top">
        <div><strong>FRIDAY</strong><span className="sub">self-coding workspace</span></div>
        <div className={apiOnline ? 'online' : 'offline'}>{apiOnline ? '● AGENT ONLINE' : '● AGENT OFFLINE'}</div>
      </header>

      <main className="main">
        <section className="panel request">
          <div className="label">WHAT SHOULD I BUILD?</div>
          <textarea value={goal} onChange={e => setGoal(e.target.value)} disabled={running} placeholder="Tell Friday what to change, build, fix, test, or investigate…" />
          <div className="controls">
            <button onClick={toggleVoice} disabled={!isSupported || running}>{status === 'listening' ? '● Listening…' : '🎙 Speak'}</button>
            {running ? <button className="danger" onClick={stop}>Stop</button> : <button className="primary" onClick={start} disabled={!goal.trim() || !apiOnline}>Start coding</button>}
          </div>
          {voiceError && <div className="notice">Voice: {voiceError}</div>}
          {error && <div className="error">{error}</div>}
        </section>

        <section className="panel activity">
          <div className="activity-head">
            <div><div className="label">LIVE SELF-CODING ACTIVITY</div><div className="hint">Real events from the agent runtime. No simulated progress.</div></div>
            <span className={running ? 'running' : 'idle'}>{running ? 'RUNNING' : 'IDLE'}</span>
          </div>
          <div className="feed">
            {activity.length === 0 ? <div className="empty">Nothing running yet.</div> : activity.map((item, i) => (
              <div className="event" key={`${item.time}-${i}`}><span className="time">{item.time}</span><span className="type">{item.type}</span><span className="event-text">{item.text}</span></div>
            ))}
            <div ref={bottomRef} />
          </div>
        </section>
      </main>

      <footer>
        <span>Friday codes in the configured workspace and reports its actual runtime events.</span>
        <button className="copy" onClick={() => navigator.clipboard?.writeText(activityText)} disabled={!activity.length}>Copy activity</button>
      </footer>
    </div>
  )
}
