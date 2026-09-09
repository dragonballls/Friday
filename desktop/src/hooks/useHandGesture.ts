import { useEffect, useRef, useState } from 'react'

const SCAN_INTERVAL = 120
const W = 160
const H = 120

function hsv(r: number, g: number, b: number) {
  const mx = Math.max(r, g, b)
  const mn = Math.min(r, g, b)
  const d = mx - mn
  let h = 0
  const s = mx === 0 ? 0 : d / mx
  const v = mx / 255
  if (d !== 0) {
    if (mx === r) h = ((g - b) / d + (g < b ? 6 : 0)) * 60
    else if (mx === g) h = ((b - r) / d + 2) * 60
    else h = ((r - g) / d + 4) * 60
  }
  return { h, s, v }
}

function isSkin(r: number, g: number, b: number) {
  const { h, s, v } = hsv(r, g, b)
  return h >= 0 && h <= 50 && s >= 0.08 && s <= 0.68 && v >= 0.3
}

export function useHandGesture(
  stream: MediaStream | null,
  active: boolean
): { openness: number | null; position: { x: number; y: number } | null } {
  const [openness, setOpenness] = useState<number | null>(null)
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null)
  const lastValueRef = useRef<number | null>(null)
  const lastTimeRef = useRef(0)

  useEffect(() => {
    if (!stream || !active) {
      lastValueRef.current = null
      setOpenness(null)
      setPosition(null)
      return
    }

    let disposed = false
    const video = document.createElement('video')
    video.srcObject = stream
    video.playsInline = true
    video.muted = true

    try {
      const playResult = video.play()
      if (playResult && typeof playResult.catch === 'function') {
        playResult.catch(() => {
          // Camera playback can be rejected by browser autoplay policy.
        })
      }
    } catch {
      // Some browsers can throw synchronously when playback is unavailable.
    }

    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      try { video.pause() } catch {}
      video.srcObject = null
      return
    }

    const tick = () => {
      if (disposed || video.readyState < 2) return
      try {
        ctx.drawImage(video, 0, 0, W, H)
        const img = ctx.getImageData(0, 0, W, H)
        const d = img.data

        let skinCount = 0
        let totalPixels = 0
        let sx = 0, sy = 0

        for (let y = 0; y < H; y += 2) {
          for (let x = 0; x < W; x += 2) {
            const i = (y * W + x) * 4
            totalPixels++
            if (isSkin(d[i], d[i + 1], d[i + 2])) {
              skinCount++
              sx += x
              sy += y
            }
          }
        }

        if (disposed) return

        const ratio = skinCount / totalPixels
        const value = ratio > 0.04
          ? Math.round(Math.min((ratio - 0.04) / 0.26, 1) * 100) / 100
          : null

        if (skinCount > 0) {
          const cx = (sx / skinCount / W) * 2 - 1
          const cy = -(sy / skinCount / H) * 2 + 1
          setPosition({ x: Math.max(-1, Math.min(1, cx)), y: Math.max(-1, Math.min(1, cy)) })
        } else {
          setPosition(null)
        }

        const prev = lastValueRef.current
        const now = Date.now()

        if (value !== prev || now - lastTimeRef.current > 400) {
          lastValueRef.current = value
          lastTimeRef.current = now
          setOpenness(value)
        }
      } catch {
        // Camera frames can become unavailable while permissions or tracks change.
      }
    }

    const id = setInterval(tick, SCAN_INTERVAL)
    tick()

    return () => {
      disposed = true
      clearInterval(id)
      try { video.pause() } catch {}
      video.srcObject = null
    }
  }, [stream, active])

  return { openness, position }
}
