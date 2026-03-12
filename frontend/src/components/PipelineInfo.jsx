import React from 'react'
import styles from './PipelineInfo.module.css'

const STEPS = [
  { name: 'YOLOv8n',     desc: 'Detects people per frame (class 0)',      colorVar: '--accent-light' },
  { name: 'ByteTrack',   desc: 'Assigns persistent IDs across frames',     colorVar: '--blue' },
  { name: 'LineZone',    desc: 'Counts crossings on virtual tripwire',     colorVar: '--green' },
  { name: 'Window (3s)', desc: 'Groups IDs crossing within 3 sec window', colorVar: '--orange' },
  { name: 'Flag',        desc: 'Count ≥ 2 after 1 swipe = violation',     colorVar: '--red' },
]

export default function PipelineInfo({ status }) {
  return (
    <div className={styles.container}>
      <p className={styles.title}>PIPELINE</p>
      {STEPS.map(({ name, desc, colorVar }) => (
        <div key={name} className={styles.step}>
          <span className={styles.name} style={{ color: `var(${colorVar})` }}>{name}</span>
          <span className={styles.desc}>{desc}</span>
        </div>
      ))}

      {status === 'done' && (
        <div className={styles.doneNotice}>
          ✅ Processing complete. Annotated video saved as{' '}
          <strong>annotated_output.mp4</strong> next to your input file.
        </div>
      )}
    </div>
  )
}
