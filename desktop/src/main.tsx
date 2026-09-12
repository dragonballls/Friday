import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { watchForUpdates } from './core/autoUpdate'

// Production updates remain non-visual. The only application UI is the Jarvis chat bar.
if (import.meta.env.PROD) watchForUpdates()

const root = document.getElementById('root')

if (!root) {
  throw new Error('Jarvis root element was not found.')
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
