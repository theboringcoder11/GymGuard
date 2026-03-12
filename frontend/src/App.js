import { useState, useEffect, useRef } from "react";

const WS_URL = "ws://localhost:8000/ws";
const API_URL = "http://localhost:8000";

function useWebSocket(url) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        setTimeout(connect, 2000); // auto-reconnect
      };
      ws.onmessage = (e) => {
        try { setData(JSON.parse(e.data)); } catch {}
      };
    };
    connect();
    return () => wsRef.current?.close();
  }, [url]);

  return { data, connected };
}

function StatBox({ label, value, sub, color = "#e2e8f0" }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.03)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 10,
      padding: "14px 18px",
    }}>
      <div style={{ fontSize: 9, color: "#475569", letterSpacing: 2, marginBottom: 6, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1, fontFamily: "'JetBrains Mono', monospace" }}>{value ?? "—"}</div>
      {sub && <div style={{ fontSize: 10, color: "#334155", marginTop: 5 }}>{sub}</div>}
    </div>
  );
}

function ViolationRow({ v, fps }) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "60px 80px 60px 1fr",
      gap: 12,
      padding: "9px 14px",
      borderBottom: "1px solid rgba(255,255,255,0.04)",
      fontSize: 11,
      alignItems: "center",
      animation: "fadeIn 0.3s ease",
    }}>
      <span style={{ color: "#ef4444", fontWeight: 700 }}>#{v.id}</span>
      <span style={{ color: "#94a3b8" }}>{v.timestamp}s</span>
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 28, height: 28, borderRadius: "50%",
        background: "rgba(239,68,68,0.15)",
        color: "#ef4444", fontWeight: 700, fontSize: 13,
      }}>{v.people}</span>
      <span style={{ color: "#ef4444", fontSize: 10, fontWeight: 600 }}>
        TAILGATE — {v.people} people / 1 swipe
      </span>
    </div>
  );
}

