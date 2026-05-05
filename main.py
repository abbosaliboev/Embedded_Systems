"""
Smart Safety Guard — main entry point.

Starts two threads:
  1. Sensor polling loop  → reads sensors, saves to DB, evaluates alerts
  2. Flask web server     → serves the dashboard over the local network
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
from web_app import run_server, push_sse_update

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

            # Attach alert list for the SSE broadcast
            sse_payload = {**reading, "alerts": list(active_alerts)}
            # Convert bool/None so JSON serializer is happy
            sse_payload["pir"] = bool(reading["pir"])
            sse_payload["gas"] = bool(reading["gas"])
            push_sse_update(sse_payload)

            logger.debug("Reading: %s | Active alerts: %s", reading, active_alerts)

        except Exception:
            logger.exception("Error in sensor loop")

        time.sleep(config.SENSOR_POLL_INTERVAL)


def main():
    global _running

    logger.info("=== Smart Safety Guard starting ===")
    init_db()

    sensor_mgr = SensorManager(config)
    alert_engine = AlertEngine(sensor_mgr, config)

    # Graceful shutdown on Ctrl-C or SIGTERM
    def shutdown(signum, frame):
        global _running
        logger.info("Shutdown signal received")
        _running = False
        alert_engine.shutdown()
        sensor_mgr.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Sensor thread
    t = threading.Thread(target=sensor_loop, args=(sensor_mgr, alert_engine), daemon=True)
    t.start()

    # Web server runs on the main thread (blocking)
    logger.info("Dashboard available at http://<raspberry-pi-ip>:%s", config.WEB_PORT)
    run_server(config.WEB_HOST, config.WEB_PORT)


if __name__ == "__main__":
    main()
