import type { ReactNode } from 'react'
import styles from './Toggle.module.css'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  'aria-label'?: string
  /** Rendered inside the sliding thumb -- the caller picks what to show
   * for the current state (e.g. a sun/moon swap). Passing it bumps the
   * track to a larger size so the glyph fits. */
  icon?: ReactNode
}

export function Toggle({ checked, onChange, 'aria-label': ariaLabel, icon }: ToggleProps) {
  return (
    <span className={`${styles.toggle} ${icon != null ? styles.withIcon : ''}`}>
      <input
        type="checkbox"
        checked={checked}
        aria-label={ariaLabel}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className={styles.track}>
        <span className={styles.thumb}>{icon}</span>
      </span>
    </span>
  )
}
