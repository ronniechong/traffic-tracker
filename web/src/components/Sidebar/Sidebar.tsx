import { Header } from './Header'
import { Legend } from './Legend'
import { FreewayList } from './FreewayList'
import { formatUpdatedAt } from '../../lib/formatUpdatedAt'
import type { Theme } from '../../map/mapController'
import type { StatusResponse } from '../../api-types'
import styles from './Sidebar.module.css'

interface SidebarProps {
  status: StatusResponse | null
  isPolling: boolean
  freeways: string[]
  hiddenFreeways: ReadonlySet<string>
  onToggleFreeway: (freewayName: string, visible: boolean) => void
  open: boolean
  onClose: () => void
  tracking: boolean
  trackingError: string | null
  onToggleTracking: () => void
  theme: Theme
  onThemeChange: (theme: Theme) => void
}

export function Sidebar({
  status,
  isPolling,
  freeways,
  hiddenFreeways,
  onToggleFreeway,
  open,
  onClose,
  tracking,
  trackingError,
  onToggleTracking,
  theme,
  onThemeChange,
}: SidebarProps) {
  const updatedAt = formatUpdatedAt(status?.updated_at_utc)

  return (
    <aside className={`${styles.sidebar} ${open ? styles.sidebarOpen : ''}`}>
      <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Close menu">
        &times;
      </button>
      <Header theme={theme} onThemeChange={onThemeChange} />
      <Legend />
      <FreewayList freeways={freeways} hidden={hiddenFreeways} onToggle={onToggleFreeway} />
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>My location</h2>
        <button
          type="button"
          className={`${styles.trackButton} ${tracking ? styles.trackButtonActive : ''}`}
          onClick={onToggleTracking}
          aria-pressed={tracking}
        >
          {tracking ? 'Stop tracking' : '📍 Track me'}
        </button>
        {trackingError ? (
          <p className={styles.trackError}>{trackingError}</p>
        ) : (
          <p className={styles.trackHint}>
            Shows your live position on the map using your device's location. Stays on your device — nothing is
            recorded or sent anywhere.
          </p>
        )}
      </div>
      <div className={styles.section}>
        <p className={styles.updatedAt}>
          {isPolling && <span className={styles.pollingSpinner} aria-hidden="true" />}
          {updatedAt ? `Conditions as of ${updatedAt}` : 'Waiting for live data…'}
        </p>
      </div>
      <div className={styles.section}>
        <p className={styles.disclaimer}>
          Experimental project, not an official transport information source. For real-time road conditions, use
          VicRoads or your GPS navigation app.
        </p>
        <p className={styles.attribution}>Data: VIC open data portal's Freeway Travel Time API (VicRoads).</p>
        <p className={styles.attribution}>
          Light/Medium/Heavy conditions are classified by VicRoads (the same labels shown on their freeway signs) —
          the exact thresholds behind each label aren't published.
        </p>
        <p className={styles.attribution}>
          Speed limits shown are VicRoads' own speed-zone data, monthly-refreshed, not live.
        </p>
      </div>
    </aside>
  )
}
