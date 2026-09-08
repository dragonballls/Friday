import { useCallback, useState } from 'react'

type FileEntry = { name: string; kind: 'file' | 'directory'; path: string }

type DirectoryPickerWindow = Window & typeof globalThis & {
  showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>
}

function WorkspaceBrowser({ onClose }: { onClose: () => void }) {
  const [rootName, setRootName] = useState('No workspace selected')
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const chooseWorkspace = useCallback(async () => {
    const picker = (window as DirectoryPickerWindow).showDirectoryPicker
    if (!picker) {
      setError('This browser does not support local workspace access.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const root = await picker()
      const next: FileEntry[] = []
      for await (const [name, handle] of root.entries()) {
        next.push({ name, kind: handle.kind, path: name })
      }
      next.sort((a, b) => a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind === 'directory' ? -1 : 1)
      setRootName(root.name)
      setEntries(next)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Unable to open workspace.')
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-6" role="dialog" aria-modal="true" aria-label="Workspace browser">
      <div className="glass w-full max-w-3xl max-h-[80vh] rounded-2xl border border-white/[.08] shadow-2xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[.06]">
          <div>
            <div className="text-sm font-medium text-white">Workspace</div>
            <div className="text-[11px] text-white/40 mt-0.5">{rootName}</div>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={chooseWorkspace} disabled={loading} className="px-3 py-1.5 rounded-lg text-xs text-[#D4A040] bg-[#D4A040]/10 hover:bg-[#D4A040]/15 disabled:opacity-50">
              {loading ? 'Opening…' : 'Open folder'}
            </button>
            <button type="button" onClick={onClose} aria-label="Close workspace" className="w-7 h-7 rounded-lg text-white/50 hover:text-white hover:bg-white/[.06]">×</button>
          </div>
        </div>

        {error && <div className="mx-4 mt-4 rounded-lg px-3 py-2 text-xs text-red-300 bg-red-500/10 border border-red-500/20">{error}</div>}

        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          {entries.length === 0 && !error ? (
            <div className="h-48 flex flex-col items-center justify-center text-center text-white/40">
              <div className="text-sm">Choose a workspace folder</div>
              <div className="text-[11px] mt-1">Friday only reads the directory you explicitly select in the browser.</div>
            </div>
          ) : (
            <div className="space-y-1">
              {entries.map(entry => (
                <div key={entry.path} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-white/[.04]">
                  <span className="w-5 text-center text-xs text-[#D4A040]">{entry.kind === 'directory' ? '▸' : '•'}</span>
                  <span className="text-xs text-white/75 truncate">{entry.name}</span>
                  <span className="ml-auto text-[10px] text-white/25">{entry.kind}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export { WorkspaceBrowser }
