export type ToastKind = 'success' | 'error' | 'warning' | 'info'

export interface ToastItem {
  id: number
  kind: ToastKind
  message: string
  createdAt: number
}

type Listener = (toasts: ToastItem[]) => void
type HistoryListener = (history: ToastItem[]) => void

const MAX_HISTORY = 50
let nextId = 1
const listeners = new Set<Listener>()
const historyListeners = new Set<HistoryListener>()
let current: ToastItem[] = []
let history: ToastItem[] = []

function notify() {
  listeners.forEach(l => l(current))
}

function notifyHistory() {
  historyListeners.forEach(l => l(history))
}

export function clearToasts() {
  current = []
  notify()
}

export function clearToastHistory() {
  history = []
  notifyHistory()
}

export function toast(kind: ToastKind, message: string, ttl = 4500) {
  const item: ToastItem = { id: nextId++, kind, message, createdAt: Date.now() }
  current = [...current, item]
  history = [item, ...history].slice(0, MAX_HISTORY)
  notify()
  notifyHistory()
  globalThis.setTimeout(() => {
    current = current.filter(t => t.id !== item.id)
    notify()
  }, Math.max(0, ttl))
}

export function dismissToast(id: number) {
  current = current.filter(t => t.id !== id)
  notify()
}

export function getToasts(): ToastItem[] {
  return current
}

export function getToastHistory(): ToastItem[] {
  return history
}

export function subscribeToasts(listener: Listener) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function subscribeToastHistory(listener: HistoryListener) {
  historyListeners.add(listener)
  return () => { historyListeners.delete(listener) }
}
