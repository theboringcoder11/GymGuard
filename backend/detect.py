"""
GymGuard - Tailgate Detector Backend (count-based CRM reconciliation)
====================================================================

Improvement over original:
- Instead of comparing entrants to a local swipe queue window,
  compare total detected entries vs total authorized swipes from a CRM.
- CRM is mocked with REST endpoints for now, but the detector reads
  from a function boundary that can later be replaced by a real API call.

Run with:
    python gymguard_improved.py

Then:
    POST /start?video_path=/path/to/video.mp4
    POST /mock-crm/swipes/{session_id}   body: {"member_id":"M-0001","quantity":1}
"""

import argparse
import asyncio
import base64
import json
import time
import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from database import (
    init_db, create_session, close_session,
    save_entry, save_violation
)

# ── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="GymGuard API")

@app.on_event("startup")
def startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mock CRM store ────────────────────────────────────────────────────────────
# Replace this later with a real CRM/access-control integration.

mock_crm_store = {
    # session_id: {
    #   "authorized_swipes": int,
    #   "events": [{"member_id": "...", "quantity": 1, "timestamp": ...}]
    # }
}
crm_lock = threading.Lock()


def crm_get_authorized_swipes(session_id: Optional[str]) -> int:
    """Boundary function for retrieving total successful swipes from CRM."""
    if not session_id:
        return 0
    with crm_lock:
        return int(mock_crm_store.get(session_id, {}).get("authorized_swipes", 0))


def crm_record_swipe(session_id: str, member_id: str, quantity: int = 1):
    """Mock CRM write for testing."""
    with crm_lock:
        bucket = mock_crm_store.setdefault(session_id, {
            "authorized_swipes": 0,
            "events": []
        })
        bucket["authorized_swipes"] += quantity
        bucket["events"].append({
            "member_id": member_id,
            "quantity": quantity,
            "timestamp": time.time(),
        })
        return bucket


# ── Global state ──────────────────────────────────────────────────────────────

state = {
    "running": False,
    "frame_count": 0,
    "total_frames": 0,
    "fps": 0,
    "people_in_frame": 0,
    "total_entries": 0,           # computer vision detected entries
    "authorized_swipes": 0,       # CRM-reported total successful swipes
    "unauthorized_entries": 0,    # max(0, total_entries - authorized_swipes)
    "violations": [],
    "latest_frame_b64": None,
    "video_path": None,
    "status": "idle",             # idle | starting | processing | done | error
    "error": None,
    "session_id": None,
    "output_path": None,
    "reconciliation": {
        "entries": 0,
        "swipes": 0,
        "overflow": 0,
        "last_reconciled_frame": 0,
    },
}
connected_clients: list[WebSocket] = []
state_lock = threading.Lock()


# ── Detector Core ─────────────────────────────────────────────────────────────

