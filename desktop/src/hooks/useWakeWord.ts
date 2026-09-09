import { useState, useRef, useCallback, useEffect } from 'react'

interface UseWakeWordReturn {
  isSupported: boolean
  active: boolean
  listening: boolean
  error: string | null
  start: () => void
  stop: () => void
}

const WAKE_PATTERN = /\bhey\s*friday\b/i
const COOLDOWN_MS = 5000
const SESSION_RENEW_INTERVAL = 40000
const RESTART_DEBOUNCE = 300

export function useWakeWord(onWake: () => void): UseWakeWordReturn {
  const [active, setActive] = useState(false)
  const [listening, setListening] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const recognitionRef = useRef<any>(null)
  const cooldownRef = useRef(0)
  const activeRef = useRef(false)
  const sessionGenRef = useRef(0)
  const renewIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onWakeRef = useRef(onWake)
  onWakeRef.current = onWake

  const isSupported =
    typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const stop = useCallback(() => {
    if (renewIntervalRef.current) {
      clearInterval(renewIntervalRef.current)
      renewIntervalRef.current = null
    }
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.abort() } catch {}
      recognitionRef.current = null
    }
    activeRef.current = false
    sessionGenRef.current += 1
    setActive(false)
    setListening(false)
  }, [])

  const startSession = useCallback(() => {
    if (!activeRef.current) return

    const SpeechRecognitionCtor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    let recognition: any
    try {
      recognition = new SpeechRecognitionCtor()
    } catch {
      setError('Failed to initialize wake word detection')
      setActive(false)
      setListening(false)
      activeRef.current = false
      return
    }

    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'en-US'

    const gen = sessionGenRef.current

    recognition.onresult = (event: any) => {
      if (!activeRef.current || gen !== sessionGenRef.current || recognitionRef.current !== recognition) return
      const now = Date.now()
      if (now - cooldownRef.current < COOLDOWN_MS) return
      const results = event?.results
      const resultIndex = Number.isInteger(event?.resultIndex) ? event.resultIndex : 0
      if (!results || typeof results.length !== 'number') return
      for (let i = Math.max(0, resultIndex); i < results.length; i++) {
        const transcript = results[i]?.[0]?.transcript
        if (typeof transcript !== 'string') continue
        if (WAKE_PATTERN.test(transcript)) {
          cooldownRef.current = now
          onWakeRef.current()
          break
        }
      }
    }

    recognition.onerror = (event: any) => {
      if (gen !== sessionGenRef.current || recognitionRef.current !== recognition) return
      const code = event?.error || 'unknown'
      if (code !== 'no-speech' && code !== 'aborted') {
        setError(code || 'Wake word detection error')
      }
    }

    recognition.onend = () => {
      if (gen !== sessionGenRef.current) return
      setListening(false)
      if (recognitionRef.current === recognition) {
        recognitionRef.current = null
      }
      if (activeRef.current && gen === sessionGenRef.current) {
        if (restartTimerRef.current) clearTimeout(restartTimerRef.current)
        restartTimerRef.current = setTimeout(() => {
          restartTimerRef.current = null
          if (activeRef.current && gen === sessionGenRef.current) {
            startSession()
          }
        }, RESTART_DEBOUNCE)
      }
    }

    recognitionRef.current = recognition

    try {
      recognition.start()
      setListening(true)
      setError(null)
    } catch {
      if (recognitionRef.current === recognition) recognitionRef.current = null
      setError('Failed to start wake word detection')
      setListening(false)
      activeRef.current = false
      setActive(false)
    }
  }, [])

  const start = useCallback(() => {
    if (!isSupported) {
      setError('Speech recognition not supported')
      return
    }

    stop()
    activeRef.current = true
    sessionGenRef.current += 1
    setActive(true)
    setError(null)

    startSession()

    renewIntervalRef.current = setInterval(() => {
      if (!activeRef.current) return
      sessionGenRef.current += 1
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current)
        restartTimerRef.current = null
      }
      if (recognitionRef.current) {
        try { recognitionRef.current.abort() } catch {}
        recognitionRef.current = null
      }
      startSession()
    }, SESSION_RENEW_INTERVAL)
  }, [isSupported, stop, startSession])

  useEffect(() => {
    return () => {
      if (renewIntervalRef.current) clearInterval(renewIntervalRef.current)
      if (restartTimerRef.current) clearTimeout(restartTimerRef.current)
      if (recognitionRef.current) {
        try { recognitionRef.current.abort() } catch {}
      }
      activeRef.current = false
      sessionGenRef.current += 1
    }
  }, [])

  return { isSupported, active, listening, error, start, stop }
}