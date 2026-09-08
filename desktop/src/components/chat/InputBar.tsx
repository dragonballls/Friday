import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent, KeyboardEvent } from 'react'

interface InputBarProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  loading?: boolean
  voiceStatus?: 'idle' | 'listening' | 'processing'
}

export default function InputBar({ value, onChange, onSend, loading = false, voiceStatus = 'idle' }: InputBarProps) {
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler as unknown as EventListener)
    return () => window.removeEventListener('keydown', handler as unknown as EventListener)
  }, [])

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !loading) onSend()
    }
  }, [value, loading, onSend])

  const clear = useCallback(() => {
    onChange('')
    inputRef.current?.focus()
  }, [onChange])

  const handleFilePick = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const text = reader.result as string
      const header = `[File: ${file.name}]\n~~~\n${text}\n~~~\n\n`
      onChange(value + header)
      if (inputRef.current) {
        inputRef.current.focus()
        inputRef.current.selectionStart = inputRef.current.selectionEnd = inputRef.current.value.length
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }, [onChange, value])

  const isListening = voiceStatus === 'listening'
  const borderColor = isListening ? 'rgba(245,158,11,0.4)' : focused ? 'rgba(245,158,11,0.2)' : 'var(--glass-border)'

  return (
    <div style={{ position: 'relative', border: `1px solid ${borderColor}`, borderRadius: 14, background: 'var(--glass-bg)', transition: 'border-color 150ms ease' }}>
      <textarea
        ref={inputRef}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        disabled={loading}
        rows={1}
        placeholder={loading ? 'Thinking…' : 'Message Friday…'}
        style={{ width: '100%', minHeight: 52, maxHeight: 180, resize: 'vertical', border: 0, outline: 0, background: 'transparent', color: 'var(--text-primary)', padding: '15px 92px 15px 16px', boxSizing: 'border-box', font: 'inherit' }}
      />
      {value && !loading && (
        <button type="button" onClick={clear} aria-label="Clear message" title="Clear message" style={{ position: 'absolute', right: 52, bottom: 10, border: 0, background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', padding: 8 }}>×</button>
      )}
      <label style={{ position: 'absolute', right: 48, bottom: 10, padding: 8, cursor: 'pointer', color: 'var(--text-secondary)' }} title="Attach file" aria-label="Attach file">
        <input type="file" hidden onChange={handleFilePick} />
        📎
      </label>
      <button type="button" onClick={onSend} disabled={!value.trim() || loading} aria-label="Send message" title="Send message" style={{ position: 'absolute', right: 10, bottom: 10, border: 0, borderRadius: 8, padding: '8px 11px', background: 'var(--accent)', color: 'var(--accent-contrast)', cursor: value.trim() && !loading ? 'pointer' : 'not-allowed', opacity: value.trim() && !loading ? 1 : 0.5 }}>↑</button>
    </div>
  )
}
