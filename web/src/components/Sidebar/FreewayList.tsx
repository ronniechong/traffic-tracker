import { freewayDisplayName } from '../../lib/freewayDisplayName'
import styles from './Sidebar.module.css'

interface FreewayListProps {
  freeways: string[]
  hidden: ReadonlySet<string>
  onToggle: (freewayName: string, visible: boolean) => void
}

export function FreewayList({ freeways, hidden, onToggle }: FreewayListProps) {
  if (freeways.length === 0) return null

  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>Freeways</h2>
      <ul className={styles.freewayList}>
        {freeways.map((freeway) => (
          <li key={freeway} className={styles.freewayRow}>
            <span>{freewayDisplayName(freeway)}</span>
            <label className={styles.toggle}>
              <input
                type="checkbox"
                checked={!hidden.has(freeway)}
                onChange={(e) => onToggle(freeway, e.target.checked)}
              />
              <span className={styles.toggleTrack} />
            </label>
          </li>
        ))}
      </ul>
    </div>
  )
}
