import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react'
import { theme } from './core/ThemeEngine'
import { state, useStore } from './core/StateManager'
import { LeftSidebar } from './components/sidebar/LeftSidebar'
import { StatusRibbon } from './components/topbar/TopBar'
import { WorkspaceBrowser } from './components/workspace/WorkspaceBrowser'
import { AiCore, PERSONA_VISUALS } from './components/center/AiCore'
import { MessageBubble } from './components/chat/MessageBubble'
import { InputBar } from './components/chat/InputBar'
import { CameraIndicator } from './components/common/CameraIndicator'
import { useCamera } from './hooks/useCamera'
import { useHandGesture } from './hooks/useHandGesture'
import { useVoiceInput } from './hooks/useVoiceInput'
import { useVoiceOutput } from './hooks/useVoiceOutput'
import { useWakeWord } from './hooks/useWakeWord'
import { captureFrame } from './hooks/useCameraCapture'
import type { SystemInfo, NewsItem, WeatherData, Earthquake, CryptoData, SpaceData, CveItem, WorldClock, MemoryData, ScreenData, CalendarEvent, EmailMessage, ProactiveAlert, Automation, ApprovalRequest } from './types'
import { AlertToast } from './components/chat/AlertToast'
import { ApprovalDialog } from './components/chat/ApprovalDialog'
import { ToastContainer } from './components/common/Toast'
import { toast } from './core/ToastStore'
const IntelligencePanel = lazy(() => import('./components/sidebar/IntelligencePanel').then(m => ({ default: m.IntelligencePanel })))
const CommandPalette = lazy(() => import('./components/command/CommandPalette').then(m => ({ default: m.CommandPalette })))
const SettingsPanel = lazy(() => import('./components/settings/SettingsPanel').then(m => ({ default: m.SettingsPanel })))
import { streamChat, checkHealth, getSessions, createSession, deleteSession, getOutputDir, setOutputDir, getGoogleAuth, getNews, getWeather, getStocks, getGithubTrending, getEarthquakes, getCrypto, getSpace, getCve, getScreen, getMemory, deleteMemory, getCalendarEvents, getEmailInbox, getEmailUnread, connectEventSource, getAutomations, toggleAutomation, deleteAutomation, triggerAutomation, analyzeVisionImage, getVisionScreen, resolveApproval, streamAutopilot, getKnowledgeContinuity, getComputerStatus, getPrivacyStatus } from './core/api'
import type { ServerEvent } from './core/api'
import { BrainView } from './components/autopilot/BrainView'
import { ZenStage } from './components/zen/ZenStage'
import { Onboarding } from './components/zen/Onboarding'
import type { AutopilotRun, AutopilotStepStatus } from './types'

let msgId = 0
const nextId = () => `m${++msgId}`
const LANG_CYCLE = ['en-US', 'hi-IN', 'ur-PK']
const PERSONA_TTS: Record<string, { rate: number; pitch: number }> = {
  jarvis: { rate: 0.9, pitch: 1.0 },
  friday: { rate: 1.0, pitch: 1.1 },
  cortana: { rate: 0.95, pitch: 1.05 },
  adonis: { rate: 0.95, pitch: 0.95 },
}

function showNativeNotification(title: string, body: string) {
  try {
    if (!('Notification' in window)) return
    if (Notification.permission === 'granted') {
      try { new Notification(title, { body }) } catch { /* Ignore unavailable notification constructors. */ }
      return
    }
    if (Notification.permission === 'denied') return
    const request = Notification.requestPermission()
    if (request && typeof request.then === 'function') {
      request.then(p => {
        if (p === 'granted') {
          try { new Notification(title, { body }) } catch { /* Ignore unavailable notification constructors. */ }
        }
      }).catch(() => {})
    }
  } catch {
    // Notifications are optional and may be blocked by browser policy.
  }
}

function readLocalStorage(key: string, fallback = ''): string {
  try { return window.localStorage.getItem(key) ?? fallback } catch { return fallback }
}

function writeLocalStorage(key: string, value: string): void {
  try { window.localStorage.setItem(key, value) } catch { /* Ignore restricted/private storage failures. */ }
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
    const [workspaceOpen, setWorkspaceOpen] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)
  const [camActive, setCamActive] = useState(false)
  const [backendOnline, setBackendOnline] = useState(true)
  const backendOnlineDebug = (value: boolean, source: string) => {
    console.log('[BACKEND ONLINE]', value, source)
    setBackendOnline(value)
  }
  const [outputDir, setOutputDirState] = useState(() => readLocalStorage('friday_output_dir'))
  const [dataLoaded, setDataLoaded] = useState(false)
  const [sseConnected, setSseConnected] = useState(false)
  const [alerts, setAlerts] = useState<ProactiveAlert[]>([])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [intelligenceOpen, setIntelligenceOpen] = useState(() => readLocalStorage('friday_intelligence_open', '1') !== '0')
  const [personaPrompts, setPersonaPrompts] = useState<Record<string, string>>(() => {
    try {
      const raw = readLocalStorage('friday_persona_prompts')
      return raw ? JSON.parse(raw) : {}
    } catch { return {} }
  })
