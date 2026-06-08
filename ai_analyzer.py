"""
AI Incident Analyzer — uses Groq vision API to analyze camera frames
whenever a safety alert is triggered. Results are stored in the database
and optionally forwarded to Telegram.
"""

import base64
import json
import logging
import time
import threading
from datetime import datetime

import config
from database import insert_ai_analysis

logger = logging.getLogger(__name__)

# In-memory store for the latest JPEG frame received from Jetson Nano
_latest_frame: bytes | None = None
_frame_lock = threading.Lock()

# Per-trigger cooldown tracking
_last_analysis: dict[str, float] = {}
_analysis_lock = threading.Lock()


def update_frame(frame_bytes: bytes):
    """Called by web_app when Nano POSTs a new frame."""
    global _latest_frame
    with _frame_lock:
        _latest_frame = frame_bytes


def get_frame() -> bytes | None:
    with _frame_lock:
        return _latest_frame


def should_analyze(trigger: str) -> bool:
    """Rate-limit analyses per trigger type."""
    with _analysis_lock:
        last = _last_analysis.get(trigger, 0)
        return (time.time() - last) >= config.AI_ANALYSIS_COOLDOWN


def _mark_analyzed(trigger: str):
    with _analysis_lock:
        _last_analysis[trigger] = time.time()


def analyze_incident(trigger: str, sensor_data: dict, frame_bytes: bytes | None = None) -> dict | None:
    """
    Calls Groq API with sensor context + optional image.
    Returns structured dict or None on failure.
    """
    key = getattr(config, "GROQ_API_KEY", "")
    if not key or key == "your-groq-api-key-here":
        logger.warning("Groq API key not configured — skipping AI analysis")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=key)

        sensor_text = (
            f"Sensor readings at time of incident:\n"
            f"  Gas/Smoke detected: {sensor_data.get('gas', 'N/A')}\n"
            f"  Distance to nearest object: {sensor_data.get('distance', 'N/A')} cm\n"
            f"  Temperature: {sensor_data.get('temp', 'N/A')}°C\n"
            f"  Humidity: {sensor_data.get('humidity', 'N/A')}%\n"
            f"  Motion (PIR): {sensor_data.get('pir', 'N/A')}\n"
            f"  Active alerts: {sensor_data.get('alerts', [])}\n"
            f"  Trigger: {trigger}"
        )

        system_prompt = (
            "You are an AI safety analyst for an industrial IoT monitoring system called Smart Safety Guard. "
            "When alerted, analyze the situation using sensor data and the scene image (if provided). "
            "Be concise, factual, and actionable. Respond ONLY with valid JSON — no markdown, no extra text."
        )

        user_prompt = (
            f"{sensor_text}\n\n"
            "Analyze this safety incident and return JSON with exactly these keys:\n"
            "{\n"
            '  "threat_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",\n'
            '  "scene_description": "brief description of what is happening",\n'
            '  "risk_assessment": "specific risks based on sensors and image",\n'
            '  "immediate_action": "what should be done right now",\n'
            '  "incident_summary": "one sentence for the incident log"\n'
            "}"
        )

        content_parts = []
        if frame_bytes:
            b64 = base64.b64encode(frame_bytes).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        content_parts.append({"type": "text", "text": user_prompt})

        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_parts},
            ],
            max_tokens=600,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        result = json.loads(raw)
        result["trigger"] = trigger
        result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        insert_ai_analysis(
            trigger=trigger,
            threat_level=result.get("threat_level", "UNKNOWN"),
            scene_desc=result.get("scene_description", ""),
            risk=result.get("risk_assessment", ""),
            action=result.get("immediate_action", ""),
            summary=result.get("incident_summary", ""),
        )

        _mark_analyzed(trigger)
        logger.info("AI analysis complete: trigger=%s threat=%s", trigger, result.get("threat_level"))
        return result

    except json.JSONDecodeError:
        logger.error("Groq returned non-JSON response")
        return None
    except Exception:
        logger.exception("AI analysis failed")
        return None


def analyze_async(trigger: str, sensor_data: dict, callback=None):
    """
    Runs analyze_incident in a background thread.
    callback(result) is called with the dict result on success.
    """
    frame = get_frame()

    def _run():
        result = analyze_incident(trigger, sensor_data, frame)
        if result and callback:
            callback(result)

    threading.Thread(target=_run, daemon=True, name=f"ai-{trigger}").start()
