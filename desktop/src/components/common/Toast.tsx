import { useEffect, useState } from 'react'
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

  useEffect(() => {
    const unsubscribe = subscribeToasts(list => setToasts(list))
    const unsubscribeHistory = subscribeToastHistory(list => setHistory(list))
    return () => { unsubscribe(); unsubscribeHistory() }
  }, [])

  return (
    <>
      <div className="fixed bottom-4 right-4 z-[90] flex flex-col gap-2 pointer-events-none w-80 max-w-[calc(100vw-2rem)]" aria-live="polite" aria-atomic="false" aria-label="Notifications">
        {toasts.map(t => {
          const s = KIND_STYLES[t.kind]
          return (
            <div key={t.id} role={t.kind === 'error' ? 'alert' : 'status'} className="rounded-xl px-3.5 py-2.5 text-xs backdrop-blur-sm flex items-start gap-2.5 pointer-events-auto" style={{ background: s.bg, border: `1px solid ${s.border}` }}>
              <span className="mt-0.5 shrink-0" aria-hidden="true">{s.icon}</span>
              <span className="min-w-0 flex-1 leading-relaxed" style={{ color: '#e5e5e5' }}>{t.message}</span>
              <button type="button" onClick={() => dismissToast(t.id)} aria-label="Dismiss notification" title="Dismiss" className="shrink-0 -mr-1 -mt-0.5 h-5 w-5 rounded flex items-center justify-center transition-colors hover:bg-white/[.06] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]" style={{ color: '#666' }}>×</button>
            </div>
          )
        })}
      </div>

      <div className="fixed bottom-4 left-4 z-[89] pointer-events-auto">
        <button
          type="button"
          onClick={() => setActivityOpen(open => !open)}
          aria-expanded={activityOpen}
          aria-controls="friday-activity-center"
          aria-label={`Notification activity, ${history.length} entries`}
          title="Notification activity"
          className="relative h-9 px-3 rounded-xl text-[11px] backdrop-blur-md transition-colors hover:bg-white/[.08] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
          style={{ background: 'rgba(20,20,20,0.82)', border: '1px solid rgba(255,255,255,0.08)', color: '#888' }}
        >
          activity
          {history.length > 0 && <span className="ml-2 text-[#D4A040]">{history.length}</span>}
        </button>

        {activityOpen && (
          <section id="friday-activity-center" aria-label="Notification activity center" className="absolute bottom-11 left-0 w-80 max-w-[calc(100vw-2rem)] max-h-[60vh] rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl" style={{ background: 'rgba(14,14,14,0.96)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="flex items-center justify-between px-3.5 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              <div>
                <div className="text-xs text-white/75">Activity center</div>
                <div className="text-[10px] text-white/30 mt-0.5">Recent Friday notifications</div>
              </div>
              {history.length > 0 && <button type="button" onClick={clearToastHistory} className="text-[10px] text-white/35 hover:text-white/70 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">Clear</button>}
            </div>
            <div className="max-h-[calc(60vh-58px)] overflow-y-auto p-2">
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
