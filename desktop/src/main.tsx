import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary, AppErrorFallback } from './components/common/ErrorBoundary'
import { StartupGuard } from './components/common/StartupGuard'
import { MountReady } from './components/common/MountReady'
import { watchForUpdates } from './core/autoUpdate'

// Production updates are detected automatically every second. The watcher is
// deliberately non-visual: the application itself must remain the primary UI.
// Vite HMR handles development.
if (import.meta.env.PROD) watchForUpdates()

const root = document.getElementById('root')

if (!root) {
  throw new Error('Friday root element was not found.')
}

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary fallback={<AppErrorFallback />}>
      <StartupGuard>
        <App />
        <MountReady />
      </StartupGuard>
    </ErrorBoundary>
  </StrictMode>,
)
