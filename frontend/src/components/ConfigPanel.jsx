import React from 'react'
import styles from './ConfigPanel.module.css'

export default function ConfigPanel({ videoPath, setVideoPath, lineRatio, setLineRatio, onStart, connected }) {
  const canStart = videoPath.trim().length > 0 && connected

  return (
    <section className={styles.panel}>
      <p className={styles.sectionLabel}>CONFIGURE DETECTION</p>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="video-path">
          VIDEO FILE PATH
        </label>
        <input
          id="video-path"
          className={styles.input}
          type="text"
          value={videoPath}
          onChange={(e) => setVideoPath(e.target.value)}
          placeholder="/absolute/path/to/your/video.mp4"
          spellCheck={false}
        />
        <p className={styles.hint}>
          Use an absolute path. Stock footage of people walking through a door works best.
        </p>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="line-ratio">
          COUNTING LINE POSITION — {Math.round(lineRatio * 100)}% down the frame
        </label>
        <input
          id="line-ratio"
          type="range"
          min={0.3}
          max={0.9}
          step={0.05}
          value={lineRatio}
          onChange={(e) => setLineRatio(parseFloat(e.target.value))}
        />
        <p className={styles.hint}>
          Drag to position the virtual tripwire. Aim for just inside the doorway.
        </p>
      </div>

      <button
        className={`${styles.startBtn} ${canStart ? styles.startBtnActive : styles.startBtnDisabled}`}
        onClick={onStart}
        disabled={!canStart}
      >
        ▶ START DETECTION
      </button>
    </section>
  )
}
