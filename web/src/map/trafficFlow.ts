import * as maplibregl from 'maplibre-gl'
import type { Segment } from '../api-types'

// PROTOTYPE -- viability check for animated "moving traffic" dashes on top
// of the existing segment lines. Not wired into any UI toggle yet.
//
// Technique: MapLibre has no native "animate this line's pattern" paint
// property, so this reuses the standard trick (same one Mapbox's own
// "Animate a line" example uses) -- cycle `line-dasharray` through a
// precomputed sequence of phase-shifted patterns. Because the dasharray is
// evaluated along the line's real path in map space (not screen-space SVG
// stroke-dashoffset), it follows bends/curves correctly for free.
//
// `line-dasharray` is NOT a data-driven paint property in the MapLibre
// style spec -- it can't vary per feature within one layer, only per
// layer. So "animate each segment at its own speed_limit_kmh" can't be one
// layer with per-feature speed; it has to become one layer per distinct
// *bucketed* speed, each stepping its dasharray at its own rate. Bucketing
// (round to nearest 5 km/h) keeps the layer count small (a couple dozen at
// most, cheap for MapLibre) while still reading as continuous variation
// rather than the coarse 3-tier condition-only version this replaced.

const FLOW_SOURCE_ID = 'traffic-flow-segments'
const FLOW_LAYER_PREFIX = 'traffic-flow-'
const FLOW_COLOR = '#ffffff'

// One step of the sequence is [gap-before, dash, gap-after] (or a 4-value
// wrapped variant near the seam) in line-width multiples. Stepping through
// it in order reads as a short dash crawling along the line.
const FLOW_DASH_SEQUENCE: number[][] = [
  [0, 4, 3],
  [0.5, 4, 2.5],
  [1, 4, 2],
  [1.5, 4, 1.5],
  [2, 4, 1],
  [2.5, 4, 0.5],
  [3, 4, 0],
  [0, 0.5, 3, 3.5],
  [0, 1, 3, 3],
  [0, 1.5, 3, 2.5],
  [0, 2, 3, 2],
  [0, 2.5, 3, 1.5],
  [0, 3, 3, 1],
  [0, 3.5, 3, 0.5],
]

// speed_limit_kmh is missing for ~1% of segments (zero-match/no-geometry
// in the speed-limit join) -- fall back to a nominal per-condition value
// so those segments still animate at a plausible rate rather than being
// silently excluded from the speed-driven version.
const FALLBACK_SPEED_BY_CONDITION: Record<string, number> = {
  Light: 100,
  Medium: 80,
  Heavy: 60,
}

// Congestion still has to show up somehow -- a Heavy-condition segment
// crawls even on a 100km/h freeway, a Light one flows even on a 60km/h
// arterial. Multiplies the posted limit down toward a "how fast traffic
// is actually moving" estimate. Rough first pass, not calibrated against
// anything real.
const CONDITION_MULTIPLIER: Record<string, number> = {
  Light: 1,
  Medium: 0.65,
  Heavy: 0.35,
}

const BUCKET_ROUNDING_KMH = 5
const MIN_EFFECTIVE_KMH = 15
const MAX_EFFECTIVE_KMH = 110

// Calibrated so a 100km/h effective speed steps at the same 55ms the
// previous condition-only "Light" tier used -- keeps the fastest case
// looking the same, everything else scales down from there.
const REFERENCE_KMH = 100
const REFERENCE_STEP_MS = 55
const MIN_STEP_MS = 40
const MAX_STEP_MS = 260

function effectiveSpeedKmh(segment: Segment): number | null {
  if (segment.condition === 'Blank' || segment.persistent_blank) return null
  const posted = segment.speed_limit_kmh ?? FALLBACK_SPEED_BY_CONDITION[segment.condition] ?? null
  if (posted == null) return null
  const multiplier = CONDITION_MULTIPLIER[segment.condition] ?? 1
  const effective = posted * multiplier
  return Math.min(MAX_EFFECTIVE_KMH, Math.max(MIN_EFFECTIVE_KMH, effective))
}

function bucketKeyFor(effectiveKmh: number): string {
  const rounded = Math.round(effectiveKmh / BUCKET_ROUNDING_KMH) * BUCKET_ROUNDING_KMH
  return String(rounded)
}

function stepIntervalForBucket(bucketKey: string): number {
  const kmh = Number(bucketKey)
  const interval = REFERENCE_STEP_MS * (REFERENCE_KMH / kmh)
  return Math.min(MAX_STEP_MS, Math.max(MIN_STEP_MS, interval))
}

