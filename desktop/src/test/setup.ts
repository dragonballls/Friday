import '@testing-library/jest-dom'

class LocalStorageMock {
  private store: Record<string, string> = {}
  clear() { this.store = {} }
  getItem(key: string) { return this.store[key] ?? null }
  setItem(key: string, value: string) { this.store[key] = value }
  removeItem(key: string) { delete this.store[key] }
  get length() { return Object.keys(this.store).length }
  key(index: number) { return Object.keys(this.store)[index] ?? null }
}

if (!globalThis.localStorage) {
  globalThis.localStorage = new LocalStorageMock()
}

if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = () => {}
}

if (!HTMLCanvasElement.prototype.getContext) {
  HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext
}

const canvasContext = {
  createRadialGradient: () => ({ addColorStop: () => {} }),
  fillStyle: '',
  fillRect: () => {},
}

const originalGetContext = HTMLCanvasElement.prototype.getContext
HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, contextId: string, ...args: unknown[]) {
  if (contextId === '2d') return canvasContext as unknown as CanvasRenderingContext2D
  return originalGetContext.call(this, contextId as never, ...args as never[])
} as typeof HTMLCanvasElement.prototype.getContext