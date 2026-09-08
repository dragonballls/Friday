import { memo, useRef, useEffect } from 'react'

interface CameraIndicatorProps {
  stream: MediaStream | null
  active: boolean
  openness: number | null
  onToggle: () => void
  voiceInputStatus: string
  voiceOutputStatus: string
}

export const CameraIndicator = memo(function CameraIndicator({
  stream, active, openness, onToggle, voiceInputStatus, voiceOutputStatus,
}: CameraIndicatorProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream
  }, [stream])

  if (!active) return null

  const voiceLabel = voiceInputStatus === 'listening'
    ? 'LISTENING'
    : voiceOutputStatus === 'speaking'
      ? 'SPEAKING'
      : null

  const gestureLabel = openness != null
    ? openness > 0.5 ? 'Open hand' : 'Fist'
    : 'Gesture unavailable'

  return (
    <button
      type="button"
      className="fixed bottom-4 right-4 z-50 group w-[76px] h-[56px] sm:w-[84px] sm:h-[62px] cursor-pointer rounded-xl overflow-hidden transition-all duration-300 hover:scale-105 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
      onClick={onToggle}
      title="Disable gesture control"
      aria-label={`Gesture camera active. ${gestureLabel}. Click to disable gesture control.`}
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        aria-hidden="true"
        className="w-full h-full object-cover rounded-xl pointer-events-none"
        style={{ transform: 'scaleX(-1)' }}
      />
      <div
        className="absolute inset-0 rounded-xl pointer-events-none"
        style={{
          border: '1px solid rgba(255,255,255,0.1)',
          background: 'linear-gradient(to bottom, transparent 50%, rgba(0,0,0,0.4) 100%)',
        }}
      />
      <div className="absolute top-1 left-1.5 flex items-center gap-1 pointer-events-none">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse shadow-[0_0_4px_rgba(74,222,128,0.6)]" aria-hidden="true" />
        <span className="text-[7px] font-medium tracking-widest text-white/50">CAM</span>
      </div>

      <div className="absolute bottom-1 left-1.5 flex items-center gap-1 pointer-events-none">
        <span
          className="text-[8px] font-bold tracking-wider"
          style={{ color: openness != null ? '#f59e0b' : '#444' }}
        >
          {openness != null ? (openness > 0.5 ? 'OPEN' : 'FIST') : '--'}
        </span>
      </div>

      {voiceLabel && (
        <div className="absolute bottom-1 right-1.5 flex items-center gap-1 pointer-events-none" aria-live="polite">
          <span
            className="text-[8px] font-bold tracking-wider"
            style={{ color: voiceInputStatus === 'listening' ? '#ef4444' : '#D4A040' }}
          >
            {voiceLabel}
          </span>
        </div>
      )}
    </button>
  )
})
