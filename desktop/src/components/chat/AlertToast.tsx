import { useEffect, useRef, useState } from 'react'
import type { ProactiveAlert } from '../../types'

interface AlertToastProps {
  alert: ProactiveAlert
  onDismiss: () => void
}

const SEVERITY_COLORS: Record<string, { border: string; bg: string; icon: string }> = {
  warning: { border: 'rgba(239,68,68,0.4)', bg: 'rgba(239,68,68,0.1)', icon: '\u26A0' },
  info: { border: 'rgba(212,160,64,0.3)', bg: 'rgba(212,160,64,0.08)', icon: '\u2139' },
}

export function AlertToast({ alert, onDismiss }: AlertToastProps) {
  const [visible, setVisible] = useState(false)
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const removeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dismissedRef = useRef(false)
  const sev = SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.info
  const liveRole = alert.severity === 'warning' ? 'alert' : 'status'

  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisible(true))
    dismissTimerRef.current = setTimeout(() => {
      if (dismissedRef.current) return
      dismissedRef.current = true
      setVisible(false)
      removeTimerRef.current = setTimeout(onDismiss, 300)
    }, 6000)

    return () => {
      cancelAnimationFrame(frame)
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
      if (removeTimerRef.current) clearTimeout(removeTimerRef.current)
    }
  }, [onDismiss])

  const dismiss = () => {
    if (dismissedRef.current) return
    dismissedRef.current = true
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    setVisible(false)
    removeTimerRef.current = setTimeout(onDismiss, 300)
  }

  return (
    <div
      className="pointer-events-auto transition-all duration-300"
      role={liveRole}
      aria-atomic="true"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(-12px)',
      }}
    >
      <div
        className="rounded-xl px-3.5 py-2.5 text-xs backdrop-blur-sm"
        style={{
          background: sev.bg,
          border: `1px solid ${sev.border}`,
          maxWidth: '360px',
        }}
      >
        <div className="flex items-start gap-2">
          <span className="mt-0.5 shrink-0" aria-hidden="true">{sev.icon}</span>
          <div className="min-w-0 flex-1">
            <div className="font-medium" style={{ color: '#e5e5e5' }}>{alert.title}</div>
            <div className="mt-0.5 leading-relaxed whitespace-pre-wrap break-words" style={{ color: '#999' }}>{alert.description}</div>
          </div>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Dismiss alert"
            title="Dismiss alert"
            className="shrink-0 -mr-1 -mt-0.5 h-7 w-7 rounded flex items-center justify-center transition-colors hover:bg-white/[.06] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
            style={{ color: '#666' }}
          >
            {'\u2715'}
          </button>
        </div>
        {alert.action_label && (
          <span
            className="inline-block mt-1.5 px-2 py-0.5 rounded text-[10px] font-medium"
            style={{ background: 'rgba(212,160,64,0.15)', color: '#D4A040' }}
          >
            {alert.action_label}
          </span>
        )}
      </div>
    </div>
  )
}
