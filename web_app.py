"""
Flask web application — serves the dashboard and exposes a JSON API.
Real-time updates are pushed to the browser via Server-Sent Events (SSE).
"""

import json
import os
import queue
import logging
from flask import Flask, render_template, Response, jsonify, request
from database import get_latest_reading, get_recent_readings, get_recent_events, get_daily_report, get_available_days, insert_event

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Broadcast queue: main loop pushes snapshots here; SSE subscribers drain it.
_sse_queue: queue.Queue = queue.Queue(maxsize=50)


def push_sse_update(data: dict):
    """Called by the main loop each time sensors are read."""
    try:
        _sse_queue.put_nowait(data)
    except queue.Full:
        pass  # Drop oldest if no clients are connected


# ------------------------------------------------------------------ #
#  Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/latest")
def api_latest():
    reading = get_latest_reading()
    events = get_recent_events(limit=10)
    return jsonify({"reading": reading, "events": events})


@app.route("/api/history")
def api_history():
    readings = get_recent_readings(limit=120)
    return jsonify(readings)


@app.route("/api/events")
def api_events():
    events = get_recent_events(limit=100)
    return jsonify(events)


@app.route("/api/detection", methods=["POST"])
def api_detection():
    """Receives YOLO detection results from Jetson Nano."""
    data = request.get_json(silent=True) or {}
    in_zone = data.get("in_danger_zone", False)
    conf = data.get("confidence", 0.0)

    if in_zone:
        insert_event("PERSON_DETECTED", f"Confidence: {conf:.0%}")
        push_sse_update({"alert": "PERSON_DETECTED", "confidence": conf})

    return jsonify({"status": "ok"})


@app.route("/api/report")
def api_report():
    day = request.args.get("date")  # ?date=2026-05-05  (optional)
    return jsonify(get_daily_report(day))


@app.route("/api/days")
def api_days():
    return jsonify(get_available_days())


@app.route("/report")
def report_page():
    return render_template("report.html")


@app.route("/stream")
def stream():
    """SSE endpoint — browser connects once and receives live sensor data."""
    def event_generator():
        # Send the latest DB reading immediately on connect.
        reading = get_latest_reading()
        if reading:
            yield _format_sse(reading)

        while True:
            try:
                data = _sse_queue.get(timeout=30)
                yield _format_sse(data)
            except queue.Empty:
                yield ": heartbeat\n\n"  # Keep connection alive

    return Response(event_generator(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ------------------------------------------------------------------ #
#  Server startup helper                                               #
# ------------------------------------------------------------------ #

def run_server(host: str, port: int):
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)
    app.run(host=host, port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    # Standalone entry point used by Railway (sensor loop does NOT run here).
    logging.basicConfig(level=logging.INFO)
    from database import init_db
    init_db()
    port = int(os.getenv("PORT", 5000))
    run_server("0.0.0.0", port)
