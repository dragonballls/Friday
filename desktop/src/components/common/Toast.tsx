import { useEffect, useRef, useState } from 'react'
import { subscribeToasts, dismissToast, getToasts, subscribeToastHistory, getToastHistory, clearToastHistory } from '../../core/ToastStore'
import type { ToastItem } from '../../core/ToastStore'

const KIND_STYLES: Record<ToastItem['kind'], { border: string; bg: string; icon: string }> = {
  success: { border: 'rgba(52,211,153,0.4)', bg: 'rgba(52,211,153,0.1)', icon: '\u2713' },
  error: { border: 'rgba(239,68,68,0.4)', bg: 'rgba(239,68,68,0.1)', icon: '\u26A0' },
  warning: { border: 'rgba(251,191,36,0.4)', bg: 'rgba(251,191,36,0.1)', icon: '\u26A0' },
  info: { border: 'rgba(59,130,246,0.4)', bg: 'rgba(59,130,246,0.1)', icon: '\u2139' },
}

function formatTime(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>(() => getToasts())
  const [history, setHistory] = useState<ToastItem[]>(() => getToastHistory())
  const [activityOpen, setActivityOpen] = useState(false)
  const activityRef = useRef<HTMLElement | null>(null)
  const activityButtonRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    const unsubscribe = subscribeToasts(list => setToasts(list))
    const unsubscribeHistory = subscribeToastHistory(list => setHistory(list))
    return () => { unsubscribe(); unsubscribeHistory() }
  }, [])

  useEffect(() => {
    if (!activityOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setActivityOpen(false)
        activityButtonRef.current?.focus()
      }
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null
      if (target && activityRef.current?.contains(target)) return
      if (target && activityButtonRef.current?.contains(target)) return
      setActivityOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [activityOpen])

  useEffect(() => {
    if (activityOpen) {
      window.requestAnimationFrame(() => {
        const clearButton = activityRef.current?.querySelector<HTMLButtonElement>('[data-activity-clear]')
        clearButton?.focus()
      })
    }
  }, [activityOpen])

  return (
    <>
      <div className="fixed bottom-4 right-4 z-[90] flex flex-col gap-2 pointer-events-none w-[min(20rem,calc(100vw-2rem))] max-h-[calc(100vh-2rem)] overflow-y-auto overscroll-contain" aria-live="polite" aria-atomic="false" aria-label="Notifications">
        {toasts.map(t => {
          const s = KIND_STYLES[t.kind]
          return (
            <div key={t.id} role={t.kind === 'error' ? 'alert' : 'status'} className="rounded-xl px-3.5 py-2.5 text-xs backdrop-blur-sm flex items-start gap-2.5 pointer-events-auto" style={{ background: s.bg, border: `1px solid ${s.border}` }}>
              <span className="mt-0.5 shrink-0" aria-hidden="true">{s.icon}</span>
              <span className="min-w-0 flex-1 leading-relaxed" style={{ color: '#e5e5e5' }}>{t.message}</span>
              <button type="button" onClick={() => dismissToast(t.id)} aria-label="Dismiss notification" title="Dismiss" className="shrink-0 -mr-1 -mt-0.5 h-7 w-7 rounded-lg flex items-center justify-center transition-colors hover:bg-white/[.06] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]" style={{ color: '#888' }}>×</button>
            </div>
          )
        })}
      </div>

      <div className="fixed bottom-4 left-4 z-[89] pointer-events-auto">
        <button
          ref={activityButtonRef}
          type="button"
          onClick={() => setActivityOpen(open => !open)}
          aria-expanded={activityOpen}
          aria-controls="friday-activity-center"
          aria-haspopup="dialog"
          aria-label={`Notification activity, ${history.length} entries`}
          title="Notification activity"
          className="relative h-9 px-3 rounded-xl text-[11px] backdrop-blur-md transition-colors hover:bg-white/[.08] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
          style={{ background: 'rgba(20,20,20,0.82)', border: '1px solid rgba(255,255,255,0.08)', color: '#888' }}
        >
          activity
          {history.length > 0 && <span className="ml-2 text-[#D4A040]">{history.length}</span>}
        </button>

        {activityOpen && (
          <section ref={activityRef} id="friday-activity-center" role="dialog" aria-modal="false" aria-label="Notification activity center" className="absolute bottom-11 left-0 w-[min(20rem,calc(100vw-2rem))] max-h-[min(60vh,32rem)] rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl" style={{ background: 'rgba(14,14,14,0.96)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="flex items-center justify-between gap-3 px-3.5 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              <div className="min-w-0">
                <div className="text-xs text-white/75">Activity center</div>
                <div className="text-[10px] text-white/30 mt-0.5">Recent Friday notifications</div>
              </div>
              {history.length > 0 && <button type="button" data-activity-clear onClick={() => { clearToastHistory(); setActivityOpen(false); activityButtonRef.current?.focus() }} className="shrink-0 min-h-7 px-2 rounded-lg text-[10px] text-white/45 hover:text-white/80 hover:bg-white/[.05] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">Clear</button>}
            </div>
            <div className="max-h-[calc(min(60vh,32rem)-58px)] overflow-y-auto overscroll-contain p-2">
              {history.length === 0 ? (
                <div className="py-8 text-center text-[11px] text-white/30">No activity yet.</div>
              ) : history.map(item => {
                const s = KIND_STYLES[item.kind]
                return (
                  <div key={item.id} className="flex gap-2.5 px-2.5 py-2 rounded-lg hover:bg-white/[.03]">
                    <span className="shrink-0 mt-0.5" style={{ color: s.icon === '\u2713' ? '#7dd3b0' : '#aaa' }} aria-hidden="true">{s.icon}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[11px] leading-4 text-white/65 break-words">{item.message}</div>
                      <time className="text-[9px] text-white/25" dateTime={new Date(item.createdAt).toISOString()}>{formatTime(item.createdAt)}</time>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        )}
      </div>
    </>
  )
}