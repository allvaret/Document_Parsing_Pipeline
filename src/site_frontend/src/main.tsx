import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import '@fontsource-variable/source-serif-4'
import '@fontsource-variable/ibm-plex-sans'
import './styles/index.css'
import { createRouter } from './routes'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={createRouter()} />
  </StrictMode>,
)
