import { useEffect, useMemo, useRef, useState } from 'react'
import { checkHealth, streamAutopilot } from './core/barebonesApi'
import { useVoiceInput } from './hooks/useVoiceInput'

type Activity = { time: string; type: string; text: string }
type SavedTask = { goal: string; status: 'running' | 'stopped'; savedAt: number; activity: Activity[] }
const TASK_KEY = 'friday:active-task:v1'

function textFromEvent(event: any): string {
  if (typeof event?.content === 'string') return event.content
  if (typeof event?.message === 'string') return event.message
  if (typeof event?.text === 'string') return event.text
  if (typeof event?.description === 'string') return event.description
  if (typeof event?.task?.description === 'string') return event.task.description
  if (Array.isArray(event?.tools)) return `Tools: ${event.tools.map((tool: any) => tool.name || tool.tool || 'tool').join(', ')}`
  return String(JSON.stringify(event) ?? event)
}

function stamp() {
  return new Date().toLocaleTimeString([], { hour12: false })
}

function loadSavedTask(): SavedTask | null {
  try {
    const raw = window.localStorage.getItem(TASK_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SavedTask
    if (!parsed?.goal || !['running', 'stopped'].includes(parsed.status)) return null
    return parsed
  } catch {
    return null
  }
}

export default function App() {
  const [goal, setGoal] = useState('')
  const [activity, setActivity] = useState<Activity[]>([])
  const [running, setRunning] = useState(false)
  const [apiOnline, setApiOnline] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const resumeAttemptedRef = useRef(false)
  const {
    isSupported,
    status,
    finalTranscript,
    startListening,
    stopListening,
    resetTranscript,
    error: voiceError,
  } = useVoiceInput()

  const activityText = useMemo(
    () => activity.map(item => `[${item.time}] ${item.type}: ${item.text}`).join('\n'),
    [activity],
  )

  useEffect(() => {
    let active = true
    const poll = () => {
      void checkHealth().then(online => {
        if (active) setApiOnline(online)
      })
    }
    poll()
    const timer = window.setInterval(poll, 2000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
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

  useEffect(() => {
    const saved = loadSavedTask()
    if (saved) {
      setGoal(saved.goal)
      setActivity(saved.activity || [])
    }
  }, [])

  useEffect(() => {
    if (!goal.trim()) return
    const saved = loadSavedTask()
    if (!saved) return
    try {
      window.localStorage.setItem(TASK_KEY, JSON.stringify({ ...saved, goal, activity }))
    } catch {
      // Local persistence is best-effort; the running agent remains authoritative.
    }
  }, [goal, activity])

  useEffect(() => {
    if (!apiOnline || running || resumeAttemptedRef.current) return
    const saved = loadSavedTask()
    if (!saved || saved.status !== 'running') return
    resumeAttemptedRef.current = true
    const text = saved.goal.trim()
    if (!text) return

    setRunning(true)
    setError('')
    setActivity(previous => [...previous, { time: stamp(), type: 'RESUME', text: 'Resuming unfinished coding work after startup…' }].slice(-500))
    abortRef.current = streamAutopilot(
      text,
      event => {
        const item = { time: stamp(), type: String(event?.type || 'EVENT').toUpperCase(), text: textFromEvent(event) }
        setActivity(previous => [...previous, item].slice(-500))
      },
      (requestError: any) => {
        const message = requestError?.message || 'Coding run failed.'
        setError(message)
        setRunning(false)
        setActivity(previous => [...previous, { time: stamp(), type: 'ERROR', text: message }].slice(-500))
      },
      () => {
        setRunning(false)
        setActivity(previous => [...previous, { time: stamp(), type: 'STATUS', text: 'Coding run ended.' }].slice(-500))
        abortRef.current = null
        try { window.localStorage.removeItem(TASK_KEY) } catch { /* best effort */ }
      },
    )
  }, [apiOnline, running])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  const persist = (nextStatus: 'running' | 'stopped', nextActivity: Activity[] = activity) => {
    try {
      window.localStorage.setItem(TASK_KEY, JSON.stringify({ goal: goal.trim(), status: nextStatus, savedAt: Date.now(), activity: nextActivity.slice(-500) }))
    } catch {
      // Keep the application usable when browser storage is unavailable.
    }
  }

  const add = (type: string, text: string) => {
    setActivity(previous => [...previous, { time: stamp(), type, text }].slice(-500))
  }

  const start = () => {
    const text = goal.trim()
    if (!text || running || !apiOnline) return

    setError('')
    persist('running')
    setRunning(true)
    add('REQUEST', text)
    add('AGENT', 'Starting a real coding run…')

    abortRef.current = streamAutopilot(
      text,
      event => add(String(event?.type || 'EVENT').toUpperCase(), textFromEvent(event)),
      (requestError: any) => {
        const message = requestError?.message || 'Coding run failed.'
        setError(message)
        add('ERROR', message)
        setRunning(false)
        persist('running')
      },
      () => {
        setRunning(false)
        add('STATUS', 'Coding run ended. The activity feed is the runtime record.')
        abortRef.current = null
        try { window.localStorage.removeItem(TASK_KEY) } catch { /* best effort */ }
      },
    )
  }

  const stop = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
    add('STOP', 'Stopped by user. The task remains saved for manual resume.')
    persist('stopped')
  }

  const toggleVoice = () => {
    if (status === 'listening') {
      stopListening()
      return
    }
    resetTranscript()
    startListening('en-US', false)
  }

  return (
    <div className="barebones">
      <header className="top">
        <div>
          <strong>FRIDAY</strong>
          <span className="sub">self-coding workspace</span>
        </div>
        <div className={apiOnline ? 'online' : 'offline'}>
          {apiOnline ? '● AGENT ONLINE' : '● AGENT OFFLINE'}
        </div>
      </header>

      <main className="main">
        <section className="panel request">
          <div className="label">WHAT SHOULD I BUILD?</div>
          <textarea
            value={goal}
            onChange={event => setGoal(event.target.value)}
            disabled={running}
            placeholder="Tell Friday what to change, build, fix, test, or investigate…"
            autoFocus
          />
          <div className="controls">
            <button onClick={toggleVoice} disabled={!isSupported || running}>
              {status === 'listening' ? '● Listening…' : '🎙 Speak'}
            </button>
            {running ? (
              <button className="danger" onClick={stop}>Stop</button>
            ) : (
              <button className="primary" onClick={start} disabled={!goal.trim() || !apiOnline}>
                {loadSavedTask()?.status === 'stopped' ? 'Resume coding' : 'Start coding'}
              </button>
            )}
          </div>
          {voiceError && <div className="notice">Voice: {voiceError}</div>}
          {error && <div className="error">{error}</div>}
        </section>

        <section className="panel activity">
          <div className="activity-head">
            <div>
              <div className="label">LIVE SELF-CODING ACTIVITY</div>
              <div className="hint">Real events from the agent runtime. No simulated progress.</div>
            </div>
            <span className={running ? 'running' : 'idle'}>{running ? 'RUNNING' : 'IDLE'}</span>
          </div>
          <div className="feed">
            {activity.length === 0 ? (
              <div className="empty">Nothing running yet.</div>
            ) : (
              activity.map((item, index) => (
                <div className="event" key={`${item.time}-${index}`}>
                  <span className="time">{item.time}</span>
                  <span className="type">{item.type}</span>
                  <span className="event-text">{item.text}</span>
                </div>
              ))
            )}
            <div ref={bottomRef} />
          </div>
        </section>
      </main>

      <footer>
        <span>Friday codes in the configured workspace and reports actual runtime events.</span>
        <button className="copy" onClick={() => navigator.clipboard?.writeText(activityText)} disabled={!activity.length}>
          Copy activity
        </button>
      </footer>
    </div>
  )
}
