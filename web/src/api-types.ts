export type Condition = 'Blank' | 'Light' | 'Medium' | 'Heavy'

// Coarser than the API's raw 0-1 fraction -- the map only needs to decide
// "does this segment get the estimated-data treatment," not the exact
// interpolation percentage.
export type DataSubstitutionTier = 'measured' | 'partially_interpolated' | 'majority_interpolated' | string

export type GeometryStatus = 'available' | 'never_available' | string

export interface Segment {
  segment_id: string
  freeway_name: string
  segment_name: string
  direction: string
  condition: Condition
  data_substitution: number
  data_substitution_tier: DataSubstitutionTier
  published_time_utc: string
  is_stale: boolean
  geometry_status: GeometryStatus
  geometry: GeoJSON.LineString | null
  has_override: boolean
}

export interface StatusResponse {
  poller_status: string
  segment_baseline_stable: boolean
  consecutive_failures: number
  updated_at_utc: string
}
