import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary, AppErrorFallback } from './components/common/ErrorBoundary'
import { StartupGuard } from './components/common/StartupGuard'
import { UpdateSection } from './components/settings/UpdateSection'
import { watchForUpdates } from './core/autoUpdate'

if (import.meta.env.PROD) watchForUpdates()

const root = document.getElementById('root')

if (!root) {
  throw new Error('Friday root element was not found.')
}

function PaintWatchdog() {
  useEffect(() => {
    let cancelled = false
    let timer = 0

    const check = () => {
      if (cancelled) return
      const shell = root.querySelector('[aria-label="Friday system status"]')
      const appRoot = root.firstElementChild
      const updatePanel = root.querySelector('[aria-label="Update status"]')

      // Only dismiss the static startup screen once the real dashboard shell
      // has actually painted. This prevents a blank black page when React has
      // mounted but the main interface is not visible.
      if (shell || !appRoot || !updatePanel) {
        window.dispatchEvent(new Event('friday:ready'))
        return
      }

      if (!document.getElementById('friday-paint-fallback')) {
        const panel = document.createElement('div')
        panel.id = 'friday-paint-fallback'
        panel.setAttribute('role', 'alert')
        panel.style.cssText = 'position:fixed;inset:0;z-index:2147483646;display:grid;place-items:center;padding:24px;background:#0a0a0f;color:#f0f0f0;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
        panel.innerHTML = '<section style="width:min(560px,100%);padding:28px;border:1px solid rgba(239,68,68,.28);border-radius:18px;background:rgba(255,255,255,.04);text-align:center"><div style="font-size:28px">⚠</div><h1 style="margin:12px 0 8px;font-size:18px">Friday interface did not paint</h1><p style="margin:0;color:#a0a0a8;font-size:13px">The frontend loaded, but the main workspace did not become visible. The Update control is still responding.</p><button id="friday-paint-reload" type="button" style="margin-top:18px;border:0;border-radius:10px;padding:9px 18px;background:linear-gradient(135deg,#f59e0b,#ffd166);color:#000;cursor:pointer;font-weight:600">Reload Friday</button></section>'
        panel.querySelector('#friday-paint-reload')?.addEventListener('click', () => window.location.reload())
        document.body.appendChild(panel)
      }
    }

    timer = window.setTimeout(check, 1800)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  return null
}

function MountReady() {
  return null
}

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary fallback={<AppErrorFallback />}>
      <StartupGuard>
        <App />
        <MountReady />
      </StartupGuard>
      <PaintWatchdog />
      <div className="fixed bottom-3 right-3 z-40 w-[min(320px,calc(100vw-24px))] rounded-xl glass px-4 shadow-lg">
        <UpdateSection />
      </div>
    </ErrorBoundary>
  </StrictMode>,
)
