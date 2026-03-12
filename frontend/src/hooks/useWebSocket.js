import { useState, useEffect, useRef } from 'react'

const WS_URL = 'ws://localhost:8000/ws'

/**
 * Maintains a WebSocket connection to the backend.
 * Auto-reconnects every 2s on disconnect.
 * Returns the latest parsed JSON payload and connection status.
 */
export function useWebSocket() {
  const [data, setData]           = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef                     = useRef(null)

  useEffect(() => {
    let cancelled = false

    const connect = () => {
      if (cancelled) return

      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        if (!cancelled) setConnected(true)
      }

      ws.onclose = () => {
        if (!cancelled) {
          setConnected(false)
          setTimeout(connect, 2000)
        }
      }

      ws.onerror = () => {
        ws.close()
      }

      ws.onmessage = (e) => {
        if (!cancelled) {
          try {
            setData(JSON.parse(e.data))
          } catch {
            // malformed frame — ignore
          }
        }
      }
    }

    connect()

    return () => {
      cancelled = true
      wsRef.current?.close()
    }
  }, [])

  return { data, connected }
}