const [briefing, setBriefing] = useState<{ summary: string; sections: string[]; greeting: string; yesterday?: string } | null>(null)
const [automations, setAutomations] = useState<Automation[]>([])
const [visionScreenResult, setVisionScreenResult] = useState<{ description: string; text: string | null; timestamp: number } | null>(null)
const [visionCameraResult, setVisionCameraResult] = useState<{ description: string; text: string | null; timestamp: number } | null>(null)
const [visionAnalyzing, setVisionAnalyzing] = useState(false)
const [holodeckExpanded, setHolodeckExpanded] = useState(true)
const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null)
  const [autopilotRun, setAutopilotRun] = useState<AutopilotRun | null>(null)
  const [now, setNow] = useState(() => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }))
  const [continuity, setContinuity] = useState('')
  const [computerReady, setComputerReady] = useState(false)
  const [computerStatus, setComputerStatus] = useState<{ platform: string; mouse_keyboard: boolean; window_management: boolean } | null>(null)
  const [blackout, setBlackout] = useState(false)
  const [showOnboarding, setShowOnboarding] = useState(() => {
    try { return readLocalStorage('friday_onboarded', '1') !== '1' } catch { return true }
  })

  // ── Fine-grained Zustand selectors (before any hooks that use them) ───
  const sessions = useStore(s => s.sessions)
  const activeSessionId = useStore(s => s.activeSessionId)
  const loading = useStore(s => s.loading)
  const orb = useStore(s => s.orb)
  const voiceLanguage = useStore(s => s.voiceLanguage)
  const persona = useStore(s => s.persona)
  const personaName = (PERSONA_VISUALS[persona] || PERSONA_VISUALS.friday).name
  const metricsState = useStore(s => s.metrics)
  const zen = useStore(s => s.zen)
  const handsFree = useStore(s => s.handsFree)
  const active = useStore(s => {
    const found = s.sessions.find(ses => ses.id === s.activeSessionId)
    return found || s.sessions[0]
  })

  const [systemInfo, setSystemInfo] = useState<SystemInfo>({
    hostname: '-', os: '-', cpu_cores: 0, python_version: '-',
    uptime_seconds: 0, llm_calls: 0, tokens_used: 0, failures: 0, retries: 0,
    model: '-', provider: '-',
  })
  const [news, setNews] = useState<NewsItem[]>([])
  const [weather, setWeather] = useState<WeatherData | null>(null)
  const [stocks, setStocks] = useState<any[]>([])
  const [repos, setRepos] = useState<any[]>([])
  const [earthquakes, setEarthquakes] = useState<Earthquake[]>([])
  const [crypto, setCrypto] = useState<CryptoData[]>([])
  const [space, setSpace] = useState<SpaceData | null>(null)
  const [cve, setCve] = useState<CveItem[]>([])
  const [clocks, setClocks] = useState<WorldClock[]>([])

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const handleGoogleConnect = useCallback(() => {
    getGoogleAuth().then(d => {
      if (d.url) {
        const popup = window.open(d.url, '_blank')
        if (!popup || popup.closed) {
          alert('Please allow popups for this site to connect Google Calendar and Email.')
        }
      }
    }).catch(() => {})
  }, [])

  const { stream, status: camStatus, requestAccess, stop: stopCam } = useCamera()
  const { openness, position: handPosition } = useHandGesture(stream, camActive)

  const {
    isSupported: voiceInputSupported,
    status: voiceInputStatus,
    interimTranscript,
    finalTranscript,
    startListening: startVoiceInput,
    stopListening: stopVoiceInput,
    cancelAutoRestart,
    resetTranscript,
  } = useVoiceInput()

  const {
    enabled: voiceOutputEnabled,
    setEnabled: setVoiceOutputEnabled,
    status: voiceOutputStatus,
    speak: speakResponse,
    stop: stopVoiceOutput,
  } = useVoiceOutput()

  const {
    active: wakeWordActive,
    start: startWakeWord,
    stop: stopWakeWord,
  } = useWakeWord(() => {
    cancelAutoRestart()
    resetTranscript()
    if (!ambientActive) {
      setAmbientActive(true)
    }
    startVoiceInput(voiceLanguage, true)
  })

  // ── Ambient Voice Mode ─────────────────────────────────────────────────
  const [ambientActive, setAmbientActive] = useState(false)
  const ambientTranscriptRef = useRef('')
  const ambientSilenceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const ambientActiveRef = useRef(false)

  const clearAmbientSilence = useCallback(() => {