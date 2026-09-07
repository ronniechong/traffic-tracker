import { useEffect, useMemo, useState } from 'react'
import { MapView } from './components/MapView/MapView'
import { Sidebar } from './components/Sidebar/Sidebar'
import { useTrafficData } from './hooks/useTrafficData'
import type { Theme } from './map/mapController'
import styles from './App.module.css'

function getPreferredTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function App() {
  const [theme, setTheme] = useState<Theme>(getPreferredTheme)
  const [hiddenFreeways, setHiddenFreeways] = useState<ReadonlySet<string>>(new Set())
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [tracking, setTracking] = useState(false)
  const [trackingError, setTrackingError] = useState<string | null>(null)
  const { segments, status, isPolling } = useTrafficData()

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setTheme(query.matches ? 'dark' : 'light')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const freeways = useMemo(() => {
    if (!segments) return []
    return [...new Set(segments.map((s) => s.freeway_name))].sort()
  }, [segments])

  const visibleSegments = useMemo(() => {
    if (!segments) return segments
    if (hiddenFreeways.size === 0) return segments
    return segments.filter((s) => !hiddenFreeways.has(s.freeway_name))
  }, [segments, hiddenFreeways])

  function handleToggleFreeway(freewayName: string, visible: boolean) {
    setHiddenFreeways((prev) => {
      const next = new Set(prev)
      if (visible) next.delete(freewayName)
      else next.add(freewayName)
      return next
    })
  }

  function handleToggleTracking() {
    setTrackingError(null)
    setTracking((prev) => !prev)
  }

  return (
    <div className={styles.shell}>
      <button
        type="button"
        className={styles.menuButton}
        onClick={() => setSidebarOpen(true)}
        aria-label="Open menu"
      >
        ☰
      </button>
      {sidebarOpen && (
        <button
          type="button"
          className={styles.backdrop}
          aria-label="Close menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <Sidebar
        status={status}
        isPolling={isPolling}
        freeways={freeways}
        hiddenFreeways={hiddenFreeways}
        onToggleFreeway={handleToggleFreeway}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        tracking={tracking}
        trackingError={trackingError}
        onToggleTracking={handleToggleTracking}
      />
      <div className={styles.mapArea}>
        <MapView
          theme={theme}
          segments={visibleSegments}
          tracking={tracking}
          onTrackingChange={setTracking}
          onTrackingError={setTrackingError}
        />
      </div>
    </div>
  )
}
