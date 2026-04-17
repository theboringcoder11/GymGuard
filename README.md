# GymGuard CV — Local Tailgate Detection

Runs YOLOv8 on a stock video, counts people crossing a virtual tripwire,
and flags tailgate violations in a live React dashboard.

```
gymguard/
├── backend/
│   ├── detect.py        ← CV pipeline (YOLOv8 + ByteTrack + FastAPI + WebSocket)
│   └── requirements.txt
└── frontend/
    ├── src/App.js         ← React dashboard
    └── public/index.html
```

---

## 1. Backend Setup

```bash
cd backend

# Install dependencies (Python 3.9+)
pip install -r requirements.txt

# Run on your stock video
python detect.py --video /path/to/your/video.mp4
```

YOLOv8n weights (~6MB) download automatically on first run.

**Optional flags:**
```bash
# Adjust the counting line height (default 0.65 = 65% down the frame)
python detect.py --video video.mp4 --line 0.55

# Adjust detection confidence (default 0.40)
python detect.py --video video.mp4 --conf 0.35

# Process video only, no web server (faster)
python detect.py --video video.mp4 --no-server
```

The backend starts at **http://localhost:8000** and streams frames + events
over WebSocket at **ws://localhost:8000/ws**.

---

## 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dashboard
npm start
```

Open **http://localhost:3000** in your browser.

Enter the absolute path to your video file, set the line position, and hit Start.

---

## What to Expect

- The dashboard streams the annotated video feed live as the backend processes it
- Each frame shows YOLOv8 bounding boxes with tracker IDs and confidence scores
- A virtual counting line is drawn across the frame at your chosen height
- When 2+ people cross the line within a 3-second window, a violation is logged
- After processing, `annotated_output.mp4` is saved next to your input video

---

## Getting Good Stock Video

Best results with video that shows:
- A single door/entry point filmed from above or at an angle
- People walking through one at a time (or tailgating)
- Decent lighting and resolution (720p+)

Good free sources:
- **Pexels.com** → search "people walking door" or "gym entrance"
- **Pixabay.com** → search "entrance people"
- **Mixkit.co**   → search "people entering building"

---

## Tech Stack

| Component     | Library              |
|---------------|----------------------|
| Detection     | YOLOv8n (Ultralytics)|
| Tracking      | ByteTrack (Supervision) |
| Line counting | supervision LineZone |
| API           | FastAPI              |
| Streaming     | WebSocket            |
| Dashboard     | React 18             |

---

## Next Steps for Production

- Connect to real access control API (Brivo, Kisi, Salto) to get actual member swipe events
- Replace `M-SIM` member ID with real member lookup by timestamp
- Add alert system (email/SMS via Twilio when violation fires)
- Store violations to PostgreSQL with member photos
- Deploy backend to edge compute on-site (Raspberry Pi 5 or Jetson Nano)
