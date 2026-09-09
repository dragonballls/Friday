import { useState, useEffect, useRef, useCallback } from 'react'

export type CameraStatus = 'loading' | 'denied' | 'active' | 'idle'

interface UseCameraReturn {
  stream: MediaStream | null
  status: CameraStatus
  requestAccess: () => void
  stop: () => void
}

export function useCamera(): UseCameraReturn {
  const [status, setStatus] = useState<CameraStatus>('idle')
  const [stream, setStream] = useState<MediaStream | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop())
    }
  }, [])

  const requestAccess = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('denied')
      return
    }

    setStatus('loading')
    try {
      streamRef.current?.getTracks().forEach(t => t.stop())
      const s = await navigator.mediaDevices.getUserMedia({
        video: { width: 160, height: 120, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = s
      setStream(s)
      setStatus('active')
    } catch {
      streamRef.current = null
      setStream(null)
      setStatus('denied')
    }
  }, [])

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    setStream(null)
    setStatus('idle')
  }, [])

  return { stream, status, requestAccess, stop }
}
