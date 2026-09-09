import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { StartupGuard } from './components/common/StartupGuard'
import { UpdateSection } from './components/settings/UpdateSection'
import { watchForUpdates } from './core/autoUpdate'

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
    <ErrorBoundary>
      <StartupGuard>
        <App />
        <MountReady />
      </StartupGuard>
    </ErrorBoundary>
    <div className="fixed bottom-3 right-3 z-40 w-[min(320px,calc(100vw-24px))] rounded-xl glass px-4 shadow-lg">
      <UpdateSection />
    </div>
  </StrictMode>,
)
