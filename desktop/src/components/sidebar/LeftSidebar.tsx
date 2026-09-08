import { memo, useMemo, useRef, useState } from 'react'
import type { Session } from '../../types'

interface LeftSidebarProps {
  sessions: Session[]
  activeId: string
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onSettings: () => void
  outputDir: string
  onSetOutputDir: (path: string) => void
}

export const LeftSidebar = memo(function LeftSidebar({
  sessions, activeId, onSelect, onNew, onDelete, onSettings, outputDir, onSetOutputDir
}: LeftSidebarProps) {
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSave = () => {
    const val = inputRef.current?.value.trim() || ''
    onSetOutputDir(val)
    setEditing(false)
  }

  const filteredSessions = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return sessions
    return sessions.filter(session => session.title.toLowerCase().includes(needle))
  }, [query, sessions])

  const recentSessions = sessions.slice(-3).reverse()

  return (
    <aside
      className="w-60 max-w-[22vw] min-w-[180px] flex flex-col h-full shrink-0 glass"
      aria-label="Conversation sidebar"
      style={{ borderRight: '1px solid var(--glass-border)' }}
    >
      <div
        className="flex items-center justify-between px-4 h-10 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
      >
        <span className="text-[11px] font-medium tracking-[0.2em]" style={{ color: '#666' }}>
          SESSIONS
        </span>
        <button
          type="button"
          onClick={onNew}
          aria-label="Start new conversation"
          title="New conversation"
          className="w-6 h-6 flex items-center justify-center rounded-md text-sm transition-all hover:bg-white/[.04] active:scale-95"
          style={{ color: '#888' }}
        >
          +
        </button>
      </div>

      <div className="px-3 pt-2 pb-1 shrink-0">
        <label className="sr-only" htmlFor="session-search">Search conversations</label>
        <input
          id="session-search"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search conversations"
          className="w-full px-2.5 py-1.5 rounded-lg text-[11px] outline-none placeholder:text-white/20"
          style={{ background: 'rgba(255,255,255,0.03)', color: '#bbb', border: '1px solid rgba(255,255,255,0.05)' }}
        />
      </div>

      <div className="flex-1 overflow-y-auto py-1.5 px-2 space-y-0.5" aria-label="Conversations">
        {filteredSessions.length === 0 ? (
          <div className="px-3 py-6 text-center text-[11px]" style={{ color: '#555' }}>
            {query ? 'No conversations match your search.' : 'No conversations yet.'}
          </div>
        ) : filteredSessions.map(s => {
          const act = s.id === activeId
          return (
            <div
              key={s.id}
              role="button"
              tabIndex={0}
              aria-current={act ? 'page' : undefined}
              onClick={() => onSelect(s.id)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(s.id)
                }
              }}
              className="group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all duration-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
              style={{
                borderLeft: act ? '2px solid #D4A040' : '2px solid transparent',
                background: act ? 'rgba(212,160,64,0.06)' : 'transparent',
              }}
              onMouseEnter={e => { if (!act) e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
              onMouseLeave={e => { if (!act) e.currentTarget.style.background = 'transparent' }}
            >
              <span className="truncate flex-1 text-sm" style={{
                color: act ? '#D4A040' : '#9E9E9E',
                fontWeight: act ? 450 : 350,
                letterSpacing: '0.01em',
              }}>
                {s.title}
              </span>
              <button
                type="button"
                onClick={e => { e.stopPropagation(); onDelete(s.id) }}
                aria-label={`Delete conversation ${s.title}`}
                title="Delete conversation"
                className="opacity-0 group-hover:opacity-50 focus-visible:opacity-100 hover:opacity-100 transition-all duration-150 text-sm shrink-0 ml-2 w-5 h-5 flex items-center justify-center rounded hover:bg-white/[.06] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
                style={{ color: '#666' }}
              >
                ×
              </button>
            </div>
          )
        })}
      </div>

      {recentSessions.length > 1 && !query && (
        <div className="px-4 py-3 shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <div className="text-[10px] tracking-[0.15em] mb-2" style={{ color: '#666' }}>RECENT</div>
          <div className="space-y-1">
            {recentSessions.map(s => (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelect(s.id)}
                className="w-full text-left truncate text-[11px] px-2 py-1 rounded transition-all hover:bg-white/[.03] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
                style={{ color: s.id === activeId ? '#D4A040' : '#888' }}
              >
                {s.title}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="px-4 py-3 shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <div className="text-[10px] tracking-[0.15em] mb-2" style={{ color: '#666' }}>OUTPUT</div>
        {editing ? (
          <div className="flex gap-1">
            <input
              ref={inputRef}
              defaultValue={outputDir}
              className="flex-1 min-w-0 px-2 py-1 rounded text-[11px] outline-none"
              style={{ background: 'rgba(255,255,255,0.06)', color: '#ccc', border: '1px solid rgba(212,160,64,0.3)' }}
              placeholder="C:\path\to\output"
              aria-label="Output folder path"
              onKeyDown={e => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false) }}
              autoFocus
            />
            <button type="button" onClick={handleSave} className="px-2 py-1 rounded text-[11px]" style={{ background: 'rgba(212,160,64,0.15)', color: '#D4A040' }}>ok</button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="w-full text-left truncate text-[11px] px-2 py-1.5 rounded transition-all focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
            style={{ color: outputDir ? '#9E9E9E' : '#555', background: 'rgba(255,255,255,0.02)' }}
            title={outputDir || 'Click to set'}
          >
            {outputDir || '+ set output folder'}
          </button>
        )}
      </div>

      <div className="px-4 py-3 flex items-center justify-between shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <button type="button" onClick={onSettings} className="text-xs transition-all hover:text-white/80 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]" style={{ color: '#666' }}>
          settings
        </button>
        <span className="text-[11px]" style={{ color: '#444' }}>v0.4</span>
      </div>
    </aside>
  )
})
