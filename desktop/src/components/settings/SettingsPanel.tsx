import { useEffect, useRef, useState } from 'react'
import type { MarketplacePlugin, CustomTool } from '../../core/api'
import { getPlugins, installPlugin, uninstallPlugin, getCustomTools, createCustomTool, deleteCustomTool, getPrivacyStatus, setPrivacy } from '../../core/api'

interface SettingsPanelProps {
  onClose: () => void
  voiceOutputEnabled: boolean
  onToggleVoiceOutput: () => void
  voiceLanguage: string
  onCycleLanguage: () => void
  wakeWordActive: boolean
  onToggleWakeWord: () => void
  camActive: boolean
  onToggleCamera: () => void
  backendOnline: boolean
  calendarAuth: string
  emailAuth: string
  onGoogleConnect: () => void
  persona: string
  onSetPersona: (key: string) => void
  personaPrompt?: string
  onSetPersonaPrompt?: (prompt: string) => void
}

export function SettingsPanel({
  onClose,
  voiceOutputEnabled,
  onToggleVoiceOutput,
  voiceLanguage,
  onCycleLanguage,
  wakeWordActive,
  onToggleWakeWord,
  camActive,
  onToggleCamera,
  backendOnline,
  calendarAuth,
  emailAuth,
  onGoogleConnect,
  persona,
  onSetPersona,
  personaPrompt = '',
  onSetPersonaPrompt = () => {},
}: SettingsPanelProps) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const [plugins, setPlugins] = useState<MarketplacePlugin[] | null>(null)
  const [pluginMsg, setPluginMsg] = useState('')
  const [customTools, setCustomTools] = useState<CustomTool[] | null>(null)
  const [toolDesc, setToolDesc] = useState('')
  const [toolMsg, setToolMsg] = useState('')
  const [toolBusy, setToolBusy] = useState(false)
  const [blackout, setBlackout] = useState(false)

  useEffect(() => {
    getPlugins().then(setPlugins).catch(() => setPlugins([]))
    getCustomTools().then(setCustomTools).catch(() => setCustomTools([]))
    getPrivacyStatus().then(s => setBlackout(s.enabled)).catch(() => {})
  }, [])

  const handleInstall = async (name: string) => {
    const res = await installPlugin(name)
    setPluginMsg(res.error || res.message || '')
    setPlugins(await getPlugins().catch(() => []))
  }

  const handleUninstall = async (name: string) => {
    const res = await uninstallPlugin(name)
    setPluginMsg(res.error || res.message || '')
    setPlugins(await getPlugins().catch(() => []))
  }

  const handleCreateTool = async () => {
    if (!toolDesc.trim()) return
    setToolBusy(true)
    setToolMsg('')
    try {
      const res = await createCustomTool(toolDesc)
      if (res.error) setToolMsg(`Error: ${res.error}`)
      else {
        setToolMsg(`Built tool "${res.tool?.name}"`)
        setToolDesc('')
      }
      setCustomTools(await getCustomTools().catch(() => []))
    } catch (error) {
      setToolMsg(`Error: ${error instanceof Error ? error.message : 'Unable to build tool'}`)
    } finally {
      setToolBusy(false)
    }
  }

  const handleDeleteTool = async (name: string) => {
    await deleteCustomTool(name)
    setCustomTools(await getCustomTools().catch(() => []))
  }

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    const frame = window.requestAnimationFrame(() => closeRef.current?.focus())
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('keydown', handleKey)
    }
  }, [onClose])

  const toggleRow = (label: string, enabled: boolean, onToggle: () => void) => (
    <div className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <span className="min-w-0 text-sm" style={{ color: '#ccc' }}>{label}</span>
      <button
        type="button"
        onClick={onToggle}
        aria-label={`${label}: ${enabled ? 'On' : 'Off'}`}
        aria-pressed={enabled}
        className="relative w-10 h-5 shrink-0 rounded-full transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
        style={{
          background: enabled ? 'rgba(0,168,255,0.3)' : 'rgba(255,255,255,0.08)',
          border: enabled ? '1px solid rgba(0,168,255,0.4)' : '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <span
          aria-hidden="true"
          className="absolute top-0.5 w-3.5 h-3.5 rounded-full transition-all"
          style={{
            left: enabled ? '22px' : '3px',
            background: enabled ? '#00a8ff' : '#666',
          }}
        />
      </button>
    </div>
  )

  const statusBadge = (_label: string, ok: boolean) => (
    <span
      className="inline-block shrink-0 px-2 py-0.5 rounded text-[11px]"
      style={{
        background: ok ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
        color: ok ? '#4ade80' : '#f87171',
      }}
    >
      {ok ? 'Connected' : 'Disconnected'}
    </span>
  )

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className="w-[min(420px,calc(100vw-2rem))] max-h-[min(80vh,760px)] overflow-y-auto overscroll-contain rounded-2xl glass"
        style={{
          border: '1px solid var(--glass-border)',
          boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
        }}
      >
        <div className="flex items-center justify-between gap-4 px-4 sm:px-6 h-12 shrink-0" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <span className="text-sm font-medium tracking-wide" style={{ color: '#e5e5e5' }}>Settings</span>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            title="Close settings (Esc)"
            className="w-7 h-7 shrink-0 flex items-center justify-center rounded-lg text-sm transition-all hover:bg-white/[.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
            style={{ color: '#888' }}
          >
            ×
          </button>
        </div>

        <div className="px-4 sm:px-6 py-4 space-y-1">
          <div className="text-[10px] tracking-[0.15em] py-2" style={{ color: '#555' }}>VOICE</div>
          {toggleRow('Voice Output', voiceOutputEnabled, onToggleVoiceOutput)}
          <div className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="min-w-0 text-sm" style={{ color: '#ccc' }}>Language</span>
            <button
              type="button"
              onClick={onCycleLanguage}
              aria-label={`Voice language: ${voiceLanguage}. Change language`}
              className="px-3 py-1 shrink-0 rounded-lg text-xs transition-all hover:bg-white/[.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
              style={{ color: '#00a8ff', border: '1px solid rgba(0,168,255,0.2)' }}
            >
              {voiceLanguage}
            </button>
          </div>
          {toggleRow('Wake Word ("Hey Friday")', wakeWordActive, onToggleWakeWord)}
          <div className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="min-w-0 text-sm" style={{ color: '#ccc' }}>Voice Personality</span>
            <div className="flex max-w-[65%] gap-1 overflow-x-auto overscroll-contain py-0.5">
              {['friday', 'jarvis', 'cortana', 'adonis'].map(k => (
                <button
                  key={k}
                  type="button"
                  onClick={() => onSetPersona(k)}
                  aria-pressed={persona === k}
                  aria-label={`Use ${k} voice personality`}
                  className="px-2.5 py-1 shrink-0 rounded-lg text-[11px] uppercase tracking-wider transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
                  style={{
                    background: persona === k ? 'rgba(0,168,255,0.15)' : 'rgba(255,255,255,0.04)',
                    border: persona === k ? '1px solid rgba(0,168,255,0.3)' : '1px solid rgba(255,255,255,0.06)',
                    color: persona === k ? '#00a8ff' : '#888',
                  }}
                >
                  {k}
                </button>
              ))}
            </div>
          </div>

          <div className="py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <label className="text-sm block mb-2" style={{ color: '#ccc' }}>Character prompt</label>
            <textarea
              value={personaPrompt}
              onChange={event => onSetPersonaPrompt(event.target.value)}
              placeholder="Add traits, tone, boundaries, and preferences for this persona..."
              rows={5}
              aria-label="Character prompt"
              className="w-full rounded-lg p-2 text-xs resize-y outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              style={{ color: '#ddd', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
            />
            <div className="mt-1 text-[10px]" style={{ color: '#666' }}>Saved locally for the selected persona and applied to new messages.</div>
          </div>

          <div className="text-[10px] tracking-[0.15em] py-2" style={{ color: '#555' }}>INPUT</div>
          {toggleRow('Gesture Control (Camera)', camActive, onToggleCamera)}

          <div className="text-[10px] tracking-[0.15em] py-2" style={{ color: '#555' }}>CONNECTIONS</div>
          <div className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="text-sm" style={{ color: '#ccc' }}>Backend</span>
            {statusBadge('backend', backendOnline)}
          </div>
          <div className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="text-sm" style={{ color: '#ccc' }}>Google Calendar</span>
            {calendarAuth === 'authenticated' ? statusBadge('calendar', true) : (
              <button
                type="button"
                onClick={onGoogleConnect}
                className="px-3 py-1 shrink-0 rounded-lg text-xs transition-all hover:bg-white/[.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
                style={{ color: '#00a8ff', border: '1px solid rgba(0,168,255,0.2)' }}
              >
                Connect
              </button>
            )}
          </div>
          <div className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="text-sm" style={{ color: '#ccc' }}>Google Email</span>
            {emailAuth === 'authenticated' ? statusBadge('email', true) : (
              <button
                type="button"
                onClick={onGoogleConnect}
                className="px-3 py-1 shrink-0 rounded-lg text-xs transition-all hover:bg-white/[.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
                style={{ color: '#00a8ff', border: '1px solid rgba(0,168,255,0.2)' }}
              >
                Connect
              </button>
            )}
          </div>

          <div className="text-[10px] tracking-[0.15em] py-2" style={{ color: '#555' }}>PLUGINS</div>
          {pluginMsg && <div className="text-[11px] py-1 break-words" role="status" style={{ color: '#00a8ff' }}>{pluginMsg}</div>}
          {plugins === null && <div className="text-xs py-3" role="status" style={{ color: '#666' }}>Loading…</div>}
          {(plugins ?? []).map(p => (
            <div key={p.name} className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <div className="min-w-0">
                <span className="text-sm" style={{ color: '#ccc' }}>{p.name}</span>
                {p.builtin && <span className="ml-2 text-[10px] uppercase tracking-wider" style={{ color: '#555' }}>builtin</span>}
                {p.description && <div className="text-[11px] truncate" style={{ color: '#666' }}>{p.description}</div>}
              </div>
              {p.builtin ? (
                <span className="shrink-0 text-[10px] uppercase tracking-wider" style={{ color: '#4ade80' }}>active</span>
              ) : p.installed ? (
                <button
                  type="button"
                  onClick={() => handleUninstall(p.name)}
                  aria-label={`Remove plugin ${p.name}`}
                  className="px-3 py-1 shrink-0 rounded-lg text-xs transition-all hover:bg-white/[.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/70"
                  style={{ color: '#f87171', border: '1px solid rgba(248,113,113,0.2)' }}
                >
                  Remove
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleInstall(p.name)}
                  aria-label={`Install plugin ${p.name}`}
                  className="px-3 py-1 shrink-0 rounded-lg text-xs transition-all hover:bg-white/[.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
                  style={{ color: '#00a8ff', border: '1px solid rgba(0,168,255,0.2)' }}
                >
                  Install
                </button>
              )}
            </div>
          ))}

          <div className="text-[10px] tracking-[0.15em] py-2" style={{ color: '#555' }}>PRIVACY</div>
          {toggleRow('Blackout Mode (local-only, no outbound)', blackout, () => {
            setPrivacy(!blackout).then(s => setBlackout(s.enabled)).catch(() => {})
          })}
          {blackout && <div className="text-[11px] py-2 break-words" style={{ color: '#4ade80' }}>Local-only — network tools blocked, Ollama provider.</div>}

          <div className="text-[10px] tracking-[0.15em] py-2" style={{ color: '#555' }}>CUSTOM TOOLS</div>
          <div className="py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <textarea
              value={toolDesc}
              onChange={e => setToolDesc(e.target.value)}
              placeholder="Describe a tool, e.g. 'a tool that downloads the latest image from a URL and saves it'"
              rows={3}
              aria-label="Custom tool description"
              className="w-full rounded-lg px-3 py-2 text-xs resize-none outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              style={{ background: 'rgba(255,255,255,0.04)', color: '#ccc', border: '1px solid rgba(255,255,255,0.08)' }}
            />
            <button
              type="button"
              onClick={handleCreateTool}
              disabled={toolBusy || !toolDesc.trim()}
              aria-label={toolBusy ? 'Building custom tool' : 'Build custom tool'}
              className="mt-2 px-3 py-1.5 rounded-lg text-xs transition-all disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70"
              style={{ color: '#00a8ff', border: '1px solid rgba(0,168,255,0.2)' }}
            >
              {toolBusy ? 'Building…' : 'Build tool'}
            </button>
            {toolMsg && <div className="mt-2 text-[11px] break-words" role="status" aria-live="polite" style={{ color: toolMsg.startsWith('Error') ? '#f87171' : '#4ade80' }}>{toolMsg}</div>}
          </div>
          {customTools !== null && customTools.length === 0 && (
            <div className="text-[11px] py-2" style={{ color: '#666' }}>No custom tools yet.</div>
          )}
          {(customTools ?? []).map(t => (
            <div key={t.name} className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <div className="min-w-0">
                <span className="text-sm" style={{ color: '#ccc' }}>{t.name}</span>
                <div className="text-[11px] truncate" style={{ color: '#666' }}>{t.description}</div>
              </div>
              <button
                type="button"
                onClick={() => handleDeleteTool(t.name)}
                aria-label={`Delete custom tool ${t.name}`}
                className="px-3 py-1 shrink-0 rounded-lg text-xs transition-all hover:bg-white/[.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/70"
                style={{ color: '#f87171', border: '1px solid rgba(248,113,113,0.2)' }}
              >
                Delete
              </button>
            </div>
          ))}

          <div className="text-[10px] tracking-[0.15em] py-2" style={{ color: '#555' }}>ABOUT</div>
          <div className="flex items-center justify-between gap-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="text-sm" style={{ color: '#ccc' }}>Theme</span>
            <span className="text-xs" style={{ color: '#888' }}>Dark</span>
          </div>
          <div className="flex items-center justify-between py-3">
            <span className="text-sm" style={{ color: '#ccc' }}>Version</span>
            <span className="text-xs" style={{ color: '#666' }}>0.4</span>
          </div>
        </div>
      </div>
    </div>
  )
}
