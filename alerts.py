"""
Alert engine: evaluates sensor readings against thresholds,
drives actuators, and logs safety events.

Buzzer uses edge-trigger (fires once when alert becomes active).
LED and fan use level-trigger (follow current alert state).
"""

import threading
import logging
from database import insert_event

logger = logging.getLogger(__name__)


class AlertEngine:
    def __init__(self, sensor_manager, config, on_new_alert=None):
        self.sm = sensor_manager
        self.cfg = config
        self.on_new_alert = on_new_alert  # callback(trigger, reading, active_alerts)
        self._buzzer_timer: threading.Timer | None = None
        self._active_alerts: set[str] = set()

    def evaluate(self, reading: dict) -> set[str]:
        """Check all safety conditions and react accordingly."""
        new_alerts: set[str] = set()

        if reading.get("pir") is not None and reading["pir"]:
            new_alerts.add("MOTION")

        if reading.get("distance") is not None and reading["distance"] < self.cfg.DISTANCE_DANGER_CM:
            new_alerts.add("PROXIMITY")

        if reading.get("gas") is not None and reading["gas"]:
            new_alerts.add("GAS")

        if reading.get("temp") is not None and reading["temp"] > self.cfg.TEMP_HIGH_CELSIUS:
            new_alerts.add("OVERHEAT")

        newly_active = new_alerts - self._active_alerts

        # Log and callback only on edge (newly triggered alerts)
        for alert in newly_active:
            details = self._build_details(alert, reading)
            insert_event(alert, details)
            if self.on_new_alert:
                try:
                    self.on_new_alert(alert, reading, new_alerts)
                except Exception:
                    logger.exception("on_new_alert callback failed")

        # LED + fan: level-trigger
        self.sm.set_led(bool(new_alerts))
        self.sm.set_fan("GAS" in new_alerts or "OVERHEAT" in new_alerts)

        # Buzzer: edge-trigger (only when new alert appears; auto-off on clear)
        if newly_active:
            self._trigger_buzzer()
        elif not new_alerts:
            self._cancel_buzzer()

        self._active_alerts = new_alerts
        return new_alerts

    def _build_details(self, alert_type: str, reading: dict) -> str:
        if alert_type == "PROXIMITY":
            return f"Object at {reading['distance']} cm (threshold {self.cfg.DISTANCE_DANGER_CM} cm)"
        if alert_type == "OVERHEAT":
            return f"Temperature {reading['temp']}°C (threshold {self.cfg.TEMP_HIGH_CELSIUS}°C)"
        if alert_type == "GAS":
            return "MQ-2 digital output triggered"
        if alert_type == "MOTION":
            return "PIR sensor triggered"
        return ""

    def _trigger_buzzer(self):
        if self._buzzer_timer:
            self._buzzer_timer.cancel()
            self._buzzer_timer = None
        self.sm.set_buzzer(True)
        self._buzzer_timer = threading.Timer(
            self.cfg.BUZZER_DURATION, self._auto_off_buzzer
        )
        self._buzzer_timer.daemon = True
        self._buzzer_timer.start()

    def _auto_off_buzzer(self):
        self.sm.set_buzzer(False)
        self._buzzer_timer = None

    def _cancel_buzzer(self):
        if self._buzzer_timer:
            self._buzzer_timer.cancel()
            self._buzzer_timer = None
        self.sm.set_buzzer(False)

    def shutdown(self):
        self._cancel_buzzer()
        self.sm.set_led(False)
        self.sm.set_fan(False)
