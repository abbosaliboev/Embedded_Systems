"""
Alert engine: evaluates sensor readings against thresholds,
triggers actuators, and logs safety events to the database.
"""

import threading
import logging
from database import insert_event

logger = logging.getLogger(__name__)


class AlertEngine:
    def __init__(self, sensor_manager, config):
        self.sm = sensor_manager
        self.cfg = config
        self._buzzer_timer: threading.Timer | None = None
        self._active_alerts: set[str] = set()

    def evaluate(self, reading: dict):
        """Check all safety conditions and react accordingly."""
        new_alerts = set()

        if reading["pir"]:
            new_alerts.add("MOTION")

        if reading["distance"] is not None and reading["distance"] < self.cfg.DISTANCE_DANGER_CM:
            new_alerts.add("PROXIMITY")

        if reading["gas"]:
            new_alerts.add("GAS")

        if reading["temp"] is not None and reading["temp"] > self.cfg.TEMP_HIGH_CELSIUS:
            new_alerts.add("OVERHEAT")

        # Log events that just became active (edge trigger, not level trigger)
        for alert in new_alerts - self._active_alerts:
            details = self._build_details(alert, reading)
            insert_event(alert, details)

        any_danger = bool(new_alerts)
        self._apply_actuators(any_danger, "GAS" in new_alerts or "OVERHEAT" in new_alerts)
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

    def _apply_actuators(self, danger: bool, run_fan: bool):
        self.sm.set_led(danger)
        self.sm.set_fan(run_fan)

        if danger:
            self._trigger_buzzer()
        else:
            self._cancel_buzzer()

    def _trigger_buzzer(self):
        # Cancel any pending auto-off timer so it doesn't turn off mid-alert.
        if self._buzzer_timer:
            self._buzzer_timer.cancel()
            self._buzzer_timer = None

        self.sm.set_buzzer(True)

        # Auto-off after BUZZER_DURATION seconds.
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
