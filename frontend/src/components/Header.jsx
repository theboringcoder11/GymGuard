import React from 'react'
import styles from './Header.module.css'

export default function Header({ connected }) {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <h1 className={styles.title}>
          GYMGUARD <span className={styles.accent}>CV</span>
        </h1>
        <p className={styles.subtitle}>
          TAILGATE DETECTION · YOLOv8 + BYTETRACK · LOCAL INFERENCE
        </p>
      </div>

      <div className={styles.status}>
        <span
          className={`${styles.dot} ${connected ? styles.dotConnected : styles.dotDisconnected}`}
        />
        <span className={connected ? styles.statusConnected : styles.statusDisconnected}>
          {connected ? 'BACKEND CONNECTED' : 'CONNECTING...'}
        </span>
      </div>
    </header>
  )
}
