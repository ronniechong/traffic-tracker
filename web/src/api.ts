import type { Segment, StatusResponse } from './api-types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined

const FETCH_TIMEOUT_MS = 8000

async function fetchJson<T>(path: string): Promise<T | null> {
  if (!BASE_URL) return null

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
  try {
    const response = await fetch(`${BASE_URL}${path}`, { signal: controller.signal })
    // Any non-2xx (including 429) is treated the same as a network
    // failure here -- the caller's job is only to decide whether it has
    // fresh data to show, not to explain why it doesn't.
    if (!response.ok) return null
    return (await response.json()) as T
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

export async function fetchStatus(): Promise<StatusResponse | null> {
  return fetchJson<StatusResponse>('/v1/status')
}

export async function fetchSegments(): Promise<Segment[] | null> {
  return fetchJson<Segment[]>('/v1/segments')
}

// A degraded poller means the API is technically reachable but its
// underlying data may be stale/wrong beyond what `is_stale` per-segment
// flags already communicate -- treated as "no new data" rather than
// rendering a status label the map deliberately never surfaces.
export function isPollerHealthy(status: StatusResponse | null): boolean {
  if (!status) return false
  return status.poller_status === 'ok'
}
