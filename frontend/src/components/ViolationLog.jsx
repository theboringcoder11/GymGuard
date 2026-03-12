import React from 'react'
import styles from './ViolationLog.module.css'

function ViolationRow({ violation }) {
  return (
    <div className={styles.row}>
      <span className={styles.id}>#{violation.id}</span>
      <span className={styles.time}>{violation.timestamp}s</span>
      <span className={styles.countBadge}>{violation.people}</span>
      <span className={styles.detail}>
        TAILGATE — {violation.people} people / 1 swipe
      </span>
    </div>
  )
}

export default function ViolationLog({ violations }) {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>VIOLATION LOG</span>
        {violations.length > 0 && (
          <span className={styles.badge}>{violations.length} FLAGGED</span>
        )}
      </div>

      <div className={styles.columnHeaders}>
        <span>EVENT</span>
        <span>TIME</span>
        <span>COUNT</span>
        <span>DETAIL</span>
      </div>

      {violations.length === 0 ? (
        <p className={styles.empty}>No violations detected yet</p>
      ) : (
        [...violations].reverse().map((v) => (
          <ViolationRow key={v.id} violation={v} />
        ))
      )}
    </div>
  )
}
