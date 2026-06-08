"""
Telegram bot for Smart Safety Guard.
Commands: /start /help /status /alerts /photo /analyze /silence /led /fan
Auto-notifies on safety alerts and AI analysis results.
"""

import logging
import requests
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

_token = ""
_chat_id = ""
_bot_username = ""
_last_update_id = 0
_last_sent_ts = None
_polling_thread = None


def configure(token: str, chat_id: str):
    global _token, _chat_id
    _token = token.strip()
    _chat_id = str(chat_id).strip()


def is_configured() -> bool:
    return bool(_token and _chat_id)


def get_status() -> dict:
    return {
        "configured": is_configured(),
        "bot_name": _bot_username or None,
        "last_sent": _last_sent_ts,
    }


def _api(method: str, **params):
    if not _token:
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_token}/{method}",
            json=params, timeout=10,
        )
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        logger.warning("Telegram API %s error: %s", method, e)
        return None


def _send(chat_id, text, parse_mode="HTML"):
    global _last_sent_ts
    result = _api("sendMessage", chat_id=chat_id or _chat_id,
                   text=str(text)[:4096], parse_mode=parse_mode)
    if result and result.get("ok"):
        _last_sent_ts = datetime.now().strftime("%H:%M:%S")
    return result


def _send_photo(chat_id, photo_bytes: bytes, caption: str = ""):
    global _last_sent_ts
    if not _token:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_token}/sendPhoto",
            data={"chat_id": chat_id or _chat_id,
                  "caption": caption[:1024], "parse_mode": "HTML"},
            files={"photo": ("frame.jpg", photo_bytes, "image/jpeg")},
            timeout=20,
        )
        if r.status_code == 200:
            _last_sent_ts = datetime.now().strftime("%H:%M:%S")
    except Exception as e:
        logger.warning("Telegram sendPhoto error: %s", e)


def send_alert(alert_type: str, details: str, sensor_data: dict):
    """Send safety alert notification to configured chat."""
    if not is_configured():
        return
    icons = {
        "GAS": "\U0001f4a8", "PROXIMITY": "\U0001f4cf",
        "OVERHEAT": "\U0001f321️", "MOTION": "\U0001f6b6",
        "PERSON_DETECTED": "\U0001f441️"
    }
    icon = icons.get(alert_type, "⚠️")
    gas_txt = "⚠️ DETECTED" if sensor_data.get("gas") else "✅ Clear"
    text = (
        f"{icon} <b>SAFETY ALERT: {alert_type}</b>\n"
        f"<i>{details}</i>\n\n"
        f"<b>Sensor snapshot:</b>\n"
        f"  \U0001f321️ Temp: {sensor_data.get('temp', '?')}°C\n"
        f"  \U0001f4a7 Humidity: {sensor_data.get('humidity', '?')}%\n"
        f"  \U0001f4cf Distance: {sensor_data.get('distance', '?')} cm\n"
        f"  \U0001f4a8 Gas: {gas_txt}\n"
        f"  \U0001f550 {datetime.now().strftime('%H:%M:%S')}"
    )
    _send(_chat_id, text)


def send_analysis_result(result: dict):
    """Send AI analysis result with camera photo if available."""
    if not is_configured():
        return
    threat = result.get("threat_level", "?")
    lvl_icon = {
        "LOW": "\U0001f7e2", "MEDIUM": "\U0001f7e1",
        "HIGH": "\U0001f7e0", "CRITICAL": "\U0001f534"
    }.get(threat, "⚪")
    text = (
        f"{lvl_icon} <b>AI Analysis — {threat}</b>\n"
        f"Trigger: {result.get('trigger', '?')}\n\n"
        f"\U0001f50d <b>Scene:</b> {result.get('scene_description', '?')}\n\n"
        f"⚠️ <b>Risk:</b> {result.get('risk_assessment', '?')}\n\n"
        f"✅ <b>Action:</b> {result.get('immediate_action', '?')}\n\n"
        f"\U0001f4cb <b>Summary:</b> {result.get('incident_summary', '?')}\n"
        f"\U0001f550 {result.get('timestamp', datetime.now().strftime('%H:%M:%S'))}"
    )
    # Attach camera frame if available
    try:
        from web_app import _latest_frame_bytes
        if _latest_frame_bytes:
            _send_photo(_chat_id, _latest_frame_bytes, text)
            return
    except Exception:
        pass
    _send(_chat_id, text)


