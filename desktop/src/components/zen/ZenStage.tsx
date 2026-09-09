import { memo, useRef, useEffect, useState } from 'react'
import type { Message, OrbState, AutopilotRun } from '../../types'
import { OrbCore } from './OrbCore'
import { ZenInput } from './ZenInput'
import { MessageBubble } from '../chat/MessageBubble'
import { BrainView } from '../autopilot/BrainView'
import { ShareMoment } from './ShareMoment'
import { PERSONA_VISUALS } from '../center/personaVisuals'

interface ZenStageProps {
  orbState: OrbState
  metrics: { latency: number; model: string; provider: string; memory: number; tokenUsage: number }
  messages: Message[]
  autopilotRun: AutopilotRun | null
  onSend: (text: string) => void
  onStop: () => void
  onRegenerate: () => void
  loading: boolean
  voiceInputSupported: boolean
  voiceStatus: 'idle' | 'listening' | 'error'
  voiceInterim: string
  voiceLanguage: string
  onVoiceStart: () => void
  onVoiceStop: () => string
  onCycleLanguage: () => void
  onToggleDashboard: () => void
  handsFree?: boolean
  ambientActive?: boolean
  onToggleHandsFree?: () => void
  persona?: string
  personaName?: string
  greeting?: string
  continuity?: string
  computerReady?: boolean
  blackout?: boolean
  temperature?: number | null
  location?: string
  time?: string
  handPosition?: { x: number; y: number } | null
  voiceActivity?: boolean
}

