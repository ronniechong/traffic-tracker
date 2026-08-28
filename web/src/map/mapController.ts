import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Segment } from '../api-types'

// OpenFreeMap: free, keyless, no published rate limits -- avoids shipping
// a paid/quota-limited tile-provider key in a public static build.
export type Theme = 'light' | 'dark'

const OPENFREEMAP_STYLES: Record<Theme, string> = {
  light: 'https://tiles.openfreemap.org/styles/liberty',
  dark: 'https://tiles.openfreemap.org/styles/dark',
}

export const SEGMENTS_SOURCE_ID = 'freeway-segments'
export const SEGMENT_LINES_LAYER_ID = 'freeway-segment-lines'

// A few pixels of slack around the click point -- segment lines are thin
// (3px) and often close together, so an exact-pixel hit test would miss
// clicks that visually land on a line.
const CLICK_HIT_RADIUS_PX = 4

// Centers on the CBD for first load -- most freeway corridors converge
// there, so it's a more useful starting view than the whole metro extent.
const MELBOURNE_CENTER: [number, number] = [144.9631, -37.8136]
const INITIAL_ZOOM = 12

// A generous box around the 12 covered freeways' real extent (from South
// Gippsland Fwy's southeast reach to the Western Ring Rd/Calder Fwy's
// northwest edge) -- keeps panning within the coverage area instead of
// letting the map wander to unrelated parts of the country. Deliberately
// loose, not a tight crop to each freeway's exact bounding box.
const COVERAGE_BOUNDS: maplibregl.LngLatBoundsLike = [
  [144.3, -38.35],
  [145.9, -37.55],
]

// Condition colors, kept out of the orange/red-only trap: Light is green
// (not the confusable red/green pairing on its own -- Medium's orange and
// Heavy's red are still distinguishable from Light by lightness/hue, not
// just hue alone), Blank is a neutral grey rather than any traffic color
// since it carries no condition signal at all.
const CONDITION_COLORS: Record<string, string> = {
  Light: '#22c55e',
  Medium: '#f97316',
  Heavy: '#dc2626',
  Blank: '#9ca3af',
}
const DEFAULT_CONDITION_COLOR = CONDITION_COLORS.Blank

// A visibly darker grey than transient Blank -- a segment with no data
// right now reads differently from one with no data for hours, even
// though both carry no condition signal to color by.
const PERSISTENT_BLANK_COLOR = '#4b5563'

// Segments beyond this substitution tier get the "estimated" dashed
// treatment rather than reading as normal live data.
const ESTIMATED_TIERS = new Set(['partially_interpolated', 'majority_interpolated'])

function isRenderable(segment: Segment): boolean {
  // `never_available` (and any other non-`available` status) means this
  // segment has no usable geometry at all, not even a cached fallback --
  // silently rendering nothing for it is correct, rendering a broken/empty
  // line would be worse.
  return segment.geometry_status === 'available' && segment.geometry !== null
}

export function segmentsToGeoJSON(segments: Segment[]): GeoJSON.FeatureCollection<GeoJSON.LineString> {
  return {
    type: 'FeatureCollection',
    features: segments
      .filter(isRenderable)
      .map((segment) => ({
        type: 'Feature',
        properties: {
          id: segment.segment_id,
          condition: segment.condition,
          estimated: ESTIMATED_TIERS.has(segment.data_substitution_tier),
          persistentBlank: segment.persistent_blank,
        },
        // isRenderable already checked non-null.
        geometry: segment.geometry as GeoJSON.LineString,
      })),
  }
}

export function initMap(container: HTMLElement, theme: Theme): maplibregl.Map {
  return new maplibregl.Map({
    container,
    style: OPENFREEMAP_STYLES[theme],
    center: MELBOURNE_CENTER,
    zoom: INITIAL_ZOOM,
    minZoom: 8,
    maxBounds: COVERAGE_BOUNDS,
    attributionControl: { compact: true },
  }).addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
}

/** Adds the segment-line layer. Call once after the map's `load` event --
 * GeoJSON sources can't be added before the style is ready. */
export function addSegmentLayer(map: maplibregl.Map): void {
  map.addSource(SEGMENTS_SOURCE_ID, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  })

  map.addLayer({
    id: SEGMENT_LINES_LAYER_ID,
    type: 'line',
    source: SEGMENTS_SOURCE_ID,
    layout: { 'line-join': 'round', 'line-cap': 'round' },
    paint: {
      'line-color': [
        'case',
        ['get', 'persistentBlank'],
        PERSISTENT_BLANK_COLOR,
        [
          'match',
          ['get', 'condition'],
          'Light',
          CONDITION_COLORS.Light,
          'Medium',
          CONDITION_COLORS.Medium,
          'Heavy',
          CONDITION_COLORS.Heavy,
          'Blank',
          CONDITION_COLORS.Blank,
          DEFAULT_CONDITION_COLOR,
        ],
      ],
      // Estimated segments render lower-opacity and dashed so they read as
      // "the data behind this is inferred," not as a rendering glitch.
      'line-opacity': ['case', ['get', 'estimated'], 0.55, 0.9],
      'line-width': 3,
      'line-dasharray': ['case', ['get', 'estimated'], ['literal', [2, 1.5]], ['literal', [1, 0]]],
    },
  })
}

export function setSegmentData(map: maplibregl.Map, segments: Segment[]): void {
  const source = map.getSource(SEGMENTS_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
  // A failed fetch means the caller simply never calls this again with new
  // data -- the source keeps showing whatever it last had (or nothing, on
  // first load), which is the intended fail-silent behavior.
  if (!source) return
  source.setData(segmentsToGeoJSON(segments))
}

export function setMapStyle(map: maplibregl.Map, theme: Theme, onReady: () => void): void {
  map.setStyle(OPENFREEMAP_STYLES[theme])
  map.once('style.load', onReady)
}

/** Returns the `segment_id` of the segment nearest a click point, or
 * `undefined` if the click didn't land on (or near) a rendered segment. */
export function querySegmentIdAtPoint(map: maplibregl.Map, point: maplibregl.PointLike): string | undefined {
  return querySegmentIdsAtPoint(map, point)[0]
}

/** Returns every distinct `segment_id` within the click hit-test buffer,
 * nearest first. Opposite-direction carriageways render as separate,
 * closely-parallel lines with unrelated `segment_name` strings (VicRoads
 * doesn't name direction pairs symmetrically -- "A to B" vs. a differently
 * worded reverse, not a matching "B to A"), so proximity is the only
 * reliable way to find both directions of the same click. */
export function querySegmentIdsAtPoint(map: maplibregl.Map, point: maplibregl.PointLike): string[] {
  const { x, y } = point as { x: number; y: number }
  const bbox: [maplibregl.PointLike, maplibregl.PointLike] = [
    [x - CLICK_HIT_RADIUS_PX, y - CLICK_HIT_RADIUS_PX],
    [x + CLICK_HIT_RADIUS_PX, y + CLICK_HIT_RADIUS_PX],
  ]
  const features = map.queryRenderedFeatures(bbox, { layers: [SEGMENT_LINES_LAYER_ID] })
  const seen = new Set<string>()
  const ids: string[] = []
  for (const feature of features) {
    const id = feature.properties?.id
    if (typeof id === 'string' && !seen.has(id)) {
      seen.add(id)
      ids.push(id)
    }
  }
  return ids
}
