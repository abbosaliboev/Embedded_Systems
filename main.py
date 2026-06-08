"""
Smart Safety Guard — main entry point.

Threads:
  1. Sensor polling loop  → reads sensors, evaluates alerts, pushes SSE
  2. Flask web server     → dashboard at :5000
  3. Telegram bot polling → optional, if token is configured
"""

import time
import signal
import logging
import threading
import sys

import config
from database import init_db, insert_reading
from sensors import SensorManager
from alerts import AlertEngine
from web_app import run_server, push_sse_update, set_sensor_manager
import ai_analyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("safety_guard.log"),
    ],
)
logger = logging.getLogger(__name__)

_running = True


def _on_new_alert(trigger: str, reading: dict, active_alerts: set):
    """Called by AlertEngine when an alert becomes newly active."""
    # Forward alert to Telegram immediately
    try:
        import telegram_bot
        if telegram_bot.is_configured():
            telegram_bot.send_alert(trigger, trigger, reading)
    except Exception:
        logger.warning("Failed to send Telegram alert", exc_info=True)

    if not ai_analyzer.should_analyze(trigger):
        return
    sensor_data = {**reading, "alerts": list(active_alerts)}

    def _on_result(result):
        push_sse_update({"ai_analysis": result})
        try:
            import telegram_bot
            if telegram_bot.is_configured():
                telegram_bot.send_analysis_result(result)
        except Exception:
            pass

    ai_analyzer.analyze_async(trigger, sensor_data, callback=_on_result)


def sensor_loop(sensor_mgr: SensorManager, alert_engine: AlertEngine):
    logger.info("Sensor polling started (interval: %ss)", config.SENSOR_POLL_INTERVAL)
    while _running:
        try:
            reading = sensor_mgr.read_all()
            active_alerts = alert_engine.evaluate(reading)

            insert_reading(
                pir=reading["pir"],
                distance=reading["distance"],
                gas=reading["gas"],
                temp=reading["temp"],
                humidity=reading["humidity"],
            )

            sse_payload = {
                **reading,
                "alerts": list(active_alerts),
                **sensor_mgr.get_actuator_state(),
                "pir": bool(reading["pir"]) if reading["pir"] is not None else None,
                "gas": bool(reading["gas"]) if reading["gas"] is not None else None,
            }
            push_sse_update(sse_payload)

        except Exception:
            logger.exception("Error in sensor loop")

        time.sleep(config.SENSOR_POLL_INTERVAL)


def main():
    global _running

    logger.info("=== Smart Safety Guard starting ===")
    init_db()

    sensor_mgr = SensorManager(config)
    alert_engine = AlertEngine(sensor_mgr, config, on_new_alert=_on_new_alert)
    set_sensor_manager(sensor_mgr)

    # Start Telegram bot if configured
    try:
        import telegram_bot
        tok = getattr(config, "TELEGRAM_BOT_TOKEN", "")
        cid = getattr(config, "TELEGRAM_CHAT_ID", "")
        if tok and cid:
            telegram_bot.configure(tok, cid)
            telegram_bot.start_polling()
            logger.info("Telegram bot started")
        else:
            logger.info("Telegram bot not configured (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in config.py)")
    except Exception:
        logger.exception("Failed to start Telegram bot")

    def shutdown(signum, frame):
        global _running
        logger.info("Shutdown signal received")
        _running = False
        alert_engine.shutdown()
        sensor_mgr.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    t = threading.Thread(target=sensor_loop, args=(sensor_mgr, alert_engine), daemon=True)
    t.start()

    logger.info("Dashboard available at http://<raspberry-pi-ip>:%s", config.WEB_PORT)
    run_server(config.WEB_HOST, config.WEB_PORT)


if __name__ == "__main__":
    main()
