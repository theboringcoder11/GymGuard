"""
GymGuard - Tailgate Detector Backend
=====================================
Processes a video file with YOLOv8, counts people crossing an entry line,
and streams real-time results to the React dashboard via WebSocket.

Run with:
    python detector.py --video path/to/your/video.mp4
"""

import argparse
import asyncio
import base64
import json
import time
import threading
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="GymGuard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global state shared between detector thread and websocket ─────────────────

state = {
    "running": False,
    "frame_count": 0,
    "total_frames": 0,
    "fps": 0,
    "people_in_frame": 0,
    "total_entries": 0,
    "violations": [],
    "latest_frame_b64": None,
    "video_path": None,
    "status": "idle",   # idle | processing | done | error
    "error": None,
}
connected_clients: list[WebSocket] = []
state_lock = threading.Lock()


# ── Detector Core ─────────────────────────────────────────────────────────────

def run_detection(video_path: str, line_ratio: float = 0.65, conf: float = 0.40):
    """
    Runs in a background thread. Processes each frame, annotates it,
    and updates global `state` which is broadcast to WebSocket clients.
    """
    model = YOLO("yolov8n.pt")  # downloads automatically on first run (~6MB)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        with state_lock:
            state["status"] = "error"
            state["error"] = f"Could not open video: {video_path}"
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Counting line: horizontal line across the frame at line_ratio height
    line_y = int(height * line_ratio)
    line_start = sv.Point(0, line_y)
    line_end   = sv.Point(width, line_y)
    line_zone  = sv.LineZone(start=line_start, end=line_end)

    # Supervision annotators
    box_annotator   = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_scale=0.5, text_thickness=1)
    line_annotator  = sv.LineZoneAnnotator(thickness=2, text_thickness=1, text_scale=0.5)
    tracker         = sv.ByteTrack()

    # Output video writer
    out_path = str(Path(video_path).parent / "annotated_output.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    violations = []
    frame_idx  = 0
    entry_window = {}   # tracker_id -> frame when they crossed the line
    swipe_simulated_at = int(total_frames * 0.05)  # simulated member swipe event

    with state_lock:
        state["running"]      = True
        state["status"]       = "processing"
        state["total_frames"] = total_frames
        state["fps"]          = fps
        state["video_path"]   = video_path

    t_start = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # Run YOLOv8 — person class only
        results = model(frame, classes=[0], conf=conf, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)

        # Track across frames (assigns persistent IDs)
        detections = tracker.update_with_detections(detections)

        # Count people crossing the line
        crossed_in, crossed_out = line_zone.trigger(detections=detections)

        # Check for tailgate: if more than 1 unique ID crossed since last swipe
        ids_crossed = set()
        for i, (did_cross, tracker_id) in enumerate(
            zip(crossed_in, detections.tracker_id if detections.tracker_id is not None else [])
        ):
            if did_cross:
                ids_crossed.add(tracker_id)

        if len(ids_crossed) > 0:
            for tid in ids_crossed:
                entry_window[tid] = frame_idx

        # Window: count unique IDs that crossed within last 3 seconds
        window_frames = int(fps * 3)
        recent_ids = {
            tid for tid, f in entry_window.items()
            if frame_idx - f <= window_frames
        }

        is_violation = (
            len(recent_ids) >= 2
            and frame_idx > swipe_simulated_at
        )

        if is_violation and (not violations or frame_idx - violations[-1]["frame"] > fps * 2):
            violation = {
                "id":         len(violations) + 1,
                "frame":      frame_idx,
                "timestamp":  round(frame_idx / fps, 2),
                "people":     len(recent_ids),
                "member_id":  "M-SIM",   # replace with real access control lookup
                "confidence": float(np.mean(detections.confidence)) if len(detections) else 0,
            }
            violations.append(violation)

        # ── Annotate frame ──────────────────────────────────────────────────

        annotated = frame.copy()

        # Draw bounding boxes + labels
        if len(detections) > 0:
            labels = [
                f"person {conf_val:.0%} #{tid}"
                for conf_val, tid in zip(
                    detections.confidence,
                    detections.tracker_id if detections.tracker_id is not None else range(len(detections))
                )
            ]
            annotated = box_annotator.annotate(scene=annotated, detections=detections)
            annotated = label_annotator.annotate(scene=annotated, detections=detections, labels=labels)

        # Draw counting line
        annotated = line_annotator.annotate(
            annotated, line_counter=line_zone
        )

        # Violation overlay
        if is_violation:
            overlay = annotated.copy()
            cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 220), -1)
            cv2.addWeighted(overlay, 0.12, annotated, 0.88, 0, annotated)
            cv2.putText(
                annotated,
                f"⚠ TAILGATE DETECTED — {len(recent_ids)} PEOPLE / 1 SWIPE",
                (20, height - 30),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, (50, 50, 255), 2
            )

        # HUD overlays
        elapsed = time.time() - t_start
        processing_fps = frame_idx / elapsed if elapsed > 0 else 0

        cv2.rectangle(annotated, (0, 0), (300, 28), (0, 0, 0), -1)
        cv2.putText(annotated, f"GymGuard CV  |  frame {frame_idx}/{total_frames}  |  {processing_fps:.1f} fps",
                    (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        cv2.rectangle(annotated, (0, height - 28), (200, height), (0, 0, 0), -1)
        cv2.putText(annotated, f"People in frame: {len(detections)}",
                    (8, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 80, 255) if len(detections) > 1 else (80, 220, 80), 1)

        writer.write(annotated)

        # Encode frame as JPEG → base64 for WebSocket streaming
        # Only send every 3rd frame to keep WS traffic reasonable
        frame_b64 = None
        if frame_idx % 3 == 0:
            _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buf).decode("utf-8")

        with state_lock:
            state["frame_count"]      = frame_idx
            state["people_in_frame"]  = len(detections)
            state["violations"]       = violations
            state["total_entries"]    = line_zone.in_count
            if frame_b64:
                state["latest_frame_b64"] = frame_b64

    cap.release()
    writer.release()

    with state_lock:
        state["running"] = False
        state["status"]  = "done"
        state["output_path"] = out_path

    print(f"\n✅ Done. Annotated video saved to: {out_path}")
    print(f"   Total violations detected: {len(violations)}")


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            # Push current state to client every 100ms
            with state_lock:
                payload = {
                    "running":         state["running"],
                    "status":          state["status"],
                    "frame_count":     state["frame_count"],
                    "total_frames":    state["total_frames"],
                    "fps":             state["fps"],
                    "people_in_frame": state["people_in_frame"],
                    "total_entries":   state["total_entries"],
                    "violations":      state["violations"],
                    "frame_b64":       state["latest_frame_b64"],
                    "error":           state["error"],
                }
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        connected_clients.remove(ws)


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/status")
def get_status():
    with state_lock:
        return {k: v for k, v in state.items() if k != "latest_frame_b64"}


@app.post("/start")
def start_detection(video_path: str, line_ratio: float = 0.65, conf: float = 0.40):
    if state["running"]:
        return {"error": "Detection already running"}
    # Reset state
    with state_lock:
        state["frame_count"]      = 0
        state["violations"]       = []
        state["total_entries"]    = 0
        state["status"]           = "starting"
        state["error"]            = None
        state["latest_frame_b64"] = None
    t = threading.Thread(
        target=run_detection,
        args=(video_path, line_ratio, conf),
        daemon=True
    )
    t.start()
    return {"message": "Detection started", "video": video_path}


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GymGuard Tailgate Detector")
    parser.add_argument("--video",      required=True,  help="Path to input video file")
    parser.add_argument("--line",       type=float, default=0.65, help="Counting line position (0.0-1.0)")
    parser.add_argument("--conf",       type=float, default=0.40, help="Detection confidence threshold")
    parser.add_argument("--no-server",  action="store_true",      help="Run detection only, no web server")
    args = parser.parse_args()

    if args.no_server:
        # Just process the video, no dashboard
        run_detection(args.video, args.line, args.conf)
    else:
        # Start detection in background, serve dashboard API
        t = threading.Thread(
            target=run_detection,
            args=(args.video, args.line, args.conf),
            daemon=True
        )
        t.start()
        print(f"🎥 Processing: {args.video}")
        print(f"🌐 Dashboard API: http://localhost:8000")
        print(f"📡 WebSocket:     ws://localhost:8000/ws")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
