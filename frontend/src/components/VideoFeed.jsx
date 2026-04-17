import React from 'react'
import styles from './VideoFeed.module.css'

export default function VideoFeed({ frameB64, isViolation, peopleNow, connected, started }) {
  return (
    <div className={`${styles.container} ${isViolation ? styles.containerViolation : ''}`}>

      {frameB64 ? (
        <>
          <img
            className={styles.frame}
            src={`data:image/jpeg;base64,${frameB64}`}
            alt="Live YOLOv8 detection feed"
          />
          <div className={styles.badge}>YOLOv8n LIVE</div>
        </>
      ) : (
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>📷</span>
          <p className={styles.emptyText}>
            {!connected
              ? 'Connecting to backend...'
              : !started
              ? 'Configure and start detection above'
              : 'Waiting for first frame...'}
          </p>
          {started && !connected && (
            <p className={styles.emptyError}>
              Make sure backend is running: python detect.py --video your_video.mp4
            </p>
          )}
        </div>
      )}

      {isViolation && (
        <div className={styles.violationBanner}>
          ⚠ TAILGATE DETECTED — {peopleNow} PEOPLE / 1 SWIPE
        </div>
      )}
    </div>
  )
}
