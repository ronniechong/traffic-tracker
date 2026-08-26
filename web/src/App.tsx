import { useEffect, useState } from 'react'
import { MapView } from './components/MapView/MapView'
import { Sidebar } from './components/Sidebar/Sidebar'
import { useTrafficData } from './hooks/useTrafficData'
import type { Theme } from './map/mapController'

function getPreferredTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function App() {
  const [theme, setTheme] = useState<Theme>(getPreferredTheme)
  const { segments, status, isPolling } = useTrafficData()

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setTheme(query.matches ? 'dark' : 'light')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return (
    <div style={{ height: '100dvh', width: '100vw', display: 'flex' }}>
      <Sidebar status={status} isPolling={isPolling} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <MapView theme={theme} segments={segments} />
      </div>
    </div>
  )
}
