import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

type FileEntry = {
  name: string
  kind: 'file' | 'directory'
  path: string
  handle: FileSystemFileHandle | FileSystemDirectoryHandle
}

type DirectoryPickerWindow = Window & typeof globalThis & {
  showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>
}

const IGNORED = new Set(['.git', 'node_modules', '.venv', '__pycache__', 'dist', 'build', '.next', '.cache'])
const MAX_PREVIEW_BYTES = 256_000

function WorkspaceBrowser({ onClose }: { onClose: () => void }) {
  const [rootName, setRootName] = useState(() => {
    try { return localStorage.getItem('friday_workspace_name') || 'No workspace selected' } catch { return 'No workspace selected' }
  })
  const [root, setRoot] = useState<FileSystemDirectoryHandle | null>(null)
  const [current, setCurrent] = useState<FileSystemDirectoryHandle | null>(null)
  const [currentPath, setCurrentPath] = useState<string[]>([])
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [selected, setSelected] = useState<FileEntry | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const filterRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
        event.preventDefault()
        filterRef.current?.focus()
        filterRef.current?.select()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const loadDirectory = useCallback(async (directory: FileSystemDirectoryHandle, path: string[]) => {
    setLoading(true)
    setError('')
    setSelected(null)
    setPreview(null)
    try {
      const next: FileEntry[] = []
      for await (const [name, handle] of directory.entries()) {
        if (IGNORED.has(name)) continue
        next.push({ name, kind: handle.kind, path: [...path, name].join('/'), handle })
      }
      next.sort((a, b) => a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind === 'directory' ? -1 : 1)
      setEntries(next)
      setCurrent(directory)
      setCurrentPath(path)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to read workspace directory.')
    } finally {
      setLoading(false)
    }
  }, [])

  const chooseWorkspace = useCallback(async () => {
    const picker = (window as DirectoryPickerWindow).showDirectoryPicker
    if (!picker) {
      setError('This browser does not support local workspace access.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const picked = await picker()
      setRoot(picked)
      setRootName(picked.name)
      setCurrentPath([])
      try { localStorage.setItem('friday_workspace_name', picked.name) } catch {}
      await loadDirectory(picked, [])
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Unable to open workspace.')
      setLoading(false)
    }
  }, [loadDirectory])

  const refreshCurrent = useCallback(() => {
    if (!current) return
    void loadDirectory(current, currentPath)
  }, [current, currentPath, loadDirectory])

  const openEntry = useCallback(async (entry: FileEntry) => {
    setError('')
    if (entry.kind === 'directory') {
      await loadDirectory(entry.handle as FileSystemDirectoryHandle, [...currentPath, entry.name])
      return
    }
    setSelected(entry)
    setPreviewLoading(true)
    setPreview(null)
    try {
      const file = await (entry.handle as FileSystemFileHandle).getFile()
      if (file.size > MAX_PREVIEW_BYTES) {
        setPreview(`This file is ${(file.size / 1024).toFixed(0)} KB. Preview is limited to ${Math.round(MAX_PREVIEW_BYTES / 1024)} KB.`)
        return
      }
      const text = await file.text()
      const looksBinary = text.includes('\u0000')
      setPreview(looksBinary ? 'Binary or non-text content cannot be previewed safely.' : text)
    } catch (err) {
      setPreview(null)
      setError(err instanceof Error ? err.message : 'Unable to read the selected file.')
    } finally {
      setPreviewLoading(false)
    }
  }, [currentPath, loadDirectory])

  useEffect(() => {
    if (root && !current) loadDirectory(root, [])
  }, [root, current, loadDirectory])

  const filteredEntries = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return entries
    return entries.filter(entry => entry.name.toLowerCase().includes(needle) || entry.path.toLowerCase().includes(needle))
  }, [entries, query])

  const goBack = useCallback(() => {
    if (!root || currentPath.length === 0) return
    const parentPath = currentPath.slice(0, -1)
    let directory = root
    const resolve = async () => {
      try {
        for (const segment of parentPath) directory = await directory.getDirectoryHandle(segment)
        await loadDirectory(directory, parentPath)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to open parent directory.')
      }
    }
    void resolve()
  }, [root, currentPath, loadDirectory])

  const jumpToPath = useCallback((index: number) => {
    if (!root) return
    const target = currentPath.slice(0, index)
    let directory = root
    const resolve = async () => {
      try {
        for (const segment of target) directory = await directory.getDirectoryHandle(segment)
        await loadDirectory(directory, target)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to open directory.')
      }
    }
    void resolve()
  }, [root, currentPath, loadDirectory])

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4 sm:p-6" role="dialog" aria-modal="true" aria-label="Workspace browser">
      <div className="glass w-full max-w-6xl h-[min(82vh,760px)] rounded-2xl border border-white/[.08] shadow-2xl flex flex-col overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-5 py-3 border-b border-white/[.06]">
          <div className="min-w-0">
            <div className="text-sm font-medium text-white">Workspace Studio</div>
            <div className="text-[11px] text-white/40 mt-0.5 truncate">{rootName}</div>
          </div>
          <div className="flex w-full sm:w-auto flex-wrap items-center gap-2">
            <label className="flex flex-1 sm:flex-none items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/[.04] border border-white/[.06] min-w-[150px] sm:min-w-0">
              <span className="text-white/30" aria-hidden="true">⌕</span>
              <input ref={filterRef} value={query} onChange={e => setQuery(e.target.value)} placeholder="Filter files" aria-label="Filter workspace files" className="w-full sm:w-36 bg-transparent outline-none text-xs text-white placeholder:text-white/25" />
            </label>
            <button type="button" onClick={refreshCurrent} disabled={!current || loading} aria-label="Refresh current folder" title="Refresh current folder" className="w-8 h-8 rounded-lg text-white/45 hover:text-white hover:bg-white/[.06] disabled:opacity-20 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">↻</button>
            <button type="button" onClick={chooseWorkspace} disabled={loading} className="px-3 py-1.5 rounded-lg text-xs text-[#D4A040] bg-[#D4A040]/10 hover:bg-[#D4A040]/15 disabled:opacity-50 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">{loading ? 'Opening…' : root ? 'Change folder' : 'Open folder'}</button>
            <button type="button" onClick={onClose} aria-label="Close workspace" title="Close workspace (Esc)" className="w-8 h-8 rounded-lg text-white/50 hover:text-white hover:bg-white/[.06] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">×</button>
          </div>
        </div>

        {error && <div className="mx-4 mt-3 rounded-lg px-3 py-2 text-xs text-red-300 bg-red-500/10 border border-red-500/20" role="alert">{error}</div>}

        <div className="flex flex-1 min-h-0 flex-col md:flex-row">
          <section className="md:w-[46%] min-h-0 flex flex-col border-b md:border-b-0 md:border-r border-white/[.06]">
            <div className="flex items-center gap-1 px-3 py-2 border-b border-white/[.05] overflow-x-auto">
              <button type="button" onClick={() => jumpToPath(0)} disabled={!root} className="shrink-0 text-[11px] text-white/55 hover:text-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">{rootName}</button>
              {currentPath.map((segment, index) => <span key={`${segment}-${index}`} className="shrink-0 text-white/20 text-[10px]">/ <button type="button" onClick={() => jumpToPath(index + 1)} className="text-white/45 hover:text-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">{segment}</button></span>)}
              <button type="button" onClick={goBack} disabled={!root || currentPath.length === 0} className="ml-auto shrink-0 px-2 py-1 rounded text-[10px] text-white/45 hover:text-white hover:bg-white/[.05] disabled:opacity-20 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]" aria-label="Go to parent directory">↑ Up</button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-2">
              {!root ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-white/40 px-8">
                  <div className="text-sm text-white/65">Choose a workspace folder</div>
                  <div className="text-[11px] mt-1 leading-5">Friday only reads the directory you explicitly select. Hidden dependency/build folders are omitted to keep the explorer fast.</div>
                </div>
              ) : filteredEntries.length === 0 ? (
                <div className="h-40 flex items-center justify-center text-xs text-white/35">{query ? 'No matching files.' : 'This directory is empty.'}</div>
              ) : (
                <div className="space-y-0.5">
                  {filteredEntries.map(entry => (
                    <button key={entry.path} type="button" onClick={() => void openEntry(entry)} className={`w-full flex items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-white/[.05] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040] ${selected?.path === entry.path ? 'bg-white/[.07]' : ''}`}>
                      <span className="w-5 text-center text-xs text-[#D4A040]" aria-hidden="true">{entry.kind === 'directory' ? '▸' : '•'}</span>
                      <span className="text-xs text-white/75 truncate">{entry.name}</span>
                      <span className="ml-auto text-[10px] text-white/20">{entry.kind === 'directory' ? 'folder' : 'file'}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="px-3 py-2 border-t border-white/[.05] text-[10px] text-white/25">{filteredEntries.length} visible {filteredEntries.length === 1 ? 'entry' : 'entries'}{query ? ` · ${entries.length} total` : ''}</div>
          </section>

          <section className="flex-1 min-h-0 flex flex-col bg-black/10">
            <div className="px-4 py-2.5 border-b border-white/[.05] flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs text-white/70 truncate">{selected?.path || 'File preview'}</div>
                <div className="text-[10px] text-white/25">{selected ? 'Read-only browser preview' : 'Select a file from the explorer'}</div>
              </div>
              {selected && <button type="button" onClick={() => { setSelected(null); setPreview(null) }} className="text-[10px] text-white/40 hover:text-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D4A040]">Clear</button>}
            </div>
            <div className="flex-1 min-h-0 overflow-auto p-4">
              {previewLoading ? <div className="text-xs text-white/35" role="status">Loading preview…</div> : preview != null ? <pre className="whitespace-pre-wrap break-words text-[11px] leading-5 text-white/65 font-mono">{preview}</pre> : <div className="h-full flex items-center justify-center text-xs text-white/25 text-center px-8">Workspace files are opened read-only here. Select a text file to inspect it without modifying your local folder.</div>}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export { WorkspaceBrowser }
