import type { ReactNode } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { observationBase } from '../observation/deploymentBase'

/**
 * Keep top-level workspace navigation synchronous.
 *
 * The Console combines React Router with several high-frequency external
 * stores (TanStack Query plus the SSE stream). React Router v7 wraps link
 * navigation in a transition by default; continuous external-store updates
 * can leave the URL committed while the previous workspace remains rendered.
 * Disabling route transitions here keeps the fixed shell and its workspace
 * content authoritative to the same location.
 */
export function ConsoleBrowserRouter({ children }: { children: ReactNode }) {
  return <BrowserRouter basename={observationBase(import.meta.env.VITE_OBSERVATION_BASE) || '/'} useTransitions={false}>{children}</BrowserRouter>
}
