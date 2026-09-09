import { Toggle } from '../Toggle'
import type { Theme } from '../../map/mapController'
import styles from './Sidebar.module.css'

interface HeaderProps {
  theme: Theme
  onThemeChange: (theme: Theme) => void
}

export function Header({ theme, onThemeChange }: HeaderProps) {
  return (
    <div className={styles.header}>
      <span className={styles.logo} aria-hidden="true">
        🛣️
      </span>
      <h1 className={styles.title}>Melbourne Traffic Tracker</h1>
      <label className={styles.themeToggle}>
        <Toggle
          checked={theme === 'dark'}
          onChange={(checked) => onThemeChange(checked ? 'dark' : 'light')}
          aria-label="Dark mode"
          icon={theme === 'dark' ? '🌙' : '☀️'}
        />
      </label>
    </div>
  )
}
