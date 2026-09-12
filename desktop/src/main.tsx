import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const root = document.getElementById('root')
if (!root) throw new Error('Friday root element was not found.')
createRoot(root).render(<App />)
window.dispatchEvent(new Event('friday:ready'))
