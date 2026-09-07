import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import {
  addSegmentLayer,
  initMap,
  querySegmentIdsAtPoint,
  SEGMENT_LINES_LAYER_ID,
  setMapStyle,
  setSegmentData,
  type Theme,
} from '../../map/mapController'
import { renderSegmentTooltipHtml, SEGMENT_TOOLTIP_CLASS } from '../../map/segmentTooltip'
import { createTrafficFlowController, type TrafficFlowController } from '../../map/trafficFlow'
import '../../map/segmentTooltip.css'
import '../../map/userLocation.css'
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
  /** Whether the user has asked to see their live device location. */
  tracking?: boolean
  /** Fired when tracking stops for any reason other than the caller
   * setting `tracking` to false (permission denied, position error, the
   * user pressing the built-in control). */
  onTrackingChange?: (tracking: boolean) => void
  onTrackingError?: (message: string) => void
}

export function MapView({
  theme,
  segments,
  onMapReady,
  tracking = false,
  onTrackingChange,
  onTrackingError,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const segmentsRef = useRef<Segment[] | null>(segments)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const trafficFlowRef = useRef<TrafficFlowController | null>(null)
  const selectedLngLatRef = useRef<maplibregl.LngLat | null>(null)
  const geolocateRef = useRef<maplibregl.GeolocateControl | null>(null)
  // Our own mirror of the control's active state -- GeolocateControl
  // doesn't expose one, and `trigger()` toggles, so we need to know
  // whether a call will turn it on or off.
  const geolocateActiveRef = useRef(false)
  const onTrackingChangeRef = useRef(onTrackingChange)
  const onTrackingErrorRef = useRef(onTrackingError)
  onTrackingChangeRef.current = onTrackingChange
  onTrackingErrorRef.current = onTrackingError
  const [isMapLoading, setIsMapLoading] = useState(true)
  // The segment IDs within the click hit-test buffer, not the segment
  // objects themselves -- content is re-derived from the latest `segments`
  // prop on every poll so the tooltip stays live rather than freezing at
  // click-time data. All IDs at the click point (not just the nearest) so
  // both directions of the same stretch show together -- their lines
  // render close enough together that clicking precisely on just one is
  // impractical at this scale, and segment names don't pair predictably
  // between directions.
  const [selectedSegmentIds, setSelectedSegmentIds] = useState<string[]>([])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const map = initMap(container, theme)
    mapRef.current = map
    const popup = new maplibregl.Popup({
      closeOnClick: false,
      className: SEGMENT_TOOLTIP_CLASS,
      maxWidth: '260px',
    })
    popup.on('close', () => setSelectedSegmentIds([]))
    popupRef.current = popup

    const geolocate = new maplibregl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
      showUserLocation: true,
      showAccuracyCircle: true,
    })
    map.addControl(geolocate)
    geolocateRef.current = geolocate
    geolocate.on('trackuserlocationstart', () => {
      geolocateActiveRef.current = true
    })
    geolocate.on('trackuserlocationend', () => {
      geolocateActiveRef.current = false
      onTrackingChangeRef.current?.(false)
    })
    geolocate.on('error', (err: { code?: number }) => {
      geolocateActiveRef.current = false
      onTrackingChangeRef.current?.(false)
      const message =
        err?.code === 1
          ? 'Location access was denied. Enable it in your browser settings to use Track me.'
          : "Couldn't get your location. Try again in a moment."
      onTrackingErrorRef.current?.(message)
    })

    map.on('load', () => {
      addSegmentLayer(map)
      if (segmentsRef.current) setSegmentData(map, segmentsRef.current)
      // PROTOTYPE: animated traffic-flow overlay, see trafficFlow.ts.
      const trafficFlow = createTrafficFlowController(map)
      if (segmentsRef.current) trafficFlow.setData(segmentsRef.current)
      trafficFlow.start()
      trafficFlowRef.current = trafficFlow
      setIsMapLoading(false)
      onMapReady?.()
    })

    map.on('click', (e) => {
      const ids = querySegmentIdsAtPoint(map, e.point)
      if (ids.length === 0) {
        setSelectedSegmentIds([])
        return
      }
      selectedLngLatRef.current = e.lngLat
      setSelectedSegmentIds((prev) => {
        const same = prev.length === ids.length && prev.every((id) => ids.includes(id))
        return same ? [] : ids
      })
    })

    map.on('mouseenter', SEGMENT_LINES_LAYER_ID, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', SEGMENT_LINES_LAYER_ID, () => {
      map.getCanvas().style.cursor = ''
    })

    return () => {
      trafficFlowRef.current?.stop()
      map.remove()
      mapRef.current = null
      popupRef.current = null
      geolocateRef.current = null
    }
    // theme changes are handled by a separate effect below; re-running
    // this one would tear down and rebuild the whole map unnecessarily.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (isMapLoading) return
    const geolocate = geolocateRef.current
    if (!geolocate) return
    // `trigger()` toggles; only call it when the desired and actual states
    // differ, and ignore the transient false it triggers back through
    // `onTrackingChange` for a caller-initiated stop.
    if (tracking && !geolocateActiveRef.current) {
      geolocateActiveRef.current = true
      geolocate.trigger()
    } else if (!tracking && geolocateActiveRef.current) {
      geolocateActiveRef.current = false
      geolocate.trigger()
    }
  }, [tracking, isMapLoading])

  useEffect(() => {
    segmentsRef.current = segments
    const map = mapRef.current
    if (!map || !segments) return
    setSegmentData(map, segments)
    trafficFlowRef.current?.setData(segments)
  }, [segments])

  useEffect(() => {
    const map = mapRef.current
    const popup = popupRef.current
    if (!map || !popup) return

    if (selectedSegmentIds.length === 0) {
      popup.remove()
      return
    }

    // Empty covers both "no longer in the poll response" and "hidden by a
    // freeway toggle" -- both should dismiss rather than show stale or
    // orphaned content.
    const group = segments?.filter((s) => selectedSegmentIds.includes(s.segment_id)) ?? []
    if (group.length === 0 || !selectedLngLatRef.current) {
      popup.remove()
      setSelectedSegmentIds([])
      return
    }

    popup.setLngLat(selectedLngLatRef.current).setHTML(renderSegmentTooltipHtml(group))
    if (!popup.isOpen()) popup.addTo(map)
  }, [segments, selectedSegmentIds])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    // A style swap (e.g. the OS light/dark preference flipping) tears down
    // and rebuilds the map's sources/layers -- reapply whatever data was
    // already showing immediately, rather than leaving a blank map until
    // the next poll cycle.
    trafficFlowRef.current?.stop()
    setMapStyle(map, theme, () => {
      addSegmentLayer(map)
      if (segmentsRef.current) setSegmentData(map, segmentsRef.current)
      const trafficFlow = createTrafficFlowController(map)
      if (segmentsRef.current) trafficFlow.setData(segmentsRef.current)
      trafficFlow.start()
      trafficFlowRef.current = trafficFlow
    })
  }, [theme])

  return (
    <div className={styles.mapContainer}>
      <div ref={containerRef} className={styles.map} />
      {isMapLoading && <LoadingOverlay />}
    </div>
  )
}
