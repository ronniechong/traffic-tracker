import { useEffect, useRef, useState } from 'react'
import type * as maplibregl from 'maplibre-gl'
import { addSegmentLayer, initMap, setMapStyle, setSegmentData, type Theme } from '../../map/mapController'
import { fetchSegments, fetchStatus, isPollerHealthy } from '../../api'
import type { Segment } from '../../api-types'
import { LoadingOverlay } from '../LoadingOverlay'
import styles from './MapView.module.css'

const POLL_INTERVAL_MS = 30_000

interface MapViewProps {
  theme: Theme
}

export function MapView({ theme }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const lastSegmentsRef = useRef<Segment[] | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const map = initMap(container, theme)
    mapRef.current = map

    let cancelled = false
    let pollTimer: ReturnType<typeof setTimeout> | undefined

    async function loadOnce() {
      const [status, segments] = await Promise.all([fetchStatus(), fetchSegments()])
      if (cancelled) return
      // A degraded poller or a failed/timed-out/non-2xx fetch all collapse
      // to the same outcome: don't populate new data. No banner, no retry
      // indicator -- the map just keeps whatever it already has (or the
      // bare basemap, on first load).
      if (isPollerHealthy(status) && segments) {
        lastSegmentsRef.current = segments
        setSegmentData(map, segments)
      }
    }

    async function pollLoop() {
      await loadOnce()
      if (cancelled) return
      pollTimer = setTimeout(pollLoop, POLL_INTERVAL_MS)
    }

    map.on('load', () => {
      addSegmentLayer(map)
      void pollLoop().finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    })

    return () => {
      cancelled = true
      if (pollTimer) clearTimeout(pollTimer)
      map.remove()
      mapRef.current = null
    }
    // theme changes are handled by a separate effect below; re-running
    // this one would tear down and rebuild the whole map unnecessarily.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    // A style swap (e.g. the OS light/dark preference flipping) tears down
    // and rebuilds the map's sources/layers -- reapply whatever data was
    // already showing immediately, rather than leaving a blank map until
    // the next poll cycle.
    setMapStyle(map, theme, () => {
      addSegmentLayer(map)
      if (lastSegmentsRef.current) setSegmentData(map, lastSegmentsRef.current)
    })
  }, [theme])

  return (
    <div className={styles.mapContainer}>
      <div ref={containerRef} className={styles.map} />
      {isLoading && <LoadingOverlay />}
    </div>
  )
}
