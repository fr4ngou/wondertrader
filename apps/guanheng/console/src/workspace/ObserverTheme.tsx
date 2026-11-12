import { useState, type ReactNode } from 'react'
import { Eye, Moon, Sun } from 'lucide-react'
import { ObserverThemeContext, readObserverTheme, saveObserverTheme, useObserverAppearance } from './observerAppearance'
import './observer-palettes.css'

const themes = [
  { id: 'white', label: '白色', icon: Sun },
  { id: 'yellow', label: '护眼黄', icon: Eye },
  { id: 'black', label: '黑色', icon: Moon },
] as const

export function ObserverThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState(readObserverTheme)
  return <ObserverThemeContext.Provider value={{
    theme,
    selectTheme: (selected) => { saveObserverTheme(selected); setTheme(selected) },
  }}>{children}</ObserverThemeContext.Provider>
}

export function ObserverThemeSwitch() {
  const { theme, selectTheme } = useObserverAppearance()
  return <div className="observer-theme-switch" role="group" aria-label="界面主题">
    {themes.map(({ id, label, icon: Icon }) => <button key={id} type="button" title={label} aria-label={label}
      aria-pressed={theme === id} onClick={() => selectTheme(id)}>
      <Icon size={16} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span>
    </button>)}
  </div>
}
