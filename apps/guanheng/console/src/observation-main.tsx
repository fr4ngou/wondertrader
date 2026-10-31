import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConsoleBrowserRouter } from './components/ConsoleBrowserRouter'
import ObservationShell from './observation/ObservationShell'

// Separate build root prevents trading modules and navigation entering remote artifacts.
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } })
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={client}><ConsoleBrowserRouter><ObservationShell /></ConsoleBrowserRouter></QueryClientProvider></StrictMode>)
