const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8080/api/v1').replace(/\/$/, '')

type StreamEventHandler = (event: any) => void

type StreamErrorHandler = (error: any) => void

async function streamEndpoint(
  path: string,
  body: Record<string, unknown>,
  onEvent: StreamEventHandler,
  onError: StreamErrorHandler,
  onDone: () => void,
  controller: AbortController,
) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })

    if (!response.ok) {
      const data = await response.json().catch(() => null)
      onError({
        status: response.status,
        message: data?.error || response.statusText || `HTTP ${response.status}`,
      })
      onDone()
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError({ message: 'Friday received no response stream.' })
      onDone()
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        try {
          onEvent(JSON.parse(line))
        } catch {
          // Ignore malformed partial events rather than killing a live run.
        }
      }
    }

    buffer += decoder.decode()
    if (buffer.trim()) {
      try {
        onEvent(JSON.parse(buffer))
      } catch {
        // Ignore malformed final events.
      }
    }

    onDone()
  } catch (error: any) {
    if (error?.name !== 'AbortError') {
      onError(error)
      onDone()
    }
  }
}

export function checkHealth(): Promise<boolean> {
  return fetch(`${API_BASE}/health`, { cache: 'no-store' })
    .then(response => response.ok)
    .catch(() => false)
}

export function streamAutopilot(
  goal: string,
  onEvent: StreamEventHandler,
  onError: StreamErrorHandler,
  onDone: () => void,
): AbortController {
  const controller = new AbortController()
  void streamEndpoint('/autopilot', { goal }, onEvent, onError, onDone, controller)
  return controller
}
