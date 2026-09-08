import { memo, useEffect, useRef, useState } from 'react'

interface OnboardingProps {
  onDismiss: () => void
  onSuggest: (text: string) => void
}

const FLAGSHIP_SUGGESTIONS = [
  'Autopilot: organize my desktop and summarize',
  'Remember that my name is Tony',
  'What happened today in tech news?',
  'Set an automation to remind me to stand up hourly',
]

/**
 * P3 — "Hello, I'm Friday" first-launch onboarding. Shows once (persisted to
 * localStorage) inside zen mode: a short greeting plus flagship suggestions.
 */
export const Onboarding = memo(function Onboarding({ onDismiss, onSuggest }: OnboardingProps) {
  const [visible, setVisible] = useState(true)
  const firstSuggestionRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const seen = localStorage.getItem('friday_onboarded')
    if (seen === '1') setVisible(false)
  }, [])

  useEffect(() => {
    if (!visible) return
    firstSuggestionRef.current?.focus()

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismiss()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [visible])

  if (!visible) return null

  const dismiss = () => {
    try { localStorage.setItem('friday_onboarded', '1') } catch {}
    setVisible(false)
    onDismiss()
  }

  return (
    <div
      className="absolute inset-0 z-40 flex items-center justify-center p-4 sm:p-6"
      style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
      onMouseDown={event => { if (event.target === event.currentTarget) dismiss() }}
      role="presentation"
    >
      <div
        className="w-[min(440px,92vw)] max-h-[calc(100vh-2rem)] overflow-y-auto rounded-2xl glass animate-fade-slide-up p-5 sm:p-6"
        style={{ border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 25px 60px rgba(0,0,0,0.6)' }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="friday-onboarding-title"
        aria-describedby="friday-onboarding-description"
      >
        <div className="text-center mb-4">
          <div id="friday-onboarding-title" className="text-lg font-thin tracking-[0.25em] uppercase mb-2" style={{ color: '#fff' }}>Hello, I'm Friday</div>
          <div id="friday-onboarding-description" className="text-[11px] leading-relaxed" style={{ color: '#a0a0a8' }}>
            Your desktop command center. Ask me anything, or try one of these to get started.
          </div>
        </div>

        <div className="space-y-2 mb-5">
          {FLAGSHIP_SUGGESTIONS.map((s, index) => (
            <button
              key={s}
              ref={index === 0 ? firstSuggestionRef : undefined}
              type="button"
              onClick={() => { onSuggest(s); dismiss() }}
              className="w-full text-left px-3 py-2 rounded-lg text-[12px] transition-all duration-200 hover:bg-white/[.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
              style={{ color: '#ccc', border: '1px solid rgba(255,255,255,0.07)', background: 'rgba(255,255,255,0.02)' }}
              aria-label={`Try suggestion: ${s}`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex justify-center">
          <button
            type="button"
            onClick={dismiss}
            className="px-5 py-2 rounded-lg text-[12px] font-mono tracking-widest transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            style={{ color: '#a0a0a8', border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.03)' }}
            aria-label="Dismiss Friday onboarding"
          >
            GET STARTED
          </button>
        </div>
      </div>
    </div>
  )
})
