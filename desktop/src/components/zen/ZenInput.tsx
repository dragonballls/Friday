import { useState, useRef, useCallback, useEffect, memo } from 'react'

const LANG_LABELS: Record<string, string> = { 'en-US': 'EN', 'hi-IN': 'HI', 'ur-PK': 'UR' }

const SUGGESTIONS = [
  { label: 'Explain', action: 'Explain this concept in simple terms' },
  { label: 'Search', action: 'Search the web for' },
  { label: 'Code', action: 'Write code to' },
  { label: 'Automate', action: 'Autopilot: ' },
]

interface ZenInputProps {
  onSend: (text: string) => void
  loading: boolean
  onVoiceStart: () => void
  onVoiceStop: () => string
  voiceStatus: 'idle' | 'listening' | 'error'
  voiceInterim: string
  isVoiceSupported: boolean
  voiceLanguage: string
  onCycleLanguage: () => void
  draft?: string
  personaName?: string
}

export const ZenInput = memo(function ZenInput({
  onSend, loading, onVoiceStart, onVoiceStop, voiceStatus, voiceInterim, isVoiceSupported,
  voiceLanguage, onCycleLanguage,
  draft,
  personaName = 'Friday',
}: ZenInputProps) {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const voicePointerRef = useRef<number | null>(null)
  const voiceKeyboardRef = useRef(false)

  useEffect(() => {
    if (draft == null) return
    setValue(draft)
    inputRef.current?.focus()
  }, [draft])

  const send = useCallback(() => {
    const text = value.trim()
    if (text && !loading) {
      setValue('')
      onSend(text)
    }
  }, [value, loading, onSend])

  const stopVoiceAndSend = useCallback(() => {
    if (voicePointerRef.current == null) return
    voicePointerRef.current = null
    const transcript = onVoiceStop()
    if (transcript.trim()) {
      setValue('')
      onSend(transcript.trim())
    }
  }, [onVoiceStop, onSend])

  const startKeyboardVoice = useCallback(() => {
    if (voiceKeyboardRef.current || voicePointerRef.current != null || voiceStatus === 'listening') return
    voiceKeyboardRef.current = true
    onVoiceStart()
  }, [onVoiceStart, voiceStatus])

  const stopKeyboardVoiceAndSend = useCallback(() => {
    if (!voiceKeyboardRef.current) return
    voiceKeyboardRef.current = false
    const transcript = onVoiceStop()
    if (transcript.trim()) {
      setValue('')
      onSend(transcript.trim())
    }
  }, [onVoiceStop, onSend])

  const cancelKeyboardVoice = useCallback(() => {
    if (!voiceKeyboardRef.current) return
    voiceKeyboardRef.current = false
    onVoiceStop()
  }, [onVoiceStop])

  const isListening = voiceStatus === 'listening'
  const borderColor = isListening
    ? 'rgba(255,255,255,0.35)'
    : focused
      ? 'rgba(255,255,255,0.2)'
      : 'rgba(255,255,255,0.08)'

  return (
    <div className="flex justify-end px-4 sm:px-8 pb-4 sm:pb-6 pt-3">
      <div className="w-full min-w-0">
        <div
          className="rounded-2xl transition-all duration-300 glass overflow-hidden"
          style={{
            border: `1px solid ${borderColor}`,
            boxShadow: isListening
              ? '0 8px 40px rgba(0,0,0,0.5), 0 0 60px rgba(255,255,255,0.05)'
              : focused
                ? '0 8px 40px rgba(0,0,0,0.5), 0 0 40px rgba(255,255,255,0.02)'
                : '0 4px 24px rgba(0,0,0,0.3)',
          }}
        >
          <div className="relative flex items-end min-w-0">
            <textarea
              ref={inputRef}
              rows={1}
              value={value}
              onChange={e => setValue(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
              placeholder={`Message ${personaName}...`}
              disabled={loading}
              aria-label={`Message ${personaName}`}
              className="w-full resize-none bg-transparent outline-none text-sm leading-relaxed py-4 pl-4 sm:pl-5 pr-28 sm:pr-32 placeholder:text-neutral-600"
              style={{
                color: '#e5e5e5',
                minHeight: '56px',
                maxHeight: '160px',
                fontWeight: 350,
                letterSpacing: '0.01em',
              }}
            />

            {isListening && voiceInterim && (
              <div
                className="absolute left-4 sm:left-5 right-20 sm:right-24 bottom-full mb-1 px-3 py-1.5 rounded-lg text-xs truncate pointer-events-none glass"
                style={{ color: '#ffffff', border: '1px solid rgba(255,255,255,0.15)' }}
                aria-live="polite"
              >
                {voiceInterim}
              </div>
            )}

            <div className="absolute right-2 bottom-2 flex items-center gap-1.5">
              {isVoiceSupported && (
                <button
                  type="button"
                  onPointerDown={e => {
                    if (e.pointerType === 'mouse' && e.button !== 0) return
                    voicePointerRef.current = e.pointerId
                    e.currentTarget.setPointerCapture?.(e.pointerId)
                    onVoiceStart()
                  }}
                  onPointerUp={e => {
                    if (voicePointerRef.current !== e.pointerId) return
                    stopVoiceAndSend()
                  }}
                  onPointerCancel={e => {
                    if (voicePointerRef.current !== e.pointerId) return
                    voicePointerRef.current = null
                    onVoiceStop()
                  }}
                  onKeyDown={e => {
                    if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) {
                      e.preventDefault()
                      startKeyboardVoice()
                    }
                  }}
                  onKeyUp={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      stopKeyboardVoiceAndSend()
                    }
                  }}
                  onBlur={cancelKeyboardVoice}
                  className="h-9 w-9 shrink-0 rounded-xl flex items-center justify-center transition-all duration-300 active:scale-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
                  style={{
                    background: isListening ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.06)',
                    color: isListening ? '#000' : '#a0a0a8',
                    boxShadow: isListening ? '0 0 16px rgba(255,255,255,0.3)' : 'none',
                    border: isListening ? 'none' : '1px solid rgba(255,255,255,0.1)',
                    touchAction: 'none',
                  }}
                  title={isListening ? 'Release to send' : 'Hold to speak'}
                  aria-label={isListening ? 'Release to send voice message' : 'Hold to speak'}
                >
                  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="23" />
                    <line x1="8" y1="23" x2="16" y2="23" />
                  </svg>
                </button>
              )}

              {isVoiceSupported && (
                <button
                  type="button"
                  onClick={onCycleLanguage}
                  className="h-9 w-8 shrink-0 rounded-xl flex items-center justify-center transition-all duration-200 text-[10px] font-bold tracking-wider focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
                  style={{
                    color: isListening ? '#fff' : '#606068',
                    border: `1px solid ${isListening ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.1)'}`,
                    background: 'transparent',
                  }}
                  title={`Voice language: ${voiceLanguage}. Click to cycle.`}
                  aria-label={`Voice language ${voiceLanguage}. Click to cycle language.`}
                >
                  {LANG_LABELS[voiceLanguage] || 'EN'}
                </button>
              )}

              <button
                type="button"
                onClick={send}
                disabled={!value.trim() || loading}
                className="h-9 w-9 shrink-0 rounded-xl flex items-center justify-center transition-all duration-500 hover:scale-105 active:scale-95 disabled:opacity-25 disabled:hover:scale-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
                style={{
                  background: 'linear-gradient(135deg, #e5e5e5, #ffffff)',
                  color: '#000',
                  fontWeight: 600,
                  fontSize: '16px',
                  boxShadow: value.trim() ? '0 2px 12px rgba(255,255,255,0.25)' : 'none',
                }}
                title={loading ? 'Sending...' : 'Send message'}
                aria-label={loading ? 'Sending message' : 'Send message'}
              >
                {'\u2191'}
              </button>
            </div>
          </div>

          {!value.trim() && !loading && (
            <div className="flex items-center gap-1.5 px-4 sm:px-5 pb-2 overflow-x-auto overscroll-contain" style={{ scrollbarWidth: 'none' }}>
              {SUGGESTIONS.map(s => (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => { setValue(s.action); inputRef.current?.focus() }}
                  className="text-[11px] px-2.5 py-1 rounded-full whitespace-nowrap shrink-0 transition-all duration-150 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:ring-offset-1 focus-visible:ring-offset-black"
                  style={{
                    color: '#777',
                    border: '1px solid rgba(255,255,255,0.06)',
                    background: 'rgba(255,255,255,0.02)',
                  }}
                  aria-label={`Use ${s.label} prompt`}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'
                    e.currentTarget.style.color = '#ccc'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.02)'
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'
                    e.currentTarget.style.color = '#777'
                  }}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
})

