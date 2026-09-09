import { useEffect, useState } from 'react'
import type { Theme } from '../map/mapController'

// `global.css` defines a `data-theme="dark"` override on <html>; this hook
// is what sets it. Persisted once the user picks a side; first visit falls
// back to the OS preference so it isn't forced to light against the
// system setting.
const STORAGE_KEY = 'traffictracker-theme'

function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // localStorage can throw in private-mode / blocked-cookie contexts.
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  function setTheme(next: Theme): void {
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Non-persistent is an acceptable fallback.
    }
    setThemeState(next)
  }

  return [theme, setTheme]
}
