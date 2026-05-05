import os

# GPIO pin assignments — based on Smart IoT Box hardware configuration

# --- Sensor Pins ---
PIR_PIN = 23           # PIR motion sensor (digital input)
TRIG_PIN = 17          # Ultrasonic HC-SR04 trigger
ECHO_PIN = 27          # Ultrasonic HC-SR04 echo
MQ2_DIGITAL_PIN = 25   # MQ-2 gas sensor digital output (DO pin)
DHT_PIN = 4            # DHT11 temperature & humidity sensor
DHT_TYPE = 11          # 11 for DHT11, 22 for DHT22

# --- Actuator Pins ---
BUZZER_PIN = 18
FAN_PIN = 24
LED_RED_PIN = 22
LED_GREEN_PIN = 11

# --- Safety Thresholds ---
DISTANCE_DANGER_CM = 50     # Restricted zone boundary in cm
TEMP_HIGH_CELSIUS = 40.0    # Fan activates above this temperature
GAS_ALERT_ACTIVE = True     # MQ-2 digital output logic: HIGH = gas detected

# --- Timing ---
SENSOR_POLL_INTERVAL = 2.0  # Seconds between sensor reads
BUZZER_DURATION = 3.0       # Seconds buzzer stays on after alert

# --- Web Server ---
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000

# --- Database (MySQL) ---
# On Railway these are set automatically by the MySQL plugin.
# On Pi, set them manually or export as env vars before running.
DB_HOST     = os.getenv("MYSQLHOST",     os.getenv("DB_HOST",     "localhost"))
DB_PORT     = int(os.getenv("MYSQLPORT", os.getenv("DB_PORT",     "3306")))
DB_USER     = os.getenv("MYSQLUSER",     os.getenv("DB_USER",     "pi"))
DB_PASSWORD = os.getenv("MYSQLPASSWORD", os.getenv("DB_PASSWORD", ""))
DB_NAME     = os.getenv("MYSQLDATABASE", os.getenv("DB_NAME",     "safety_guard"))
