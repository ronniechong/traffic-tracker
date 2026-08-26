import { Header } from './Header'
import { Legend } from './Legend'
import { formatUpdatedAt } from '../../lib/formatUpdatedAt'
import type { StatusResponse } from '../../api-types'
import styles from './Sidebar.module.css'

interface SidebarProps {
  status: StatusResponse | null
  isPolling: boolean
}

export function Sidebar({ status, isPolling }: SidebarProps) {
  const updatedAt = formatUpdatedAt(status?.updated_at_utc)

  return (
    <aside className={styles.sidebar}>
      <Header />
      <Legend />
      <div className={styles.section}>
        <p className={styles.updatedAt}>
          {isPolling && <span className={styles.pollingSpinner} aria-hidden="true" />}
          {updatedAt ? `Conditions as of ${updatedAt}` : 'Waiting for live data…'}
        </p>
      </div>
    </aside>
  )
}
