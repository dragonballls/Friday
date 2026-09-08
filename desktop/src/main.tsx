import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary, AppErrorFallback } from './components/common/ErrorBoundary'
import { watchForUpdates } from './core/autoUpdate'

// Vite HMR handles development. Production builds refresh themselves when a new
// hashed asset set is deployed, so an already-open Friday stays current.
if (import.meta.env.PROD) watchForUpdates()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary fallback={<AppErrorFallback />}>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
