import { useState, useEffect, useRef, useCallback } from 'react'

export type CameraStatus = 'loading' | 'denied' | 'active' | 'idle'

interface UseCameraReturn {
  stream: MediaStream | null
  status: CameraStatus
  requestAccess: () => void
  stop: () => void
}

function stopTracks(stream: MediaStream | null): void {
  try {
    stream?.getTracks().forEach(track => track.stop())
  } catch {
    // A browser may invalidate a track while permissions or devices change.
  }
}

export function useCamera(): UseCameraReturn {
  const [status, setStatus] = useState<CameraStatus>('idle')
  const [stream, setStream] = useState<MediaStream | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const requestGenerationRef = useRef(0)

  useEffect(() => {
    return () => {
      requestGenerationRef.current += 1
      stopTracks(streamRef.current)
      streamRef.current = null
    }
  }, [])

  const requestAccess = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('denied')
      return
    }

    const generation = ++requestGenerationRef.current
    stopTracks(streamRef.current)
    streamRef.current = null
    setStream(null)
    setStatus('loading')

    try {
      const nextStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 160, height: 120, facingMode: 'user' },
        audio: false,
      })

      // A newer request or unmount won the race. Do not publish or leak this stream.
      if (generation !== requestGenerationRef.current) {
        stopTracks(nextStream)
        return
      }

      streamRef.current = nextStream
      setStream(nextStream)
      setStatus('active')
    } catch {
      if (generation !== requestGenerationRef.current) return
      streamRef.current = null
      setStream(null)
      setStatus('denied')
    }
  }, [])

  const stop = useCallback(() => {
    requestGenerationRef.current += 1
    stopTracks(streamRef.current)
    streamRef.current = null
    setStream(null)
    setStatus('idle')
  }, [])

  return { stream, status, requestAccess, stop }
}
