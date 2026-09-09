import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary, AppErrorFallback } from './components/common/ErrorBoundary'
import { StartupGuard } from './components/common/StartupGuard'
import { UpdateSection } from './components/settings/UpdateSection'
import { watchForUpdates } from './core/autoUpdate'

// Vite HMR handles development. Production builds refresh themselves when a new
// hashed asset set is deployed, so an already-open Friday stays current.
if (import.meta.env.PROD) watchForUpdates()

const root = document.getElementById('root')

if (!root) {
  throw new Error('Friday root element was not found.')
}

function MountReady() {
  useEffect(() => {
    window.dispatchEvent(new Event('friday:ready'))
  }, [])
  return null
}

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary fallback={<AppErrorFallback />}>
      <StartupGuard>
        <App />
      </StartupGuard>
      <MountReady />
      <div className="fixed bottom-3 right-3 z-40 w-[min(320px,calc(100vw-24px))] rounded-xl glass px-4 shadow-lg">
        <UpdateSection />
      </div>
    </ErrorBoundary>
  </StrictMode>,
)
