import { useEffect, useRef, useState } from 'react'
import { fetchSegments, fetchStatus, isPollerHealthy } from '../api'
import type { Segment, StatusResponse } from '../api-types'

const POLL_INTERVAL_MS = 30_000

export interface TrafficData {
  segments: Segment[] | null
  status: StatusResponse | null
  isLoading: boolean
  /** True only while a poll request is actually in flight -- distinct from
   * `isLoading`, which covers just the very first load. */
  isPolling: boolean
}

/** Shared by the map (renders `segments`) and the sidebar (shows `status`'s
 * last-updated time) so both read from one poll loop instead of each
 * fetching independently. */
export function useTrafficData(): TrafficData {
  const [segments, setSegments] = useState<Segment[] | null>(null)
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isPolling, setIsPolling] = useState(false)
  const cancelledRef = useRef(false)

  useEffect(() => {
    cancelledRef.current = false
    let pollTimer: ReturnType<typeof setTimeout> | undefined

    async function loadOnce() {
      setIsPolling(true)
      const [nextStatus, nextSegments] = await Promise.all([fetchStatus(), fetchSegments()])
      if (cancelledRef.current) return
      // A failed status fetch keeps showing the last known-good status
      // (and its last-updated time) rather than blanking it out.
      if (nextStatus) setStatus(nextStatus)
      if (isPollerHealthy(nextStatus) && nextSegments) setSegments(nextSegments)
      setIsPolling(false)
    }

    async function pollLoop() {
      await loadOnce()
      if (cancelledRef.current) return
      pollTimer = setTimeout(pollLoop, POLL_INTERVAL_MS)
    }

    void pollLoop().finally(() => {
      if (!cancelledRef.current) setIsLoading(false)
    })

    return () => {
      cancelledRef.current = true
      if (pollTimer) clearTimeout(pollTimer)
    }
  }, [])

  return { segments, status, isLoading, isPolling }
}
