"""
Flask web application — dashboard, JSON API, SSE live updates,
camera frame receiver, and AI analysis endpoints.
"""

import base64
import json
import logging
import queue
import time
import threading
import os
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request, send_file
from database import (
    get_latest_reading, get_recent_readings, get_recent_events,
    get_daily_report, get_available_days, insert_event, insert_vision_event,
    get_latest_ai_analysis, get_recent_ai_analyses,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

_sse_queue: queue.Queue = queue.Queue(maxsize=50)
_sensor_mgr = None

# Latest JPEG frame received from Jetson Nano (raw bytes)
_new_frame_event = __import__("threading").Event()
_latest_frame_bytes: bytes | None = None
_frame_lock = threading.Lock()
_frame_timestamp: str = ""

# Last vision detection state (for SSE)
_last_vision: dict = {"person_detected": False, "in_danger_zone": False, "confidence": 0.0}


def set_sensor_manager(sm):
    global _sensor_mgr
    _sensor_mgr = sm


def push_sse_update(data: dict):
    """Push sensor / AI data to all connected SSE clients."""
    try:
        _sse_queue.put_nowait(data)
    except queue.Full:
        pass


# ------------------------------------------------------------------ #
#  Routes — pages                                                      #
# ------------------------------------------------------------------ #

@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/report")
def report_page():
    return render_template("report.html")


# ------------------------------------------------------------------ #
#  Routes — sensor API                                                 #
# ------------------------------------------------------------------ #

@app.route("/api/latest")
def api_latest():
    return jsonify({
        "reading": get_latest_reading(),
        "events": get_recent_events(limit=10),
    })


@app.route("/api/history")
def api_history():
    return jsonify(get_recent_readings(limit=120))


@app.route("/api/events")
def api_events():
    return jsonify(get_recent_events(limit=100))


@app.route("/api/report")
def api_report():
    day = request.args.get("date")
    return jsonify(get_daily_report(day))


@app.route("/api/days")
def api_days():
    return jsonify(get_available_days())


# ------------------------------------------------------------------ #
#  Routes — actuator control                                           #
# ------------------------------------------------------------------ #

@app.route("/api/control", methods=["POST"])
def api_control():
    data = request.get_json(silent=True) or {}
    if _sensor_mgr is None:
        return jsonify({"status": "error", "msg": "sensor manager not ready"}), 503
    action = data.get("action")
    if action == "test_buzzer":
        threading.Thread(target=_sensor_mgr.test_buzzer, daemon=True).start()
    elif action == "led_on":
        _sensor_mgr.set_led(True)
        _sensor_mgr.manual_override(60)
    elif action == "led_off":
        _sensor_mgr.set_led(False)
        _sensor_mgr.manual_override(60)
    elif action == "fan_on":
        _sensor_mgr.set_fan(True)
        _sensor_mgr.manual_override(60)
    elif action == "fan_off":
        _sensor_mgr.set_fan(False)
        _sensor_mgr.manual_override(60)
    elif action == "silence":
        _sensor_mgr.set_buzzer(False)
    # Push immediate actuator state via SSE for instant UI feedback
    push_sse_update(_sensor_mgr.get_actuator_state())
    return jsonify({"status": "ok", "action": action, **_sensor_mgr.get_actuator_state()})


# ------------------------------------------------------------------ #
#  Routes — Jetson Nano camera frame receiver                          #
# ------------------------------------------------------------------ #

@app.route("/api/frame", methods=["POST"])
def api_frame():
    """
    Receives an annotated JPEG from Jetson Nano.
    Expected JSON: {"image_b64": "<base64-jpeg>", "timestamp": "..."}
    """
    global _latest_frame_bytes, _frame_timestamp
    data = request.get_json(silent=True) or {}
    b64 = data.get("image_b64", "")
    if b64:
        try:
            frame_bytes = base64.b64decode(b64)
            with _frame_lock:
                _latest_frame_bytes = frame_bytes
                _frame_timestamp = data.get("timestamp", datetime.now().strftime("%H:%M:%S"))
            _new_frame_event.set()
            # Update ai_analyzer with latest frame
            try:
                from ai_analyzer import update_frame
                update_frame(frame_bytes)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Bad frame data: %s", e)
            return jsonify({"status": "error"}), 400
    return jsonify({"status": "ok"})


@app.route("/api/latest_frame")
def api_latest_frame():
    """Returns the latest JPEG frame as a single image."""
    with _frame_lock:
        frame = _latest_frame_bytes
    if frame is None:
        return Response(status=204)
    return Response(frame, mimetype="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@app.route("/video_feed")
def video_feed():
    """MJPEG stream — browser handles this natively with <img src='/video_feed'>."""
    def generate():
        while True:
            _new_frame_event.wait(timeout=1.0)
            _new_frame_event.clear()
            with _frame_lock:
                frame = _latest_frame_bytes
            if frame is None:
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace;boundary=frame",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/frame_info")
def api_frame_info():
    return jsonify({
        "available": _latest_frame_bytes is not None,
        "timestamp": _frame_timestamp,
        "vision": _last_vision,
    })


# ------------------------------------------------------------------ #
#  Routes — YOLO detection from Nano                                   #
# ------------------------------------------------------------------ #

@app.route("/api/detection", methods=["POST"])
def api_detection():
    """Receives YOLO detection results from Jetson Nano."""
    global _last_vision
    data = request.get_json(silent=True) or {}
    person = data.get("person_detected", False)
    in_zone = data.get("in_danger_zone", False)
    conf = float(data.get("confidence", 0.0))

    insert_vision_event(person, in_zone, conf)
    _last_vision = {"person_detected": person, "in_danger_zone": in_zone, "confidence": conf}

    if in_zone:
        insert_event("PERSON_DETECTED", f"Confidence: {conf:.0%}")
        push_sse_update({
            "alert": "PERSON_DETECTED",
            "person_detected": True,
            "in_danger_zone": True,
            "confidence": conf,
        })

    return jsonify({"status": "ok"})


# ------------------------------------------------------------------ #
#  Routes — AI analysis                                                #
# ------------------------------------------------------------------ #

@app.route("/api/latest_analysis")
def api_latest_analysis():
    return jsonify(get_latest_ai_analysis() or {})


@app.route("/api/ai_analyses")
def api_ai_analyses():
    return jsonify(get_recent_ai_analyses(limit=10))


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Manual AI analysis triggered from the dashboard."""
    try:
        import ai_analyzer
        reading = get_latest_reading() or {}
        reading["trigger"] = "MANUAL"

        def _on_result(result):
            push_sse_update({"ai_analysis": result})
            try:
                import telegram_bot
                if telegram_bot.is_configured():
                    telegram_bot.send_analysis_result(result)
            except Exception:
                pass

        ai_analyzer.analyze_async("MANUAL", reading, callback=_on_result)
        return jsonify({"status": "ok", "msg": "Analysis started"})
    except Exception as e:
        logger.exception("Manual analyze error")
        return jsonify({"status": "error", "msg": str(e)}), 500


@app.route("/api/telegram_status")
def api_telegram_status():
    try:
        import telegram_bot
        return jsonify(telegram_bot.get_status())
    except Exception:
        return jsonify({"configured": False, "last_sent": None, "bot_name": None})


@app.route("/api/telegram_send_status", methods=["POST"])
def api_telegram_send_status():
    try:
        import telegram_bot
        if not telegram_bot.is_configured():
            return jsonify({"status": "error", "msg": "Bot not configured"}), 400
        reading = get_latest_reading() or {}
        telegram_bot.send_status_report(reading)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ------------------------------------------------------------------ #
#  Routes — SSE stream                                                 #
# ------------------------------------------------------------------ #

@app.route("/stream")
def stream():
    """SSE endpoint — browsers connect once and receive live sensor data."""
    def event_generator():
        reading = get_latest_reading()
        if reading:
            yield _format_sse(reading)

        while True:
            try:
                data = _sse_queue.get(timeout=30)
                yield _format_sse(data)
            except queue.Empty:
                yield ": heartbeat\n\n"

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ------------------------------------------------------------------ #
#  Server startup                                                      #
# ------------------------------------------------------------------ #

def run_server(host: str, port: int):
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)
    app.run(host=host, port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from database import init_db
    init_db()
    port = int(os.getenv("PORT", 5000))
    run_server("0.0.0.0", port)
