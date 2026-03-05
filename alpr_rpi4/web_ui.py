"""
ALPR System — Flask Web Dashboard (RPi4)
=========================================
Provides a headless web interface for the RPi4 build.

Endpoints:
  GET  /               — HTML dashboard (last 10 plates, FPS, uptime)
  GET  /stream         — MJPEG live stream
  GET  /api/status     — JSON status snapshot
  GET  /api/history    — JSON array of last 100 detections
  POST /api/clear      — Clear detection history

State is shared via module-level variables (thread-safe deque + lock).
Call push_result(PlateResult) and push_frame(jpeg_bytes) from the pipeline thread.
"""

import time
import threading
from collections import deque
from typing import Optional

from flask import Flask, Response, jsonify, request

# ------------------------------------------------------------------
# Shared state (written by camera thread, read by Flask)
# ------------------------------------------------------------------

_lock = threading.Lock()
_history: deque = deque(maxlen=100)   # list of dicts
_latest_frame: Optional[bytes] = None # JPEG bytes
_start_time: float = time.time()
_total_detections: int = 0
_fps_counter: deque = deque(maxlen=20)  # timestamps of last 20 processed frames


def push_result(plate_result):
    """Called by the pipeline thread for every PlateResult."""
    global _total_detections
    with _lock:
        _total_detections += 1
        _fps_counter.append(time.time())
        _history.append({
            "plate": plate_result.plate_text,
            "color": plate_result.plate_color,
            "det_conf": round(plate_result.detection_confidence, 3),
            "ocr_conf": round(plate_result.ocr_confidence, 3),
            "timestamp": plate_result.timestamp,
            "time_str": time.strftime("%H:%M:%S", time.localtime(plate_result.timestamp)),
        })


def push_frame(jpeg_bytes: bytes):
    """Called by the pipeline thread with each annotated JPEG frame."""
    global _latest_frame
    with _lock:
        _latest_frame = jpeg_bytes


def _get_fps() -> float:
    with _lock:
        if len(_fps_counter) < 2:
            return 0.0
        elapsed = _fps_counter[-1] - _fps_counter[0]
        if elapsed <= 0:
            return 0.0
        return round((len(_fps_counter) - 1) / elapsed, 1)


