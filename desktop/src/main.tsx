import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary, AppErrorFallback } from './components/common/ErrorBoundary'
import { UpdateSection } from './components/settings/UpdateSection'
import { watchForUpdates } from './core/autoUpdate'

// Vite HMR handles development. Production builds refresh themselves when a new
// hashed asset set is deployed, so an already-open Friday stays current.
if (import.meta.env.PROD) watchForUpdates()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary fallback={<AppErrorFallback />}>
      <App />
      <div className="fixed bottom-3 right-3 z-40 w-[320px] rounded-xl glass px-4">
        <UpdateSection />
      </div>
    </ErrorBoundary>
  </StrictMode>,
)