export const ZenStage = memo(function ZenStage({
  orbState,
  metrics,
  messages,
  autopilotRun,
  onSend,
  onStop,
  onRegenerate,
  loading,
  voiceInputSupported,
  voiceStatus,
  voiceInterim,
  voiceLanguage,
  onVoiceStart,
  onVoiceStop,
  onCycleLanguage,
  onToggleDashboard,
  handsFree = false,
  ambientActive = false,
  onToggleHandsFree,
  persona = 'friday',
  greeting,
  continuity = '',
  computerReady = false,
  blackout = false,
  temperature = null,
  location = '',
  time = '',
  handPosition = null,
  voiceActivity = false,
}: ZenStageProps) {
  const visual = PERSONA_VISUALS[persona] || PERSONA_VISUALS.friday
  const displayName = greeting || visual.name
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatRef = useRef<HTMLDivElement>(null)
  const [showJumpToLatest, setShowJumpToLatest] = useState(false)
  const [hasNewMessages, setHasNewMessages] = useState(false)
  const lastContent = messages[messages.length - 1]?.content
  const [momentOpen, setMomentOpen] = useState(false)

  useEffect(() => {
    const end = messagesEndRef.current
    const container = chatRef.current
    if (!end || !container) return

    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    const awayFromLatest = distanceFromBottom > 180
    setShowJumpToLatest(awayFromLatest)
    if (!awayFromLatest) {
      setHasNewMessages(false)
      end.scrollIntoView({ behavior: messages.length > 1 ? 'smooth' : 'auto', block: 'end' })
    } else if (messages.length > 0) {
      setHasNewMessages(true)
    }
  }, [messages.length, lastContent])

  const handleChatScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const container = event.currentTarget
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    const awayFromLatest = distanceFromBottom > 180
    setShowJumpToLatest(awayFromLatest)
    if (!awayFromLatest) setHasNewMessages(false)
  }

  const jumpToLatest = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    setShowJumpToLatest(false)
    setHasNewMessages(false)
  }

  return (
    <div className="relative flex flex-col h-full min-w-0">
      {/* Minimal monochrome top strip */}
      <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-3 shrink-0 select-none overflow-x-auto scrollbar-none">
        <div className="flex items-center gap-2 min-w-0 shrink-0">
          <span className="text-[13px] font-thin tracking-[0.3em] uppercase truncate" style={{ color: '#a0a0a8' }}>
            <span style={{ color: visual.color }}>{displayName}</span>
          </span>
          {ambientActive && (
            <span className="text-[9px] font-mono tracking-widest px-1.5 py-0.5 rounded animate-fade-in shrink-0" style={{ color: '#fff', background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)' }} aria-label="Ambient mode active">
              AMBIENT
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {blackout && <span className="text-[9px] font-mono tracking-widest px-1.5 py-0.5 rounded" style={{ color: '#4ade80', border: '1px solid rgba(74,222,128,0.3)', background: 'rgba(74,222,128,0.06)' }} title="Blackout mode — local-only, no outbound network">PRIVATE</span>}
          {computerReady && <span className="text-[9px] font-mono tracking-widest px-1.5 py-0.5 rounded" style={{ color: '#a0a0a8', border: '1px solid rgba(255,255,255,0.08)' }} title="Desktop control available — ask Friday to open apps, type, or click">CONTROL</span>}
          <button type="button" onClick={() => setMomentOpen(true)} className="flex items-center gap-1.5 text-[10px] font-mono tracking-widest px-2.5 py-1 rounded-md transition-all duration-200 hover:bg-white/[.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60" style={{ color: '#606068', border: '1px solid rgba(255,255,255,0.08)' }} title="Capture a Friday moment" aria-label="Capture a Friday moment">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><circle cx="12" cy="13" r="3" /></svg>
            MOMENT
          </button>
          {onToggleHandsFree && voiceInputSupported && (
            <button type="button" onClick={onToggleHandsFree} className="flex items-center gap-1.5 text-[10px] font-mono tracking-widest px-2.5 py-1 rounded-md transition-all duration-200 hover:bg-white/[.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60" style={{ color: handsFree ? '#000' : '#606068', background: handsFree ? 'rgba(255,255,255,0.95)' : 'transparent', border: `1px solid ${handsFree ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.08)'}`, boxShadow: handsFree ? '0 0 12px rgba(255,255,255,0.25)' : 'none' }} title={handsFree ? 'Hands-free listening on — click to disable' : 'Hands-free listening off — click to enable (auto-speaks replies)'} aria-label={handsFree ? 'Disable hands-free listening' : 'Enable hands-free listening'} aria-pressed={handsFree}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /></svg>
              {handsFree ? 'HANDS-FREE' : 'LISTEN'}
            </button>
          )}
          <button type="button" onClick={onToggleDashboard} className="text-[10px] font-mono tracking-widest px-2 py-1 rounded-md transition-all duration-200 hover:bg-white/[.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 shrink-0" style={{ color: '#606068' }} title="Toggle dashboard (Ctrl/Cmd+B)" aria-label="Toggle dashboard">{location ? `${location} · ` : ''}⌘B</button>
        </div>
      </div>

      {/* Orb — always full-size, owns the stage */}
      <div className="relative flex-1 flex items-center justify-end px-4 sm:px-8 min-h-0">
        <OrbCore orbState={orbState} temperature={temperature} location={location} time={time} memory={metrics.memory} model={metrics.model} latency={metrics.latency} handPosition={handPosition} voiceActivity={voiceActivity} persona={persona} />
        {autopilotRun && <div className="absolute inset-0 flex items-center justify-center"><BrainView run={autopilotRun} size={320} /></div>}
      </div>

      {/* Chat below the orb */}
      {messages.length === 0 && continuity && (
        <div className="w-full px-4 sm:px-8 pb-2 flex justify-center"><div className="max-w-2xl text-[11px] leading-relaxed text-center px-4 py-2 rounded-xl glass animate-fade-slide-up" style={{ color: '#a0a0a8', border: '1px solid rgba(255,255,255,0.06)', borderLeft: '1px solid rgba(255,255,255,0.15)' }}>{continuity}</div></div>
      )}
      {messages.length > 0 && (
        <div ref={chatRef} className="relative w-full flex-1 min-h-0 overflow-y-auto overscroll-contain space-y-6 px-4 sm:px-8 pb-4" onScroll={handleChatScroll}>
          {messages.map((m, idx) => <MessageBubble key={m.id} message={m} index={idx} onRegenerate={m.role === 'assistant' && !m.streaming ? onRegenerate : undefined} onStop={m.role === 'assistant' && m.streaming ? onStop : undefined} />)}
          <div ref={messagesEndRef} />
          {showJumpToLatest && (
            <button type="button" onClick={jumpToLatest} className="sticky bottom-3 left-1/2 -translate-x-1/2 z-10 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[10px] font-medium tracking-wide backdrop-blur-md transition-all hover:bg-white/[.12] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70" style={{ color: '#e5e5e5', background: 'rgba(18,18,18,0.88)', border: '1px solid rgba(255,255,255,0.14)', boxShadow: '0 6px 24px rgba(0,0,0,0.3)' }} aria-label="Jump to latest message" title="Jump to latest message">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 5v14" /><path d="m19 12-7 7-7-7" /></svg>
              {hasNewMessages ? 'New messages' : 'Latest'}
            </button>
          )}
        </div>
      )}

      <ZenInput onSend={onSend} loading={loading} onVoiceStart={onVoiceStart} onVoiceStop={onVoiceStop} voiceStatus={voiceStatus} voiceInterim={voiceInterim} isVoiceSupported={voiceInputSupported} voiceLanguage={voiceLanguage} onCycleLanguage={onCycleLanguage} personaName={displayName} />

      <ShareMoment open={momentOpen} onClose={() => setMomentOpen(false)} orbState={orbState} persona={persona} message={lastContent || ''} time={time} greeting={displayName} />
    </div>
  )
})