def run_detection(
    video_path: str,
    line_ratio: float = 0.65,
    conf: float = 0.40,
    flip_line: bool = False,
    crm_grace_seconds: float = 3.0,
):
    """
    Count people entering the gym and reconcile against total authorized swipes
    from CRM. If detected entries exceed authorized swipes after a grace period,
    record a violation.

    Why this is better:
    - More robust than tying each entry to a local swipe queue
    - Easier to integrate with real access-control/CRM systems
    - Still preserves CV/video evidence for review
    """
    model = YOLO("yolov8n.pt")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        with state_lock:
            state["status"] = "error"
            state["error"] = f"Could not open video: {video_path}"
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    line_y = int(height * line_ratio)
    if flip_line:
        line_start = sv.Point(width, line_y)
        line_end = sv.Point(0, line_y)
    else:
        line_start = sv.Point(0, line_y)
        line_end = sv.Point(width, line_y)

    line_zone = sv.LineZone(start=line_start, end=line_end)

    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_scale=0.5, text_thickness=1)
    line_annotator = sv.LineZoneAnnotator(thickness=2, text_thickness=1, text_scale=0.5)
    tracker = sv.ByteTrack()

    out_path = str(Path(video_path).parent / "annotated_output.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    violations = []
    frame_idx = 0

    # Grace-period logic:
    # If entries exceed swipes, wait a few seconds before flagging, because
    # the CRM swipe could arrive slightly later than the visible crossing.
    mismatch_started_frame = None
    last_recorded_overflow = 0

    session_id = create_session(video_path, line_ratio)

    with state_lock:
        state["running"] = True
        state["status"] = "processing"
        state["total_frames"] = total_frames
        state["fps"] = fps
        state["video_path"] = video_path
        state["session_id"] = session_id
        state["authorized_swipes"] = 0
        state["unauthorized_entries"] = 0
        state["reconciliation"] = {
            "entries": 0,
            "swipes": 0,
            "overflow": 0,
            "last_reconciled_frame": 0,
        }

    t_start = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # ── Detect people ─────────────────────────────────────────────────────
        results = model(frame, classes=[0], conf=conf, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)
        detections = tracker.update_with_detections(detections)

        crossed_in, crossed_out = line_zone.trigger(detections=detections)

        if detections.tracker_id is not None:
            for did_enter, tracker_id, conf_val in zip(
                crossed_in, detections.tracker_id, detections.confidence
            ):
                if did_enter:
                    save_entry(
                        session_id=session_id,
                        tracker_id=int(tracker_id),
                        frame=frame_idx,
                        timestamp=round(frame_idx / fps, 2),
                        confidence=float(conf_val),
                    )

        total_entries = int(line_zone.in_count)
        authorized_swipes = crm_get_authorized_swipes(session_id)
        overflow = max(0, total_entries - authorized_swipes)

        grace_frames = int(fps * crm_grace_seconds)

        if overflow > 0:
            if mismatch_started_frame is None:
                mismatch_started_frame = frame_idx
        else:
            mismatch_started_frame = None
            last_recorded_overflow = 0

        should_fire_violation = (
            overflow > 0
            and mismatch_started_frame is not None
            and (frame_idx - mismatch_started_frame) >= grace_frames
            and overflow > last_recorded_overflow
        )

        if should_fire_violation:
            violation = {
                "id": len(violations) + 1,
                "frame": frame_idx,
                "timestamp": round(frame_idx / fps, 2),
                "people": total_entries,
                "authorized_swipes": authorized_swipes,
                "overflow": overflow,
                "confidence": float(np.mean(detections.confidence)) if len(detections) else 0,
                "reason": "detected_entries_exceed_authorized_swipes",
            }
            violations.append(violation)

            save_violation(
                session_id=session_id,
                frame=frame_idx,
                timestamp=round(frame_idx / fps, 2),
                people=overflow,  # number of suspected unauthorized entries
            )
            last_recorded_overflow = overflow

        # ── Annotate frame ────────────────────────────────────────────────────
        annotated = frame.copy()

        if len(detections) > 0:
            labels = [
                f"person {c:.0%} #{tid}"
                for c, tid in zip(
                    detections.confidence,
                    detections.tracker_id if detections.tracker_id is not None else range(len(detections))
                )
            ]
            annotated = box_annotator.annotate(scene=annotated, detections=detections)
            annotated = label_annotator.annotate(scene=annotated, detections=detections, labels=labels)

        annotated = line_annotator.annotate(annotated, line_counter=line_zone)

        if overflow > 0:
            overlay = annotated.copy()
            cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 220), -1)
            cv2.addWeighted(overlay, 0.10, annotated, 0.90, 0, annotated)
            cv2.putText(
                annotated,
                f"ENTRY/SWIPE MISMATCH  entries={total_entries} swipes={authorized_swipes} overflow={overflow}",
                (20, height - 30),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, (50, 50, 255), 2
            )

        elapsed = time.time() - t_start
        processing_fps = frame_idx / elapsed if elapsed > 0 else 0

        cv2.rectangle(annotated, (0, 0), (520, 46), (0, 0, 0), -1)
        cv2.putText(
            annotated,
            f"GymGuard CV | frame {frame_idx}/{total_frames} | {processing_fps:.1f} fps",
            (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1
        )
        cv2.putText(
            annotated,
            f"entries={total_entries} | swipes={authorized_swipes} | overflow={overflow}",
            (8, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
            (80, 220, 80) if overflow == 0 else (0, 80, 255), 1
        )

        writer.write(annotated)

        frame_b64 = None
        if frame_idx % 3 == 0:
            _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buf).decode("utf-8")

        with state_lock:
            state["frame_count"] = frame_idx
            state["people_in_frame"] = len(detections)
            state["violations"] = violations
            state["total_entries"] = total_entries
            state["authorized_swipes"] = authorized_swipes
            state["unauthorized_entries"] = overflow
            state["reconciliation"] = {
                "entries": total_entries,
                "swipes": authorized_swipes,
                "overflow": overflow,
                "last_reconciled_frame": frame_idx,
            }
            if frame_b64:
                state["latest_frame_b64"] = frame_b64

    cap.release()
    writer.release()

    close_session(session_id, total_frames, fps, status="done")

    with state_lock:
        state["running"] = False
        state["status"] = "done"
        state["output_path"] = out_path

    print(f"\n✅ Done. Annotated video saved to: {out_path}")
    print(f"   Session ID:           {session_id}")
    print(f"   Total entries (CV):   {line_zone.in_count}")
    print(f"   Authorized swipes:    {crm_get_authorized_swipes(session_id)}")
    print(f"   Violations detected:  {len(violations)}")


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            with state_lock:
                payload = {
                    "running": state["running"],
                    "status": state["status"],
                    "frame_count": state["frame_count"],
                    "total_frames": state["total_frames"],
                    "fps": state["fps"],
                    "people_in_frame": state["people_in_frame"],
                    "total_entries": state["total_entries"],
                    "authorized_swipes": state["authorized_swipes"],
                    "unauthorized_entries": state["unauthorized_entries"],
                    "violations": state["violations"],
                    "frame_b64": state["latest_frame_b64"],
                    "error": state["error"],
                    "session_id": state["session_id"],
                    "reconciliation": state["reconciliation"],
                    "output_path": state["output_path"],
                }
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        if ws in connected_clients:
            connected_clients.remove(ws)


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/status")
def get_status():
    with state_lock:
        return {k: v for k, v in state.items() if k != "latest_frame_b64"}


@app.post("/reset")
def reset():
    if state["running"]:
        return {"error": "Detection still running — wait for it to finish first"}
    with state_lock:
        state["frame_count"] = 0
        state["total_frames"] = 0
        state["fps"] = 0
        state["people_in_frame"] = 0
        state["total_entries"] = 0
        state["authorized_swipes"] = 0
        state["unauthorized_entries"] = 0
        state["violations"] = []
        state["latest_frame_b64"] = None
        state["video_path"] = None
        state["status"] = "idle"
        state["error"] = None
        state["session_id"] = None
        state["output_path"] = None
        state["reconciliation"] = {
            "entries": 0,
            "swipes": 0,
            "overflow": 0,
            "last_reconciled_frame": 0,
        }
    return {"message": "State reset — ready for a new video"}


@app.post("/start")
def start_detection(
    video_path: str,
    line_ratio: float = 0.65,
    conf: float = 0.40,
    flip_line: bool = False,
    crm_grace_seconds: float = 3.0,
):
    if state["running"]:
        return {"error": "Detection already running"}

    with state_lock:
        state["frame_count"] = 0
        state["violations"] = []
        state["total_entries"] = 0
        state["authorized_swipes"] = 0
        state["unauthorized_entries"] = 0
        state["status"] = "starting"
        state["error"] = None
        state["latest_frame_b64"] = None
        state["output_path"] = None

    t = threading.Thread(
        target=run_detection,
        args=(video_path, line_ratio, conf, flip_line, crm_grace_seconds),
        daemon=True
    )
    t.start()
    return {
        "message": "Detection started",
        "video": video_path,
        "crm_grace_seconds": crm_grace_seconds,
    }


# ── Mock CRM endpoints ────────────────────────────────────────────────────────

@app.post("/mock-crm/swipes/{session_id}")
def mock_add_swipe(
    session_id: str,
    body: dict = Body(default={})
):
    member_id = body.get("member_id", "M-SIM")
    quantity = int(body.get("quantity", 1))
    if quantity < 1:
        return {"error": "quantity must be >= 1"}

    bucket = crm_record_swipe(session_id, member_id, quantity)

    with state_lock:
        if state["session_id"] == session_id:
            state["authorized_swipes"] = bucket["authorized_swipes"]
            state["unauthorized_entries"] = max(
                0,
                state["total_entries"] - bucket["authorized_swipes"]
            )

    return {
        "message": "Mock CRM swipe recorded",
        "session_id": session_id,
        "member_id": member_id,
        "quantity": quantity,
        "authorized_swipes": bucket["authorized_swipes"],
        "events": bucket["events"],
    }


@app.get("/mock-crm/swipes/count")
def mock_swipe_count(session_id: str):
    return {
        "session_id": session_id,
        "authorized_swipes": crm_get_authorized_swipes(session_id),
    }


@app.get("/mock-crm/swipes/events")
def mock_swipe_events(session_id: str):
    with crm_lock:
        bucket = mock_crm_store.get(session_id, {"authorized_swipes": 0, "events": []})
        return {
            "session_id": session_id,
            "authorized_swipes": bucket["authorized_swipes"],
            "events": bucket["events"],
        }


# ── History endpoints ────────────────────────────────────────────────────────

@app.get("/history/sessions")
def list_sessions():
    from database import get_all_sessions
    return get_all_sessions()


@app.get("/history/sessions/{session_id}")
def get_session_detail(session_id: str):
    from database import get_session, get_entries, get_violations
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    entries = get_entries(session_id)
    violations = get_violations(session_id)
    return {
        "session": session,
        "entries": entries,
        "violations": violations,
        "crm_authorized_swipes": crm_get_authorized_swipes(session_id),
    }


@app.get("/history/violations")
def list_all_violations():
    from database import get_all_violations
    return get_all_violations()


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GymGuard Tailgate Detector (CRM reconciliation)")
    parser.add_argument("--video", required=False, default=None, help="Path to input video file")
    parser.add_argument("--line", type=float, default=0.65, help="Counting line position (0.0-1.0)")
    parser.add_argument("--conf", type=float, default=0.40, help="Detection confidence threshold")
    parser.add_argument("--flip-line", action="store_true", help="Flip in/out direction")
    parser.add_argument("--crm-grace-seconds", type=float, default=3.0, help="Delay before mismatch becomes violation")
    parser.add_argument("--no-server", action="store_true", help="Run detection only, no web server (requires --video)")
    args = parser.parse_args()

    if args.no_server:
        if not args.video:
            print("Error: --video is required when using --no-server")
            exit(1)
        run_detection(args.video, args.line, args.conf, args.flip_line, args.crm_grace_seconds)
    else:
        if args.video:
            t = threading.Thread(
                target=run_detection,
                args=(args.video, args.line, args.conf, args.flip_line, args.crm_grace_seconds),
                daemon=True
            )
            t.start()
            print(f"🎥 Processing: {args.video}")
        else:
            print("⏳ Server started in idle mode")
            print("   POST to /start?video_path=... to begin detection")

        print("🌐 Dashboard API: http://localhost:8000")
        print("📡 WebSocket:     ws://localhost:8000/ws")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")