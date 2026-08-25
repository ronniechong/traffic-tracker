import { useEffect, useState } from 'react'
import { MapView } from './components/MapView/MapView'
import type { Theme } from './map/mapController'

function getPreferredTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function App() {
  const [theme, setTheme] = useState<Theme>(getPreferredTheme)

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setTheme(query.matches ? 'dark' : 'light')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return (
    <div style={{ height: '100dvh', width: '100vw' }}>
      <MapView theme={theme} />
    </div>
  )
}
