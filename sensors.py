"""
Sensor abstraction layer for Raspberry Pi GPIO sensors and actuators.
Falls back to mock/None mode when RPi.GPIO is unavailable (dev/CI).
"""

import time
import logging

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available — running in mock/simulation mode")

try:
    import Adafruit_DHT
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    logger.warning("Adafruit_DHT not available — DHT readings will be None")


class SensorManager:
    def __init__(self, config):
        self.cfg = config
        self._led_on = False
        self._buzzer_on = False
        self._fan_on = False
        self._setup_gpio()

    # ------------------------------------------------------------------ #
    #  GPIO setup                                                          #
    # ------------------------------------------------------------------ #

    def _setup_gpio(self):
        if not GPIO_AVAILABLE:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        if self.cfg.PIR_ENABLED:
            GPIO.setup(self.cfg.PIR_PIN, GPIO.IN)
        GPIO.setup(self.cfg.TRIG_PIN, GPIO.OUT)
        GPIO.setup(self.cfg.ECHO_PIN, GPIO.IN)
        GPIO.setup(self.cfg.MQ2_DIGITAL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.setup(self.cfg.BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        if self.cfg.FAN_PIN:
            GPIO.setup(self.cfg.FAN_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.LED_DANGER_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.LED_SAFE_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.LED_BLUE1_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.LED_BLUE2_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.LED_BLUE3_PIN, GPIO.OUT, initial=GPIO.LOW)

        logger.info("GPIO pins configured")

    # ------------------------------------------------------------------ #
    #  Sensor reads                                                        #
    # ------------------------------------------------------------------ #

    def read_pir(self):
        if not GPIO_AVAILABLE or not self.cfg.PIR_ENABLED:
            return None
        return bool(GPIO.input(self.cfg.PIR_PIN))

    def read_distance_cm(self):
        """Returns distance in cm or None on timeout."""
        if not GPIO_AVAILABLE:
            return None

        GPIO.output(self.cfg.TRIG_PIN, GPIO.LOW)
        time.sleep(0.002)
        GPIO.output(self.cfg.TRIG_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(self.cfg.TRIG_PIN, GPIO.LOW)

        timeout = time.time() + 0.04
        pulse_start = time.time()
        while GPIO.input(self.cfg.ECHO_PIN) == 0:
            pulse_start = time.time()
            if time.time() > timeout:
                return None

        pulse_end = time.time()
        while GPIO.input(self.cfg.ECHO_PIN) == 1:
            pulse_end = time.time()
            if time.time() > timeout:
                return None

        distance = round((pulse_end - pulse_start) * 17150, 1)
        return distance if 2 <= distance <= 400 else None

    def read_gas(self):
        """True = gas/smoke detected. Uses hysteresis to filter false positives."""
        if not GPIO_AVAILABLE:
            return None
        if not getattr(self.cfg, "GAS_ALERT_ACTIVE", True):
            return False
        # MQ-2 active-LOW with pull-up: LOW=gas detected, HIGH=clear
        raw = not bool(GPIO.input(self.cfg.MQ2_DIGITAL_PIN))
        # Hysteresis: require 3 consecutive True readings before reporting True
        if raw:
            self._gas_hysteresis = min(self._gas_hysteresis + 1, 4)
        else:
            self._gas_hysteresis = max(self._gas_hysteresis - 1, 0)
        return self._gas_hysteresis >= 3

    def read_dht(self):
        """Returns (temperature_celsius, humidity_percent).
        Uses real DHT sensor if available, otherwise simulated demo values."""
        if DHT_AVAILABLE and GPIO_AVAILABLE:
            sensor = Adafruit_DHT.DHT11 if self.cfg.DHT_TYPE == 11 else Adafruit_DHT.DHT22
            humidity, temperature = Adafruit_DHT.read_retry(sensor, self.cfg.DHT_PIN)
            return (temperature, humidity)
        import random, math
        t = time.time()
        temp = round(24.0 + 2.5 * math.sin(t / 60) + random.uniform(-0.3, 0.3), 1)
        humidity = round(52.0 + 5.0 * math.sin(t / 90) + random.uniform(-0.5, 0.5), 1)
        return (temp, humidity)

    def read_all(self) -> dict:
        pir = self.read_pir()
        distance = self.read_distance_cm()
        gas = self.read_gas()
        temp, humidity = self.read_dht()
        return {
            "pir": pir,
            "distance": distance,
            "gas": gas,
            "temp": temp,
            "humidity": humidity,
        }

    # ------------------------------------------------------------------ #
    #  Actuator state                                                      #
    # ------------------------------------------------------------------ #

    def get_actuator_state(self) -> dict:
        return {
            "led_on": self._led_on,
            "buzzer_on": self._buzzer_on,
            "fan_on": self._fan_on,
        }

    def manual_override(self, seconds=60):
        """Block auto-actuator changes for N seconds after manual control."""
        self._override_until = time.time() + seconds

    def is_override_active(self):
        return time.time() < getattr(self, "_override_until", 0)

    # ------------------------------------------------------------------ #
    #  Actuator control                                                    #
    # ------------------------------------------------------------------ #

    def set_buzzer(self, state: bool):
        self._buzzer_on = bool(state)
        if GPIO_AVAILABLE:
            GPIO.output(self.cfg.BUZZER_PIN, GPIO.HIGH if state else GPIO.LOW)

    def set_fan(self, state: bool):
        self._fan_on = bool(state)
        if GPIO_AVAILABLE and self.cfg.FAN_PIN:
            GPIO.output(self.cfg.FAN_PIN, GPIO.HIGH if state else GPIO.LOW)

    def set_led(self, danger: bool):
        self._led_on = bool(danger)
        if GPIO_AVAILABLE:
            if danger:
                GPIO.output(self.cfg.LED_DANGER_PIN, GPIO.HIGH)
                GPIO.output(self.cfg.LED_SAFE_PIN, GPIO.LOW)
                GPIO.output(self.cfg.LED_BLUE1_PIN, GPIO.HIGH)
                GPIO.output(self.cfg.LED_BLUE2_PIN, GPIO.HIGH)
                GPIO.output(self.cfg.LED_BLUE3_PIN, GPIO.HIGH)
            else:
                GPIO.output(self.cfg.LED_DANGER_PIN, GPIO.LOW)
                GPIO.output(self.cfg.LED_SAFE_PIN, GPIO.HIGH)
                GPIO.output(self.cfg.LED_BLUE1_PIN, GPIO.LOW)
                GPIO.output(self.cfg.LED_BLUE2_PIN, GPIO.LOW)
                GPIO.output(self.cfg.LED_BLUE3_PIN, GPIO.LOW)

    def test_buzzer(self):
        """Short beep for dashboard test button."""
        self.set_buzzer(True)
        time.sleep(0.5)
        self.set_buzzer(False)

    def cleanup(self):
        if GPIO_AVAILABLE:
            self.set_led(False)
            self.set_buzzer(False)
            self.set_fan(False)
            GPIO.cleanup()
            logger.info("GPIO cleaned up")
