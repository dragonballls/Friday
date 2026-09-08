import { memo, useCallback, useEffect, useRef } from 'react'
import type { OrbState } from '../../types'
import { PERSONA_VISUALS } from '../center/AiCore'

const ORB_STATE_LABELS: Record<string, string> = {
  idle: 'IDLE',
  listening: 'LISTENING',
  thinking: 'THINKING',
  reasoning: 'REASONING',
  executing: 'EXECUTING',
  searching: 'SEARCHING',
  coding: 'CODING',
  speaking: 'SPEAKING',
  error: 'ERROR',
  offline: 'OFFLINE',
}

interface ShareMomentProps {
  open: boolean
  onClose: () => void
  orbState: OrbState
  persona: string
  message: string
  time: string
  greeting?: string
}

export const ShareMoment = memo(function ShareMoment({
  open,
  onClose,
  orbState,
  persona,
  message,
  time,
  greeting,
}: ShareMomentProps) {
  const cardRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const visual = PERSONA_VISUALS[persona] || PERSONA_VISUALS.friday
  const displayName = greeting || visual.name

  useEffect(() => {
    if (!open) return
    closeButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const handleDownload = useCallback(() => {
    const card = cardRef.current
    if (!card) return
    const canvas = document.createElement('canvas')
    canvas.width = 1080
    canvas.height = 1350
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.fillStyle = '#0a0a0f'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    ctx.strokeStyle = 'rgba(255,255,255,0.08)'
    ctx.lineWidth = 2
    ctx.strokeRect(24, 24, canvas.width - 48, canvas.height - 48)

    const cx = canvas.width / 2
    ctx.fillStyle = visual.color
    ctx.font = '400 88px Inter, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(displayName, cx, 240)

    ctx.strokeStyle = 'rgba(255,255,255,0.2)'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.arc(cx, 520, 220, 0, Math.PI * 2)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(cx, 520, 140, 0, Math.PI * 2)
    ctx.stroke()

    ctx.fillStyle = visual.color
    ctx.font = '400 40px Inter, sans-serif'
    ctx.fillText(ORB_STATE_LABELS[orbState] ?? orbState.toUpperCase(), cx, 580)

    ctx.fillStyle = 'rgba(160,160,168,1)'
    ctx.font = '400 36px Inter, sans-serif'
    const label = `${displayName} · ${time}`
    ctx.fillText(label, cx, 800)

    const snippet = message.length > 120 ? message.slice(0, 120) + '…' : message
    ctx.fillStyle = 'rgba(229,229,229,1)'
    ctx.font = '400 32px Inter, sans-serif'
    const lines = snippet.split('\n').slice(0, 3)
    lines.forEach((line, i) => {
      ctx.fillText(line, cx, 880 + i * 48)
    })

    ctx.fillStyle = 'rgba(96,96,104,1)'
    ctx.font = '300 26px Inter, sans-serif'
    ctx.fillText('github.com/alimaandev/Friday', cx, 1280)

    const link = document.createElement('a')
    link.download = `friday-moment-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }, [orbState, persona, message, time, displayName, visual.color])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-fade-in"
      style={{ background: 'rgba(0,0,0,0.7)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Share Friday moment"
    >
      <div className="flex flex-col items-center gap-4 max-h-full max-w-full" onClick={e => e.stopPropagation()}>
        <div
          ref={cardRef}
          className="relative w-[min(320px,calc(100vw-2rem))] max-h-[calc(100vh-9rem)] aspect-[4/5] rounded-2xl overflow-hidden glass animate-fade-slide-up"
          style={{ border: '1px solid rgba(255,255,255,0.1)' }}
        >
          <div className="absolute inset-0 flex flex-col items-center justify-center px-6 sm:px-8 text-center min-h-0">
            <div className="text-[clamp(24px,8vw,40px)] font-thin tracking-[0.3em] uppercase break-words" style={{ color: visual.color }}>
              {displayName}
            </div>
            <div
              className="mt-6 sm:mt-8 w-28 h-28 sm:w-36 sm:h-36 shrink-0 rounded-full"
              style={{
                border: `2px solid ${orbState === 'offline' ? 'rgba(255,255,255,0.15)' : `${visual.color}66`}`,
                boxShadow: orbState === 'offline' ? 'none' : `0 0 40px ${visual.color}33`,
              }}
            />
            <div className="mt-4 text-xs tracking-[0.25em]" style={{ color: '#a0a0a8' }}>
              {ORB_STATE_LABELS[orbState] ?? orbState.toUpperCase()}
            </div>
            <div className="mt-6 sm:mt-8 text-xs" style={{ color: '#606068' }}>
              {displayName.toUpperCase ? displayName.toUpperCase() : displayName} · {time}
            </div>
            {message && (
              <div className="mt-4 text-sm leading-relaxed max-h-24 overflow-y-auto overscroll-contain break-words" style={{ color: '#ccc' }}>
                {message}
              </div>
            )}
            <div className="mt-auto pt-4 pb-4 sm:pb-6 text-[9px] sm:text-[10px] tracking-widest break-all" style={{ color: '#404048' }}>
              github.com/alimaandev/Friday
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={handleDownload}
            className="px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 hover:scale-105 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            style={{
              background: 'linear-gradient(135deg, #e5e5e5, #ffffff)',
              color: '#000',
            }}
          >
            Download PNG
          </button>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl text-sm transition-all duration-200 hover:bg-white/[.06] glass focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            style={{ color: '#a0a0a8' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
})
