import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

interface Command {
  id: string
  label: string
  action: () => void
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  commands: Command[]
}

export function CommandPalette({ open, onClose, commands }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const listId = 'friday-command-list'

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return needle ? commands.filter(c => c.label.toLowerCase().includes(needle)) : commands
  }, [commands, query])

  const restoreFocus = useCallback(() => {
    const previous = previousFocusRef.current
    previousFocusRef.current = null
    if (previous && document.contains(previous)) {
      window.setTimeout(() => previous.focus(), 0)
    }
  }, [])

  const close = useCallback(() => {
    onClose()
    restoreFocus()
  }, [onClose, restoreFocus])

  const execute = useCallback((idx: number) => {
    const cmd = filtered[idx]
    if (cmd) {
      cmd.action()
      onClose()
      restoreFocus()
    }
  }, [filtered, onClose, restoreFocus])

  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setQuery('')
    setSelected(0)
    const timer = window.setTimeout(() => inputRef.current?.focus(), 50)
    return () => window.clearTimeout(timer)
  }, [open])

  useEffect(() => {
    setSelected(i => Math.max(0, Math.min(i, Math.max(filtered.length - 1, 0))))
  }, [filtered.length])

  useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); close(); return }
      if (e.key === 'Tab') {
        const dialog = document.getElementById('friday-command-dialog')
        if (!dialog) return
        const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled])'))
        if (!focusable.length) return
        const current = document.activeElement as HTMLElement | null
        const index = current ? focusable.indexOf(current) : -1

        if (index === -1) {
          e.preventDefault()
          focusable[e.shiftKey ? focusable.length - 1 : 0].focus()
          return
        }

        if (e.shiftKey && index === 0) {
          e.preventDefault()
          focusable[focusable.length - 1].focus()
        } else if (!e.shiftKey && index === focusable.length - 1) {
          e.preventDefault()
          focusable[0].focus()
        }
        return
      }
      if (e.key === 'ArrowDown') { e.preventDefault(); if (filtered.length) setSelected(i => Math.min(i + 1, filtered.length - 1)); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); if (filtered.length) setSelected(i => Math.max(i - 1, 0)); return }
      if (e.key === 'Enter') { e.preventDefault(); execute(selected); return }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, filtered.length, selected, execute, close])

  useEffect(() => {
    const active = document.getElementById(`friday-command-${filtered[selected]?.id}`)
    active?.scrollIntoView({ block: 'nearest' })
  }, [selected, filtered])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] sm:pt-[15vh] px-3"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      role="presentation"
      onClick={close}
    >
      <div
        id="friday-command-dialog"
        className="w-full max-w-lg max-h-[80vh] rounded-2xl overflow-hidden shadow-2xl"
        style={{
          background: 'rgba(14,14,14,0.95)',
          border: '1px solid rgba(255,255,255,0.08)',
          backdropFilter: 'blur(32px)',
          WebkitBackdropFilter: 'blur(32px)',
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <label className="sr-only" htmlFor="friday-command-input">Search commands</label>
          <input
            ref={inputRef}
            id="friday-command-input"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Type a command..."
            className="w-full bg-transparent outline-none text-sm focus-visible:ring-1 focus-visible:ring-[#D4A040]/50 rounded px-1"
            style={{ color: '#e5e5e5' }}
            role="combobox"
            aria-controls={listId}
            aria-expanded="true"
            aria-autocomplete="list"
            aria-activedescendant={filtered[selected] ? `friday-command-${filtered[selected].id}` : undefined}
          />
        </div>
        <div id={listId} className="max-h-64 overflow-y-auto overscroll-contain py-1" role="listbox" aria-label="Commands">
          {filtered.length === 0 ? (
            <div className="px-4 py-4 text-xs text-center" style={{ color: '#666' }}>No matching commands</div>
          ) : (
            filtered.map((cmd, i) => (
              <button
                key={cmd.id}
                id={`friday-command-${cmd.id}`}
                type="button"
                role="option"
                aria-selected={i === selected}
                onClick={() => execute(i)}
                className="w-full text-left px-4 py-2.5 text-sm transition-colors duration-75 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[#D4A040]/60"
                style={{
                  background: i === selected ? 'rgba(245,158,11,0.12)' : 'transparent',
                  color: i === selected ? '#f59e0b' : '#bbb',
                }}
                onMouseEnter={() => setSelected(i)}
              >
                {cmd.label}
              </button>
            ))
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-[11px]" style={{ color: '#555', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <span><kbd className="font-mono" style={{ color: '#777' }}>↑↓</kbd> navigate</span>
          <span><kbd className="font-mono" style={{ color: '#777' }}>↵</kbd> select</span>
          <span><kbd className="font-mono" style={{ color: '#777' }}>esc</kbd> close</span>
          <span><kbd className="font-mono" style={{ color: '#777' }}>tab</kbd> move focus</span>
        </div>
      </div>
    </div>
  )
}
