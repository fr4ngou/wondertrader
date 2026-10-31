import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { expect, test } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8')

test('keeps the neutral glass design tokens and readable business-text gate', () => {
  expect(styles).toContain('--bg: #e9ebee')
  expect(styles).toContain('--panel: rgba(247, 248, 250, 0.68)')
  expect(styles).toContain('--accent: #61758a')
  expect(styles).toContain('color-scheme: light')
  expect(styles).toContain('.workspace-page { font-size: 15px; }')
  expect(styles).toContain('.workspace-page button { font-size: 14px; }')
  expect(styles).toContain('.workspace-page strong { font-size: max(13px, 0.8125rem); }')
})

test('keeps the read-only shell on the neutral glass palette', () => {
  expect(styles).toContain('grid-template-columns: var(--sidebar) minmax(0, 1fr)')
  expect(styles).not.toContain('grid-template-columns: var(--sidebar) minmax(760px, 1fr) var(--rail)')
  expect(styles).toContain('Full neutral-glass migration')
  expect(styles).not.toContain('.control-rail {')
  expect(styles).not.toContain('.operator-unlock-form')
  expect(styles).not.toContain('color-scheme:dark')
})

test('keeps the five-workspace sidebar responsive without a control overlay', () => {
  expect(styles).toContain('html, body, #root { width: 100%; min-width: 0;')
  expect(styles).not.toContain('min-width: 960px')
  expect(styles).toContain('@media (max-width: 1100px)')
  expect(styles).toContain(':root { --sidebar: 78px; }')
  expect(styles).toContain('.app-shell { grid-template-columns:var(--sidebar) minmax(0,1fr); }')
  expect(styles).toContain('.nav-item > span,.nav-chevron,.sidebar-footer { display:none; }')
  expect(styles).toContain('@media (max-width: 640px)')
  expect(styles).toContain('.runtime-critical-banner > div { display: grid; min-width: 0; gap: 3px; }')
  expect(styles).toContain('.runtime-critical-banner small { line-height: 1.45; overflow-wrap: anywhere; }')
  expect(styles).toContain('.runtime-issue-list { display: grid; min-width: 0; gap: 9px; }')
  expect(styles).toContain('.runtime-issue-row { display: grid; min-width: 0;')
  expect(styles).toContain('.runtime-issue-row code { min-width: 0;')
  expect(styles).toContain('overflow-wrap: anywhere; word-break: break-word; }')
  expect(styles).toContain('.runtime-issue-row > div:first-child { flex-wrap: wrap; }')
  expect(styles).not.toContain('.control-rail-backdrop {')
  expect(styles).not.toContain('.control-list')
})

test('keeps the connection diagnostic trigger compact at the supported 1280px desktop width', () => {
  expect(styles).toContain('@media (max-width: 1400px)')
  expect(styles).toContain('.connection-details > summary span { display:none; }')
  expect(styles).toContain('.connection-details > summary { width:34px; justify-content:center; padding:0; }')
  expect(styles).toContain('.system-statuses { min-width:0; overflow-x:auto; scrollbar-width:none; }')
})

test('keeps keyboard focus and reduced-motion fallbacks explicit', () => {
  expect(styles).toContain('.skip-link:focus { transform: translateY(0); }')
  expect(styles).toContain(':where(a, button, input, select, textarea, [tabindex]):focus-visible')
  expect(styles).toContain('@media (prefers-reduced-motion: reduce)')
  expect(styles).toContain('transition-duration:.001ms !important')
})

test('does not reintroduce sub-12px business text after the readability gate', () => {
  const marker = '/* Readability gate:'
  const gatedStyles = styles.slice(styles.indexOf(marker))
  const undersized = Array.from(gatedStyles.matchAll(/font-size:\s*(\d+)px/g))
    .map((match) => Number(match[1]))
    .filter((size) => size < 12)

  expect(undersized).toEqual([])
})
