/**
 * Capture a single frame from a MediaStream as a base64 PNG string.
 * Pure function — no React hooks.
 */
export function captureFrame(stream: MediaStream | null): string | null {
  if (!stream) return null

  const video = document.createElement('video')
  video.srcObject = stream
  video.muted = true
  video.playsInline = true

  try {
    // A newly-created video element may not have decoded a frame yet.
    // Avoid drawing an empty frame or leaking a rejected play() promise.
    const playResult = video.play()
    if (playResult && typeof playResult.catch === 'function') {
      playResult.catch(() => {})
    }

    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null
    }

    const canvas = document.createElement('canvas')
    canvas.width = 320
    canvas.height = 240
    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/png').split(',')[1] || null
  } catch {
    return null
  } finally {
    video.pause()
    video.srcObject = null
    video.remove()
  }
}