function layerId(bucketKey: string): string {
  return `${FLOW_LAYER_PREFIX}${bucketKey}`
}

function buildFlowGeoJSON(segments: Segment[]): {
  featureCollection: GeoJSON.FeatureCollection<GeoJSON.LineString>
  bucketKeys: Set<string>
} {
  const bucketKeys = new Set<string>()
  const features: GeoJSON.Feature<GeoJSON.LineString>[] = []

  for (const segment of segments) {
    if (segment.geometry_status !== 'available' || segment.geometry === null) continue
    const effective = effectiveSpeedKmh(segment)
    if (effective === null) continue
    const bucketKey = bucketKeyFor(effective)
    bucketKeys.add(bucketKey)
    features.push({
      type: 'Feature',
      properties: { flowBucket: bucketKey },
      geometry: segment.geometry,
    })
  }

  return { featureCollection: { type: 'FeatureCollection', features }, bucketKeys }
}

export interface TrafficFlowController {
  /** Call whenever segment data refreshes (including the first load). */
  setData(segments: Segment[]): void
  start(): void
  stop(): void
}

/** Creates a controller bound to one map instance. Adds its own source
 * (separate from the base segment-lines source) and manages one line
 * layer per active speed bucket, adding/removing layers as the set of
 * buckets present in the data changes across polls. Animation phase per
 * bucket persists across `setData` calls -- a bucket that's still present
 * doesn't visually jump/reset just because a poll happened. */
export function createTrafficFlowController(map: maplibregl.Map): TrafficFlowController {
  map.addSource(FLOW_SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })

  const stepIndex = new Map<string, number>()
  const elapsedSinceStep = new Map<string, number>()

  function ensureLayer(bucketKey: string) {
    const id = layerId(bucketKey)
    if (map.getLayer(id)) return
    map.addLayer({
      id,
      type: 'line',
      source: FLOW_SOURCE_ID,
      filter: ['==', ['get', 'flowBucket'], bucketKey],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': FLOW_COLOR,
        'line-width': 1.5,
        'line-opacity': 0.85,
        'line-dasharray': FLOW_DASH_SEQUENCE[stepIndex.get(bucketKey) ?? 0],
      },
    })
    if (!stepIndex.has(bucketKey)) stepIndex.set(bucketKey, 0)
    if (!elapsedSinceStep.has(bucketKey)) elapsedSinceStep.set(bucketKey, 0)
  }

  function removeLayer(bucketKey: string) {
    const id = layerId(bucketKey)
    if (map.getLayer(id)) map.removeLayer(id)
    stepIndex.delete(bucketKey)
    elapsedSinceStep.delete(bucketKey)
  }

  function setData(segments: Segment[]) {
    const source = map.getSource(FLOW_SOURCE_ID) as maplibregl.GeoJSONSource | undefined
    if (!source) return
    const { featureCollection, bucketKeys } = buildFlowGeoJSON(segments)
    source.setData(featureCollection)

    for (const key of bucketKeys) ensureLayer(key)
    for (const key of [...stepIndex.keys()]) {
      if (!bucketKeys.has(key)) removeLayer(key)
    }
  }

  let rafId: number | null = null
  let lastFrameTime = performance.now()

  function tick(now: number) {
    const delta = now - lastFrameTime
    lastFrameTime = now

    for (const bucketKey of stepIndex.keys()) {
      const id = layerId(bucketKey)
      if (!map.getLayer(id)) continue

      const elapsed = (elapsedSinceStep.get(bucketKey) ?? 0) + delta
      const interval = stepIntervalForBucket(bucketKey)
      if (elapsed < interval) {
        elapsedSinceStep.set(bucketKey, elapsed)
        continue
      }
      elapsedSinceStep.set(bucketKey, 0)

      const next = ((stepIndex.get(bucketKey) ?? 0) + 1) % FLOW_DASH_SEQUENCE.length
      stepIndex.set(bucketKey, next)
      map.setPaintProperty(id, 'line-dasharray', FLOW_DASH_SEQUENCE[next])
    }

    rafId = requestAnimationFrame(tick)
  }

  function start() {
    if (rafId !== null) return
    lastFrameTime = performance.now()
    rafId = requestAnimationFrame(tick)
  }

  function stop() {
    if (rafId !== null) cancelAnimationFrame(rafId)
    rafId = null
  }

  return { setData, start, stop }
}
