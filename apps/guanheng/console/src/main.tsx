import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from './workspace/IndependentApp'
import { ConsoleBrowserRouter } from './components/ConsoleBrowserRouter'
import './styles.css'
import { ObserverThemeProvider } from './workspace/ObserverTheme'
import { applyObserverTheme, readObserverTheme } from './workspace/observerAppearance'

applyObserverTheme(readObserverTheme())

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConsoleBrowserRouter>
        <ObserverThemeProvider><App /></ObserverThemeProvider>
      </ConsoleBrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
