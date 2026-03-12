import React, { useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket.js'
import Header       from './components/Header.jsx'
import ConfigPanel  from './components/ConfigPanel.jsx'
import StatBar      from './components/StatBar.jsx'
import ProgressBar  from './components/ProgressBar.jsx'
import VideoFeed    from './components/VideoFeed.jsx'
import ViolationLog from './components/ViolationLog.jsx'
import PipelineInfo from './components/PipelineInfo.jsx'
import styles from './App.module.css'

const API_URL = 'http://localhost:8000'

export default function App() {
  const { data, connected } = useWebSocket()

  const [videoPath, setVideoPath] = useState('')
  const [lineRatio, setLineRatio] = useState(0.65)
  const [started,   setStarted]   = useState(false)

  // Derived state from WebSocket payload
  const status        = data?.status         ?? 'idle'
  const frameCount    = data?.frame_count    ?? 0
  const totalFrames   = data?.total_frames   ?? 0
  const peopleNow     = data?.people_in_frame ?? 0
  const totalEntries  = data?.total_entries  ?? 0
  const violations    = data?.violations     ?? []
  const frameB64      = data?.frame_b64      ?? null
  const progress      = totalFrames > 0 ? (frameCount / totalFrames) * 100 : 0
  const isViolation   = peopleNow > 1 && status === 'processing'

  const handleStart = async () => {
    if (!videoPath.trim() || !connected) return
    await fetch(
      `${API_URL}/start?video_path=${encodeURIComponent(videoPath)}&line_ratio=${lineRatio}`,
      { method: 'POST' }
    )
    setStarted(true)
  }

  return (
    <div className={styles.page}>
      <Header connected={connected} />

      {!started && (
        <ConfigPanel
          videoPath={videoPath}
          setVideoPath={setVideoPath}
          lineRatio={lineRatio}
          setLineRatio={setLineRatio}
          onStart={handleStart}
          connected={connected}
        />
      )}

      <StatBar
        status={status}
        progress={progress}
        frameCount={frameCount}
        totalFrames={totalFrames}
        peopleNow={peopleNow}
        totalEntries={totalEntries}
        violationCount={violations.length}
      />

      {started && <ProgressBar progress={progress} />}

      <div className={styles.main}>
        <VideoFeed
          frameB64={frameB64}
          isViolation={isViolation}
          peopleNow={peopleNow}
          connected={connected}
          started={started}
        />

        <div className={styles.sidebar}>
          <ViolationLog violations={violations} />
          <PipelineInfo status={status} />
        </div>
      </div>
    </div>
  )
}
