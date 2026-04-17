import React from 'react'
import styles from './ConfigPanel.module.css'

export default function ConfigPanel({ videoPath, setVideoPath, lineRatio, setLineRatio, onStart, connected }) {
  const canStart = videoPath.trim().length > 0 && connected

  return (
    <section className={styles.panel}>
      
    </section>
  )
}
