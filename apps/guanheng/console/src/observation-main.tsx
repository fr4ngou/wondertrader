import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConsoleBrowserRouter } from './components/ConsoleBrowserRouter'
import ObservationShell from './observation/ObservationShell'
import { ObserverThemeProvider, ObserverThemeSwitch } from './workspace/ObserverTheme'
import { applyObserverTheme, readObserverTheme } from './workspace/observerAppearance'

applyObserverTheme(readObserverTheme())

// Separate build root prevents trading modules and navigation entering remote artifacts.
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } })
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={client}><ConsoleBrowserRouter><ObserverThemeProvider><ObservationShell appearance={<ObserverThemeSwitch />} /></ObserverThemeProvider></ConsoleBrowserRouter></QueryClientProvider></StrictMode>)
