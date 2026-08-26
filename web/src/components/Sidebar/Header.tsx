import styles from './Sidebar.module.css'

export function Header() {
  return (
    <div className={styles.header}>
      <span className={styles.logo} aria-hidden="true">
        🛣️
      </span>
      <h1 className={styles.title}>Melbourne Traffic Tracker</h1>
    </div>
  )
}
