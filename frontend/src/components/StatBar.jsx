import React from 'react'
import styles from './StatBar.module.css'

function StatBox({ label, value, sub, colorVar }) {
  return (
    <div className={styles.box}>
      <p className={styles.label}>{label}</p>
      <p className={styles.value} style={{ color: `var(${colorVar})` }}>
        {value ?? '—'}
      </p>
      {sub && <p className={styles.sub}>{sub}</p>}
    </div>
  )
}

export default function StatBar({ status, progress, frameCount, totalFrames, peopleNow, totalEntries, violationCount }) {
  const statusColor =
    status === 'processing' ? '--orange' :
    status === 'done'       ? '--green'  : '--text-muted'

  return (
    <div className={styles.grid}>
      <StatBox
        label="STATUS"
        value={status.toUpperCase()}
        colorVar={statusColor}
      />
      <StatBox
        label="PROGRESS"
        value={`${Math.round(progress)}%`}
        sub={`${frameCount} / ${totalFrames} frames`}
        colorVar="--blue"
      />
      <StatBox
        label="PEOPLE NOW"
        value={peopleNow}
        sub="in current frame"
        colorVar={peopleNow > 1 ? '--red' : '--green'}
      />
      <StatBox
        label="TOTAL ENTRIES"
        value={totalEntries}
        sub="line crossings"
        colorVar="--accent-light"
      />
      <StatBox
        label="VIOLATIONS"
        value={violationCount}
        sub="tailgate events"
        colorVar={violationCount > 0 ? '--red' : '--green'}
      />
    </div>
  )
}