def send_status_report(sensor_data: dict):
    """Send current sensor status report."""
    if not is_configured():
        return
    gas_ok  = not sensor_data.get("gas")
    dist    = sensor_data.get("distance")
    dist_ok = dist is None or dist > 50
    temp    = sensor_data.get("temp")
    temp_ok = temp is None or temp <= 40
    all_ok  = gas_ok and dist_ok and temp_ok
    overall = "\U0001f7e2 ALL CLEAR" if all_ok else "\U0001f7e1 ATTENTION NEEDED"
    text = (
        f"\U0001f6e1️ <b>Smart Safety Guard — Status Report</b>\n"
        f"{overall}\n\n"
        f"\U0001f321️ Temperature: <b>{temp or '??'}°C</b> {'✅' if temp_ok else '⚠️ HIGH'}\n"
        f"\U0001f4a7 Humidity: <b>{sensor_data.get('humidity', '??')}%</b>\n"
        f"\U0001f4cf Distance: <b>{dist or '??'} cm</b> {'✅' if dist_ok else '⚠️ CLOSE'}\n"
        f"\U0001f4a8 Gas/Smoke: <b>{'⚠️ DETECTED' if sensor_data.get('gas') else '✅ Clear'}</b>\n"
        f"\U0001f6b6 Motion: <b>{'YES' if sensor_data.get('pir') else 'No'}</b>\n"
        f"\U0001f550 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    _send(_chat_id, text)


def _handle_command(message: dict):
    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()
    if not text.startswith("/"):
        return
    cmd = text.split()[0].lower().split("@")[0]
    logger.info("Telegram cmd %s from chat %s", cmd, chat_id)

    if cmd in ("/start", "/help"):
        _send(chat_id, (
            "\U0001f6e1️ <b>Smart Safety Guard Bot</b>\n\n"
            "<b>Available commands:</b>\n"
            "/status — Current sensor readings\n"
            "/alerts — Last 5 safety alerts\n"
            "/photo — Latest camera frame\n"
            "/analyze — Trigger AI scene analysis\n"
            "/silence — Stop the buzzer\n"
            "/led_on — Turn LED on\n"
            "/led_off — Turn LED off\n"
            "/fan_on — Turn cooler on\n"
            "/fan_off — Turn cooler off\n"
            "/help — Show this help"
        ))

    elif cmd == "/status":
        from database import get_latest_reading
        r = get_latest_reading() or {}
        send_status_report(r)

    elif cmd == "/alerts":
        from database import get_recent_events
        events = get_recent_events(limit=5)
        if events:
            lines = ["⚠️ <b>Recent Alerts</b>\n"]
            for ev in events:
                ts = (ev.get("timestamp") or "")[-8:]
                lines.append(
                    f"• [{ts}] <b>{ev.get('event_type', '?')}</b>: {ev.get('details', '')}"
                )
            _send(chat_id, "\n".join(lines))
        else:
            _send(chat_id, "✅ No recent alerts!")

    elif cmd == "/photo":
        try:
            from web_app import _latest_frame_bytes
            if _latest_frame_bytes:
                _send_photo(chat_id, _latest_frame_bytes, "\U0001f4f7 Latest camera frame")
            else:
                _send(chat_id, "\U0001f4f7 No camera frame available yet.")
        except Exception:
            _send(chat_id, "\U0001f4f7 Camera unavailable.")

    elif cmd == "/analyze":
        try:
            from ai_analyzer import analyze_async
            from database import get_latest_reading
            reading = get_latest_reading() or {}
            _send(chat_id, "\U0001f916 AI analysis started… Result coming soon.")

            def _on_result(result):
                send_analysis_result(result)

            analyze_async("TELEGRAM_CMD", reading, callback=_on_result)
        except Exception as e:
            _send(chat_id, f"❌ Analysis failed: {e}")

    elif cmd == "/silence":
        try:
            from web_app import _sensor_mgr
            if _sensor_mgr:
                _sensor_mgr.set_buzzer(False)
                _send(chat_id, "\U0001f507 Buzzer silenced.")
        except Exception:
            _send(chat_id, "❌ Failed to silence buzzer.")

    elif cmd == "/led_on":
        try:
            from web_app import _sensor_mgr
            if _sensor_mgr:
                _sensor_mgr.set_led(True)
                _send(chat_id, "\U0001f4a1 LED turned ON.")
        except Exception:
            _send(chat_id, "❌ Failed.")

    elif cmd == "/led_off":
        try:
            from web_app import _sensor_mgr
            if _sensor_mgr:
                _sensor_mgr.set_led(False)
                _send(chat_id, "\U0001f311 LED turned OFF.")
        except Exception:
            _send(chat_id, "❌ Failed.")

    elif cmd == "/fan_on":
        try:
            from web_app import _sensor_mgr
            if _sensor_mgr:
                _sensor_mgr.set_fan(True)
                _send(chat_id, "\U0001f300 Cooler turned ON.")
        except Exception:
            _send(chat_id, "❌ Failed.")

    elif cmd == "/fan_off":
        try:
            from web_app import _sensor_mgr
            if _sensor_mgr:
                _sensor_mgr.set_fan(False)
                _send(chat_id, "⏹ Cooler turned OFF.")
        except Exception:
            _send(chat_id, "❌ Failed.")

    else:
        _send(chat_id, "Unknown command. Type /help for the list of commands.")


def start_polling():
    """Start long-polling for Telegram updates in a background thread."""
    if not _token:
        logger.info("Telegram bot token not configured — bot disabled")
        return

    def _poll():
        global _last_update_id, _bot_username
        info = _api("getMe")
        if info and info.get("ok"):
            _bot_username = info["result"].get("username", "")
            logger.info("Telegram bot @%s started", _bot_username)
            _send(_chat_id, (
                "\U0001f7e2 <b>Smart Safety Guard Online</b>\n"
                f"Bot @{_bot_username} connected. Type /help for commands."
            ))

        while True:
            try:
                result = _api("getUpdates", offset=_last_update_id + 1, timeout=30)
                if result and result.get("ok"):
                    for update in result.get("result", []):
                        _last_update_id = update["update_id"]
                        if "message" in update:
                            try:
                                _handle_command(update["message"])
                            except Exception:
                                logger.exception("Error handling Telegram message")
            except Exception:
                logger.exception("Telegram polling error")
            time.sleep(1)

    global _polling_thread
    _polling_thread = threading.Thread(target=_poll, daemon=True, name="telegram-bot")
    _polling_thread.start()
