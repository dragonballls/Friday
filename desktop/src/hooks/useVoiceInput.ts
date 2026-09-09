import { useState, useRef, useCallback, useEffect } from 'react'

export type VoiceStatus = 'idle' | 'listening' | 'error'

interface UseVoiceInputReturn {
  isSupported: boolean
  status: VoiceStatus
  interimTranscript: string
  finalTranscript: string
  error: string | null
  startListening: (lang?: string, autoRestart?: boolean) => void
  stopListening: () => string
  cancelAutoRestart: () => void
  resetTranscript: () => void
}

const RESTART_DEBOUNCE = 300

export function useVoiceInput(): UseVoiceInputReturn {
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [finalTranscript, setFinalTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)

  const recognitionRef = useRef<any>(null)
  const finalRef = useRef('')
  const autoRestartRef = useRef(false)
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const langRef = useRef('en-US')
  const sessionGenRef = useRef(0)

  const isSupported =
    typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const clearRestartTimer = useCallback(() => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
  }, [])

  const resetTranscript = useCallback(() => {
    setInterimTranscript('')
    setFinalTranscript('')
    finalRef.current = ''
    setError(null)
  }, [])

  const cancelAutoRestart = useCallback(() => {
    autoRestartRef.current = false
    sessionGenRef.current += 1
    clearRestartTimer()
  }, [clearRestartTimer])

  const startListening = useCallback((lang?: string, autoRestart?: boolean) => {
    if (!isSupported) {
      setError('Speech recognition not supported')
      return
    }

    cancelAutoRestart()
    autoRestartRef.current = autoRestart ?? false
    const generation = sessionGenRef.current

    if (recognitionRef.current) {
      try { recognitionRef.current.abort() } catch {}
      recognitionRef.current = null
    }

    langRef.current = lang || 'en-US'

    const SpeechRecognitionCtor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    let recognition: any
    try {
      recognition = new SpeechRecognitionCtor()
    } catch {
      setStatus('error')
      setError('Failed to initialize speech recognition')
      return
    }

    const scheduleRestart = () => {
      if (!autoRestartRef.current || sessionGenRef.current !== generation) return
      clearRestartTimer()
      restartTimerRef.current = setTimeout(() => {
        restartTimerRef.current = null
        if (autoRestartRef.current && sessionGenRef.current === generation) {
          startListening(langRef.current, true)
        }
      }, RESTART_DEBOUNCE)
    }

    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = langRef.current

    recognition.onresult = (event: any) => {
      if (sessionGenRef.current !== generation) return
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalRef.current += transcript
          setFinalTranscript(finalRef.current)
        } else {
          interim += transcript
        }
      }
      setInterimTranscript(interim)
    }

    recognition.onerror = (event: any) => {
      if (sessionGenRef.current !== generation) return
      const code = event?.error || 'unknown'
      if (code === 'no-speech' || code === 'aborted') {
        setStatus('idle')
        scheduleRestart()
      } else {
        setStatus('error')
        setError(code)
      }
    }

    recognition.onend = () => {
      if (sessionGenRef.current !== generation) return
      setStatus('idle')
      setInterimTranscript('')
      scheduleRestart()
    }

    recognitionRef.current = recognition
    setStatus('listening')
    setError(null)
    finalRef.current = ''
    setFinalTranscript('')
    setInterimTranscript('')

    try {
      recognition.start()
    } catch {
      if (sessionGenRef.current === generation) {
        recognitionRef.current = null
        setStatus('error')
        setError('Failed to start recognition')
      }
    }
  }, [isSupported, cancelAutoRestart, clearRestartTimer])

  const stopListening = useCallback((): string => {
    autoRestartRef.current = false
    sessionGenRef.current += 1
    clearRestartTimer()
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
      recognitionRef.current = null
    }
    const transcript = finalRef.current
    return transcript
  }, [clearRestartTimer])

  useEffect(() => {
    return () => {
      autoRestartRef.current = false
      sessionGenRef.current += 1
      clearRestartTimer()
      if (recognitionRef.current) {
        try { recognitionRef.current.abort() } catch {}
      }
    }
  }, [clearRestartTimer])

  return { isSupported, status, interimTranscript, finalTranscript, error, startListening, stopListening, cancelAutoRestart, resetTranscript }
}