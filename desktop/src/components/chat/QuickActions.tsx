import { memo } from 'react'

interface QuickActionsProps {
  onAction: (prompt: string) => void
  disabled: boolean
}

const ACTIONS = [
  { label: 'Search Web', prompt: 'Search the web for' },
  { label: 'Analyze', prompt: 'Analyze the following' },
  { label: 'Execute', prompt: 'Execute a plan to' },
]

export const QuickActions = memo(function QuickActions({ onAction, disabled }: QuickActionsProps) {
  return (
    <div className="flex items-center gap-2 px-4 sm:px-5 pb-3 pt-1 overflow-x-auto overscroll-contain scrollbar-none">
      {ACTIONS.map(a => (
        <button
          key={a.label}
          type="button"
          onClick={() => onAction(a.prompt)}
          disabled={disabled}
          aria-label={`${a.label} quick action`}
          title={a.label}
          className="text-xs px-3 py-1 rounded-full transition-all duration-150 active:scale-95 disabled:opacity-30 shrink-0 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]"
          style={{
            color: '#888',
            border: '1px solid rgba(255,255,255,0.08)',
            background: 'rgba(255,255,255,0.03)',
          }}
          onMouseEnter={e => {
            if (disabled) return
            e.currentTarget.style.background = 'rgba(245,158,11,0.1)'
            e.currentTarget.style.borderColor = 'rgba(245,158,11,0.25)'
            e.currentTarget.style.color = '#f59e0b'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
            e.currentTarget.style.color = '#888'
          }}
        >
          {a.label}
        </button>
      ))}
    </div>
  )
})
