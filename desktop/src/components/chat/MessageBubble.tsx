import { memo, useState, useCallback } from 'react'
import { TypingIndicator } from './TypingIndicator'
import { MarkdownBlock } from './MarkdownBlock'
import type { Message } from '../../types'

interface MessageBubbleProps {
  message: Message
  index: number
  onRegenerate?: () => void
  onStop?: () => void
}

function ToolCallCard({ name, args, result }: { name: string; args: string; result: string }) {
  const [open, setOpen] = useState(false)
  const isErr = result.startsWith('{"error"')
  return (
    <div className="mt-2 rounded-xl text-xs font-mono overflow-hidden glass">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-[rgba(255,255,255,0.03)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--blue)]"
        style={{ color: '#a0a0a8' }}
        aria-expanded={open}
        aria-label={`${open ? 'Collapse' : 'Expand'} tool call ${name}`}
      >
        <span aria-hidden="true" style={{ color: open ? 'var(--gold)' : '#606068' }}>{open ? '\u25BC' : '\u25B6'}</span>
        <span aria-hidden="true" style={{ color: isErr ? '#ef4444' : '#22c55e' }}>{isErr ? '\u2716' : '\u2713'}</span>
        <span className="font-medium truncate min-w-0" style={{ color: '#e5e5e5' }}>{name}</span>
        <span className="ml-auto truncate max-w-[35%] sm:max-w-[200px] opacity-50 min-w-0" style={{ color: '#606068' }}>{args}</span>
      </button>
      {open && (
        <div className="px-3 pb-2 space-y-1 max-h-[400px] overflow-y-auto">
          <div style={{ color: '#606068' }}>args:</div>
          <div className="max-h-[100px] overflow-y-auto" style={{ color: '#ccc', overflowWrap: 'anywhere' }}>{args}</div>
          <div style={{ color: '#606068' }} className="mt-1">result:</div>
          <div
            className="max-h-[180px] overflow-y-auto"
            style={{ color: isErr ? '#ef4444' : '#a0a0a8', overflowWrap: 'anywhere' }}
          >
            {result}
          </div>
        </div>
      )}
    </div>
  )
}

function PlanDisplay({ tasks }: { tasks: string }) {
  return (
    <div className="mt-2 mb-3 rounded-xl px-3 sm:px-4 py-3 text-xs glass blue-border">
      <div className="mb-2 text-xs font-medium tracking-wider blue-text">PLAN</div>
      <div className="whitespace-pre-wrap font-light leading-relaxed" style={{ color: '#a0a0a8', overflowWrap: 'anywhere' }}>
        {tasks}
      </div>
    </div>
  )
}

function useCopyButton(content: string) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(async () => {
    let success = false
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content)
        success = true
      }
    } catch {
      // Fall back below for browsers or contexts without clipboard permission.
    }

    if (!success) {
      try {
        const ta = document.createElement('textarea')
        ta.value = content
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        ta.setAttribute('readonly', '')
        document.body.appendChild(ta)
        ta.select()
        success = document.execCommand('copy')
        document.body.removeChild(ta)
      } catch {
        success = false
      }
    }

    if (success) {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    }
  }, [content])
  return { copied, handleCopy }
}

export const MessageBubble = memo(function MessageBubble({ message: m, index: idx, onRegenerate, onStop }: MessageBubbleProps) {
  const { copied, handleCopy } = useCopyButton(m.content || '')
  const isAssistant = m.role === 'assistant'

  return (
    <div
      className={`flex min-w-0 animate-fade-slide-in group relative ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
      style={{ animationDelay: `${idx * 0.05}s`, animationFillMode: 'both' }}
    >
      <div
        className="absolute -top-2 right-0 flex items-center gap-1.5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-all duration-200 -translate-y-1 group-hover:translate-y-0 group-focus-within:translate-y-0"
        style={{ zIndex: 10 }}
      >
        {!m.streaming && m.content && (
          <>
            <button
              type="button"
              onClick={handleCopy}
              className="h-7 w-7 rounded-lg flex items-center justify-center text-[11px] transition-all hover:scale-105 active:scale-95 glass glass-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--blue)]"
              style={{ color: copied ? '#22c55e' : '#a0a0a8' }}
              title="Copy message"
              aria-label={copied ? 'Message copied' : 'Copy message'}
            >
              {copied ? '\u2713' : '\u2398'}
            </button>
            {isAssistant && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="h-7 w-7 rounded-lg flex items-center justify-center text-xs transition-all hover:scale-105 active:scale-95 glass glass-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--blue)]"
                style={{ color: '#a0a0a8' }}
                title="Regenerate response"
                aria-label="Regenerate response"
              >
                {'\u21BB'}
              </button>
            )}
          </>
        )}
        {isAssistant && m.streaming && onStop && (
          <button
            type="button"
            onClick={onStop}
            className="h-7 w-7 rounded-lg flex items-center justify-center text-xs transition-all hover:scale-105 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
            style={{ background: 'rgba(239,68,68,0.12)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.15)' }}
            title="Stop generation"
            aria-label="Stop generation"
          >
            {'\u25A0'}
          </button>
        )}
      </div>

      {isAssistant && (
        <div className="w-0.5 shrink-0 mr-3 sm:mr-4 rounded-full relative overflow-hidden" aria-hidden="true">
          <div className="absolute inset-0 rounded-full animate-gradient" style={{ opacity: 0.3 }} />
          <div className="w-full h-full rounded-full" style={{ background: 'rgba(0,168,255,0.15)' }} />
        </div>
      )}
      <div
        className={`${m.role === 'user' ? 'max-w-[90%] sm:max-w-[65%] px-3 sm:px-4 py-2.5 sm:py-3 rounded-2xl' : 'w-full min-w-0 text-sm leading-relaxed'} ${isAssistant ? 'max-h-[65vh] overflow-y-auto' : ''}`}
        style={{
          background: m.role === 'user' ? 'rgba(245,158,11,0.06)' : 'transparent',
          color: m.role === 'user' ? '#e5e5e5' : '#ccc',
          border: m.role === 'user' ? '1px solid rgba(245,158,11,0.1)' : 'none',
          borderLeft: m.role === 'user' ? '2px solid rgba(245,158,11,0.2)' : 'none',
          backdropFilter: m.role === 'user' ? 'blur(12px)' : 'none',
          overflowWrap: 'anywhere',
        }}
      >
        {m.reflex && (
          <div className="mb-2 inline-flex max-w-full items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-mono tracking-wider uppercase glass" style={{ border: '1px solid rgba(16,185,129,0.2)', color: '#34d399' }}>
            <span aria-hidden="true">{'\u26A1'}</span>
            <span className="truncate">{m.reflex}</span>
            <span className="shrink-0" style={{ color: '#6ee7b7', opacity: 0.6, fontSize: '9px' }}>system-1</span>
          </div>
        )}
        {m.plan && <PlanDisplay tasks={m.plan} />}
        <div>
          {isAssistant && m.content ? <MarkdownBlock content={m.content} /> : <div className="whitespace-pre-wrap text-sm font-light leading-relaxed tracking-wide">{m.content}</div>}
        </div>
        {m.streaming && !m.content && <TypingIndicator />}
        {m.streaming && m.content && <span className="inline-block w-[1ch] animate-pulse" style={{ color: 'var(--gold)' }} aria-hidden="true">{'\u258A'}</span>}
        {m.toolCalls && m.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1">
            {m.toolCalls.map((tc, i) => <ToolCallCard key={i} name={tc.name} args={tc.args} result={tc.result} />)}
          </div>
        )}
      </div>
    </div>
  )
})
