import React from 'react'
import styles from './ProgressBar.module.css'

export default function ProgressBar({ progress }) {
  return (
    <div className={styles.track}>
      <div className={styles.fill} style={{ width: `${progress}%` }} />
    </div>
  )
}
