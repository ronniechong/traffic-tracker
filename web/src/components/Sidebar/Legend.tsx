import styles from './Sidebar.module.css'

const CONDITION_ROWS: Array<{ label: string; color: string }> = [
  { label: 'Light', color: '#22c55e' },
  { label: 'Medium', color: '#f97316' },
  { label: 'Heavy', color: '#dc2626' },
  { label: 'No data', color: '#9ca3af' },
]

export function Legend() {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>Legend</h2>
      <ul className={styles.legendList}>
        {CONDITION_ROWS.map((row) => (
          <li key={row.label} className={styles.legendRow}>
            <span className={styles.swatch} style={{ backgroundColor: row.color }} />
            {row.label}
          </li>
        ))}
        <li className={styles.legendRow}>
          <span className={styles.dashSwatch} />
          Estimated (interpolated data)
        </li>
      </ul>
    </div>
  )
}