# ------------------------------------------------------------------
# Flask application
# ------------------------------------------------------------------

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>ALPR — RPi4 Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f0f0f; color: #e0e0e0; }
  header { background: #1a1a2e; padding: 16px 24px; display: flex;
           align-items: center; gap: 16px; border-bottom: 2px solid #16213e; }
  header h1 { font-size: 1.4rem; color: #00d4ff; letter-spacing: 2px; }
  header span { font-size: 0.85rem; color: #888; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
          padding: 16px; max-width: 1200px; margin: 0 auto; }
  .card { background: #1a1a2e; border-radius: 8px; padding: 16px;
          border: 1px solid #16213e; }
  .card h2 { font-size: 0.9rem; color: #00d4ff; text-transform: uppercase;
             letter-spacing: 1px; margin-bottom: 12px; }
  .stats { display: flex; gap: 16px; flex-wrap: wrap; }
  .stat { background: #0f3460; border-radius: 6px; padding: 12px 20px;
          text-align: center; flex: 1; min-width: 100px; }
  .stat .val { font-size: 2rem; font-weight: bold; color: #00d4ff; }
  .stat .lbl { font-size: 0.75rem; color: #aaa; margin-top: 4px; }
  .stream { width: 100%; border-radius: 6px; border: 1px solid #16213e;
            background: #000; min-height: 240px; display: block; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { text-align: left; padding: 8px; color: #00d4ff; border-bottom: 1px solid #16213e; }
  td { padding: 8px; border-bottom: 1px solid #111; }
  tr:hover td { background: #16213e; }
  .plate-badge { background: #00d4ff; color: #000; font-weight: bold;
                 padding: 2px 8px; border-radius: 4px; font-size: 0.9rem; }
  .color-blue { color: #4fa3e0; } .color-yellow { color: #f0c040; }
  .color-unknown { color: #888; }
  .btn-clear { background: #c0392b; color: #fff; border: none; padding: 8px 16px;
               border-radius: 4px; cursor: pointer; font-size: 0.8rem; float: right; }
  .btn-clear:hover { background: #e74c3c; }
  @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>ALPR</h1>
  <span>Raspberry Pi 4 — License Plate Recognition</span>
</header>
<div class="grid">
  <div class="card" style="grid-column: 1 / -1;">
    <h2>Status</h2>
    <div class="stats">
      <div class="stat"><div class="val">{{ fps }}</div><div class="lbl">FPS</div></div>
      <div class="stat"><div class="val">{{ total }}</div><div class="lbl">Total Detections</div></div>
      <div class="stat"><div class="val">{{ uptime }}</div><div class="lbl">Uptime</div></div>
      <div class="stat"><div class="val">{{ last_plate or '—' }}</div><div class="lbl">Last Plate</div></div>
    </div>
  </div>
  <div class="card">
    <h2>Live Stream</h2>
    <img class="stream" src="/stream" alt="Live feed">
  </div>
  <div class="card">
    <h2>Recent Detections
      <form method="POST" action="/api/clear" style="display:inline; float:right;">
        <button class="btn-clear" type="submit">Clear</button>
      </form>
    </h2>
    <table>
      <tr><th>Plate</th><th>Color</th><th>Det</th><th>OCR</th><th>Time</th></tr>
      {% for r in history %}
      <tr>
        <td><span class="plate-badge">{{ r.plate }}</span></td>
        <td class="color-{{ r.color.lower() }}">{{ r.color }}</td>
        <td>{{ (r.det_conf * 100)|int }}%</td>
        <td>{{ (r.ocr_conf * 100)|int }}%</td>
        <td>{{ r.time_str }}</td>
      </tr>
      {% endfor %}
      {% if not history %}<tr><td colspan="5" style="color:#666;">No detections yet</td></tr>{% endif %}
    </table>
  </div>
</div>
</body>
</html>
"""


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # ----------------------------------------------------------------
    # Dashboard
    # ----------------------------------------------------------------
    @app.route("/")
    def dashboard():
        from jinja2 import Template
        with _lock:
            history_snapshot = list(_history)[-10:][::-1]
            total = _total_detections
            last_plate = history_snapshot[0]["plate"] if history_snapshot else None

        fps = _get_fps()
        uptime_sec = int(time.time() - _start_time)
        h, m, s = uptime_sec // 3600, (uptime_sec % 3600) // 60, uptime_sec % 60
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

        html = Template(_DASHBOARD_HTML).render(
            fps=fps,
            total=total,
            uptime=uptime_str,
            last_plate=last_plate,
            history=history_snapshot,
        )
        return Response(html, mimetype="text/html")

    # ----------------------------------------------------------------
    # MJPEG stream
    # ----------------------------------------------------------------
    def _gen_frames():
        """Generator yielding MJPEG frames."""
        _BLANK_FRAME: Optional[bytes] = None

        def _blank():
            nonlocal _BLANK_FRAME
            if _BLANK_FRAME is None:
                import cv2
                import numpy as np
                img = np.zeros((240, 320, 3), dtype=np.uint8)
                cv2.putText(img, "No signal", (80, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (128, 128, 128), 2)
                _, buf = cv2.imencode(".jpg", img)
                _BLANK_FRAME = buf.tobytes()
            return _BLANK_FRAME

        while True:
            with _lock:
                frame = _latest_frame
            data = frame if frame else _blank()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
            time.sleep(0.1)  # ~10 fps stream

    @app.route("/stream")
    def stream():
        return Response(
            _gen_frames(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    # ----------------------------------------------------------------
    # JSON API
    # ----------------------------------------------------------------
    @app.route("/api/status")
    def api_status():
        with _lock:
            history_snap = list(_history)
            last = history_snap[-1]["plate"] if history_snap else None
            total = _total_detections
        return jsonify({
            "last_plate": last,
            "fps": _get_fps(),
            "uptime_seconds": int(time.time() - _start_time),
            "total_detections": total,
        })

    @app.route("/api/history")
    def api_history():
        with _lock:
            data = list(_history)
        return jsonify(data)

    @app.route("/api/clear", methods=["POST"])
    def api_clear():
        global _total_detections
        with _lock:
            _history.clear()
            _total_detections = 0
        # Redirect back to dashboard if called from browser form
        if request.content_type and "form" in request.content_type:
            from flask import redirect
            return redirect("/")
        return jsonify({"status": "cleared"})

    return app