export default function App() {
  const { data, connected } = useWebSocket(WS_URL);
  const [videoPath, setVideoPath] = useState("");
  const [lineRatio, setLineRatio] = useState(0.65);
  const [started, setStarted] = useState(false);

  const status       = data?.status ?? "idle";
  const progress     = data?.total_frames ? (data.frame_count / data.total_frames) * 100 : 0;
  const violations   = data?.violations ?? [];
  const peopleNow    = data?.people_in_frame ?? 0;
  const isViolation  = peopleNow > 1 && status === "processing";

  const handleStart = async () => {
    if (!videoPath.trim()) return;
    await fetch(`${API_URL}/start?video_path=${encodeURIComponent(videoPath)}&line_ratio=${lineRatio}`, {
      method: "POST",
    });
    setStarted(true);
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#07090f",
      color: "#dde3ef",
      fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      padding: 24,
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Orbitron:wght@800&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #07090f; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        input[type=range] { accent-color: #7c3aed; }
        input[type=text] {
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 6px;
          color: #e2e8f0;
          font-family: inherit;
          font-size: 12px;
          padding: 9px 12px;
          outline: none;
          width: 100%;
        }
        input[type=text]:focus { border-color: #7c3aed; }
        button {
          font-family: inherit;
          cursor: pointer;
          border: none;
          transition: all 0.15s;
        }
        button:hover { opacity: 0.85; }
      `}</style>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 22, fontWeight: 800, letterSpacing: 2 }}>
            GYMGUARD <span style={{ color: "#7c3aed" }}>CV</span>
          </div>
          <div style={{ fontSize: 10, color: "#475569", letterSpacing: 2, marginTop: 3 }}>
            TAILGATE DETECTION · YOLOv8 + BYTETRACK · LOCAL INFERENCE
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: connected ? "#22c55e" : "#ef4444",
            boxShadow: connected ? "0 0 8px #22c55e" : "none",
            animation: connected ? "none" : "pulse 1.5s infinite",
          }} />
          <span style={{ fontSize: 10, color: connected ? "#22c55e" : "#ef4444" }}>
            {connected ? "BACKEND CONNECTED" : "CONNECTING..."}
          </span>
        </div>
      </div>

      {/* Config panel (shown before start) */}
      {!started && (
        <div style={{
          background: "rgba(255,255,255,0.02)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12,
          padding: 24,
          marginBottom: 24,
          maxWidth: 600,
        }}>
          <div style={{ fontSize: 10, color: "#475569", letterSpacing: 2, marginBottom: 16 }}>CONFIGURE DETECTION</div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 6 }}>
              VIDEO FILE PATH
            </label>
            <input
              type="text"
              value={videoPath}
              onChange={(e) => setVideoPath(e.target.value)}
              placeholder="/absolute/path/to/your/video.mp4"
            />
            <div style={{ fontSize: 9, color: "#334155", marginTop: 4 }}>
              Use an absolute path. Stock footage of people walking through a door works best.
            </div>
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 6 }}>
              COUNTING LINE POSITION — {Math.round(lineRatio * 100)}% down the frame
            </label>
            <input
              type="range" min={0.3} max={0.9} step={0.05}
              value={lineRatio}
              onChange={(e) => setLineRatio(parseFloat(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={{ fontSize: 9, color: "#334155", marginTop: 4 }}>
              Drag to position the virtual tripwire. Aim for just inside the doorway.
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={!videoPath.trim() || !connected}
            style={{
              background: videoPath.trim() && connected ? "#7c3aed" : "rgba(255,255,255,0.05)",
              color: videoPath.trim() && connected ? "#fff" : "#334155",
              padding: "10px 24px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: 1,
            }}
          >
            ▶ START DETECTION
          </button>
        </div>
      )}

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 20 }}>
        <StatBox
          label="Status"
          value={status.toUpperCase()}
          color={status === "processing" ? "#f97316" : status === "done" ? "#22c55e" : "#64748b"}
        />
        <StatBox
          label="Progress"
          value={`${Math.round(progress)}%`}
          sub={`${data?.frame_count ?? 0} / ${data?.total_frames ?? 0} frames`}
          color="#60a5fa"
        />
        <StatBox
          label="People Now"
          value={peopleNow}
          sub="in current frame"
          color={peopleNow > 1 ? "#ef4444" : "#22c55e"}
        />
        <StatBox
          label="Total Entries"
          value={data?.total_entries ?? 0}
          sub="line crossings"
          color="#a78bfa"
        />
        <StatBox
          label="Violations"
          value={violations.length}
          sub="tailgate events"
          color={violations.length > 0 ? "#ef4444" : "#22c55e"}
        />
      </div>

      {/* Progress bar */}
      {started && (
        <div style={{ height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, marginBottom: 20, overflow: "hidden" }}>
          <div style={{
            height: "100%",
            width: `${progress}%`,
            background: "linear-gradient(90deg, #7c3aed, #a78bfa)",
            borderRadius: 2,
            transition: "width 0.2s",
          }} />
        </div>
      )}

      {/* Main content */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 16 }}>

        {/* Live video feed */}
        <div style={{
          background: "#000",
          borderRadius: 12,
          overflow: "hidden",
          border: `1px solid ${isViolation ? "rgba(239,68,68,0.5)" : "rgba(255,255,255,0.08)"}`,
          position: "relative",
          minHeight: 360,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "border-color 0.3s",
        }}>
          {data?.frame_b64 ? (
            <img
              src={`data:image/jpeg;base64,${data.frame_b64}`}
              alt="Live detection feed"
              style={{ width: "100%", height: "auto", display: "block" }}
            />
          ) : (
            <div style={{ textAlign: "center", color: "#334155" }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📷</div>
              <div style={{ fontSize: 12 }}>
                {connected ? (started ? "Waiting for frames..." : "Configure and start detection above") : "Connecting to backend..."}
              </div>
              {started && !connected && (
                <div style={{ fontSize: 10, color: "#ef4444", marginTop: 8 }}>
                  Make sure backend is running: python detector.py --video your_video.mp4
                </div>
              )}
            </div>
          )}

          {/* Violation flash banner */}
          {isViolation && (
            <div style={{
              position: "absolute",
              bottom: 0, left: 0, right: 0,
              background: "rgba(239,68,68,0.9)",
              color: "#fff",
              padding: "10px 16px",
              fontWeight: 700,
              fontSize: 13,
              letterSpacing: 1,
              textAlign: "center",
              animation: "fadeIn 0.2s ease",
            }}>
              ⚠ TAILGATE DETECTED — {peopleNow} PEOPLE / 1 SWIPE
            </div>
          )}

          {/* Frame counter overlay */}
          {data?.frame_b64 && (
            <div style={{
              position: "absolute",
              top: 10, right: 10,
              background: "rgba(0,0,0,0.65)",
              color: "#a78bfa",
              padding: "4px 8px",
              borderRadius: 4,
              fontSize: 10,
              fontWeight: 700,
            }}>
              YOLOv8n LIVE
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

          {/* Violation log */}
          <div style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 12,
            overflow: "hidden",
            flex: 1,
          }}>
            <div style={{
              padding: "12px 14px",
              borderBottom: "1px solid rgba(255,255,255,0.06)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}>
              <span style={{ fontSize: 10, color: "#475569", letterSpacing: 2 }}>VIOLATION LOG</span>
              {violations.length > 0 && (
                <span style={{
                  background: "rgba(239,68,68,0.15)",
                  color: "#ef4444",
                  padding: "2px 8px",
                  borderRadius: 4,
                  fontSize: 10,
                  fontWeight: 700,
                }}>
                  {violations.length} FLAGGED
                </span>
              )}
            </div>

            {/* Column headers */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "60px 80px 60px 1fr",
              gap: 12,
              padding: "7px 14px",
              fontSize: 9,
              color: "#334155",
              letterSpacing: 1.5,
              borderBottom: "1px solid rgba(255,255,255,0.04)",
            }}>
              <span>EVENT</span>
              <span>TIME</span>
              <span>COUNT</span>
              <span>DETAIL</span>
            </div>

            {violations.length === 0 ? (
              <div style={{ padding: 24, textAlign: "center", color: "#334155", fontSize: 11 }}>
                No violations detected yet
              </div>
            ) : (
              [...violations].reverse().map((v) => (
                <ViolationRow key={v.id} v={v} fps={data?.fps} />
              ))
            )}
          </div>

          {/* How it works */}
          <div style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 12,
            padding: 16,
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: 2, marginBottom: 12 }}>PIPELINE</div>
            {[
              ["YOLOv8n",     "Detects people per frame (class 0)",       "#a78bfa"],
              ["ByteTrack",   "Assigns persistent IDs across frames",      "#60a5fa"],
              ["LineZone",    "Counts crossings on virtual tripwire",      "#34d399"],
              ["Window (3s)", "Groups IDs crossing within 3 sec window",  "#f97316"],
              ["Flag",        "Count ≥ 2 after 1 swipe = violation",      "#ef4444"],
            ].map(([name, desc, color]) => (
              <div key={name} style={{ display: "flex", gap: 10, marginBottom: 8, alignItems: "flex-start" }}>
                <span style={{ color, fontWeight: 700, fontSize: 10, minWidth: 80 }}>{name}</span>
                <span style={{ color: "#475569", fontSize: 10, lineHeight: 1.4 }}>{desc}</span>
              </div>
            ))}
          </div>

          {/* Done state */}
          {status === "done" && (
            <div style={{
              background: "rgba(34,197,94,0.08)",
              border: "1px solid rgba(34,197,94,0.25)",
              borderRadius: 10,
              padding: 14,
              fontSize: 11,
              color: "#22c55e",
            }}>
              ✅ Processing complete. Annotated video saved as <strong>annotated_output.mp4</strong> in the same folder as your input video.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
