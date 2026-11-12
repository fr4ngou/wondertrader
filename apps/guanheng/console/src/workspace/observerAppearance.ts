import { createContext, useContext } from 'react'

export type ObserverTheme = 'white' | 'yellow' | 'black'
export const observerThemeKey = 'guanheng.observer.theme'

export function readObserverTheme(): ObserverTheme {
  try {
    const theme = window.localStorage.getItem(observerThemeKey)
    if (theme === 'yellow' || theme === 'black') return theme
  } catch {
    // 浏览器禁用存储时，本次打开仍可切换外观。
  }
  return 'white'
}

export function applyObserverTheme(theme: ObserverTheme) {
  document.documentElement.dataset.observerTheme = theme
}

export function saveObserverTheme(theme: ObserverTheme) {
  applyObserverTheme(theme)
  try {
    window.localStorage.setItem(observerThemeKey, theme)
  } catch {
    // 外观已应用到当前页面，持久化由浏览器决定。
  }
}

export const ObserverThemeContext = createContext<{
  theme: ObserverTheme
  selectTheme: (theme: ObserverTheme) => void
}>({ theme: 'white', selectTheme: () => undefined })

export const useObserverAppearance = () => useContext(ObserverThemeContext)
export const useObserverTheme = () => useObserverAppearance().theme

/** 将工作区色值解析为图表 Canvas 和 SVG 可直接使用的颜色。 */
export function observerChartColors(element: HTMLElement) {
  const style = getComputedStyle(element)
  const read = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback
  const ink = read('--ink', '#18253a')
  const muted = read('--muted', '#53637a')
  const line = read('--line', '#e0e7f1')
  const border = read('--line-strong', '#b9c7da')
  const accent = read('--accent', '#195bd0')
  const soft = read('--accent-soft', '#e8f0ff')
  const panel = read('--panel-solid', '#ffffff')
  return {
    ink, muted, line, border, accent, soft, panel,
    tooltip: { backgroundColor: panel, borderColor: border, textStyle: { color: ink } },
    slider: { borderColor: border, fillerColor: soft, handleStyle: { color: accent }, textStyle: { color: muted } },
  }
}
