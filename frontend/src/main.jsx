import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './app/App'
import './styles/base.css'
import './styles/layout.css'
import './styles/components.css'
import './styles/feed.css'
import './styles/upload.css'
import './styles/upload-editor.css'
import './styles/auth.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
