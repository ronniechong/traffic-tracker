import styles from './LoadingOverlay.module.css'

export function LoadingOverlay() {
  return (
    <div className={styles.overlay} role="status" aria-live="polite">
      <div className={styles.spinner} />
      <span className={styles.label}>Loading map…</span>
    </div>
  )
}
