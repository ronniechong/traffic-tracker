import { useEffect, useRef, useState } from 'react'
import type * as maplibregl from 'maplibre-gl'
import { addSegmentLayer, initMap, setMapStyle, setSegmentData, type Theme } from '../../map/mapController'
import type { Segment } from '../../api-types'
import { LoadingOverlay } from '../LoadingOverlay'
import styles from './MapView.module.css'

interface MapViewProps {
  theme: Theme
  segments: Segment[] | null
  /** The map's own initial-load state (basemap/style ready), not the data
   * poll's -- kept separate from `App`'s data-loading state so the map
   * shows itself as soon as it can render, even before the first poll
   * response arrives. */
  onMapReady?: () => void
}

export function MapView({ theme, segments, onMapReady }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const segmentsRef = useRef<Segment[] | null>(segments)
  const [isMapLoading, setIsMapLoading] = useState(true)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const map = initMap(container, theme)
    mapRef.current = map

    map.on('load', () => {
      addSegmentLayer(map)
      if (segmentsRef.current) setSegmentData(map, segmentsRef.current)
      setIsMapLoading(false)
      onMapReady?.()
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
    // theme changes are handled by a separate effect below; re-running
    // this one would tear down and rebuild the whole map unnecessarily.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    segmentsRef.current = segments
    const map = mapRef.current
    if (!map || !segments) return
    setSegmentData(map, segments)
  }, [segments])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    // A style swap (e.g. the OS light/dark preference flipping) tears down
    // and rebuilds the map's sources/layers -- reapply whatever data was
    // already showing immediately, rather than leaving a blank map until
    // the next poll cycle.
    setMapStyle(map, theme, () => {
      addSegmentLayer(map)
      if (segmentsRef.current) setSegmentData(map, segmentsRef.current)
    })
  }, [theme])

  return (
    <div className={styles.mapContainer}>
      <div ref={containerRef} className={styles.map} />
      {isMapLoading && <LoadingOverlay />}
    </div>
  )
}
