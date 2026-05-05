"""
Sensor abstraction layer.

On the Raspberry Pi this module uses RPi.GPIO and Adafruit_DHT.
When running on a non-Pi host (dev / CI) it falls back to mock values
so the rest of the codebase can be tested without hardware.
"""

import time
import logging
import random

logger = logging.getLogger(__name__)

# Attempt to import hardware libraries; fall back to mock mode gracefully.
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
    logger.warning("Adafruit_DHT not available — DHT readings will be simulated")


class SensorManager:
    def __init__(self, config):
        self.cfg = config
        self._setup_gpio()

    # ------------------------------------------------------------------ #
    #  GPIO setup                                                          #
    # ------------------------------------------------------------------ #

    def _setup_gpio(self):
        if not GPIO_AVAILABLE:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        GPIO.setup(self.cfg.PIR_PIN, GPIO.IN)
        GPIO.setup(self.cfg.TRIG_PIN, GPIO.OUT)
        GPIO.setup(self.cfg.ECHO_PIN, GPIO.IN)
        GPIO.setup(self.cfg.MQ2_DIGITAL_PIN, GPIO.IN)

        # Actuators
        GPIO.setup(self.cfg.BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.FAN_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.LED_RED_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.cfg.LED_GREEN_PIN, GPIO.OUT, initial=GPIO.HIGH)

        logger.info("GPIO pins configured")

    # ------------------------------------------------------------------ #
    #  Sensor reads                                                        #
    # ------------------------------------------------------------------ #

    def read_pir(self) -> bool:
        if not GPIO_AVAILABLE:
            return random.random() < 0.15  # ~15% chance motion in simulation
        return bool(GPIO.input(self.cfg.PIR_PIN))

    def read_distance_cm(self) -> float | None:
        """Returns distance in cm or None if measurement timed out."""
        if not GPIO_AVAILABLE:
            return round(random.uniform(20, 200), 1)

        GPIO.output(self.cfg.TRIG_PIN, GPIO.LOW)
        time.sleep(0.002)

        GPIO.output(self.cfg.TRIG_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(self.cfg.TRIG_PIN, GPIO.LOW)

        timeout = time.time() + 0.04  # 40 ms max wait
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

        duration = pulse_end - pulse_start
        distance = round(duration * 17150, 1)  # speed of sound / 2
        return distance if 2 <= distance <= 400 else None

    def read_gas(self) -> bool:
        """True = gas / smoke detected (MQ-2 digital output HIGH)."""
        if not GPIO_AVAILABLE:
            return random.random() < 0.05
        return bool(GPIO.input(self.cfg.MQ2_DIGITAL_PIN))

    def read_dht(self) -> tuple[float | None, float | None]:
        """Returns (temperature_celsius, humidity_percent)."""
        if not DHT_AVAILABLE or not GPIO_AVAILABLE:
            return (round(random.uniform(22, 45), 1), round(random.uniform(30, 80), 1))

        sensor = Adafruit_DHT.DHT11 if self.cfg.DHT_TYPE == 11 else Adafruit_DHT.DHT22
        humidity, temperature = Adafruit_DHT.read_retry(sensor, self.cfg.DHT_PIN)
        return (temperature, humidity)

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
    #  Actuator control                                                    #
    # ------------------------------------------------------------------ #

    def set_buzzer(self, state: bool):
        if GPIO_AVAILABLE:
            GPIO.output(self.cfg.BUZZER_PIN, GPIO.HIGH if state else GPIO.LOW)

    def set_fan(self, state: bool):
        if GPIO_AVAILABLE:
            GPIO.output(self.cfg.FAN_PIN, GPIO.HIGH if state else GPIO.LOW)

    def set_led(self, danger: bool):
        """Red LED on = danger; green LED on = safe."""
        if GPIO_AVAILABLE:
            GPIO.output(self.cfg.LED_RED_PIN, GPIO.HIGH if danger else GPIO.LOW)
            GPIO.output(self.cfg.LED_GREEN_PIN, GPIO.LOW if danger else GPIO.HIGH)

    def cleanup(self):
        if GPIO_AVAILABLE:
            GPIO.cleanup()
            logger.info("GPIO cleaned up")
