# GPIO pin assignments â€” confirmed by hardware scan

# --- Sensor Pins ---
PIR_ENABLED = False    # Set True once PIR pin is confirmed
PIR_PIN = 4            # PIR motion sensor â€” pin not confirmed yet
TRIG_PIN = 18          # Ultrasonic HC-SR04 trigger (confirmed)
ECHO_PIN = 21          # Ultrasonic HC-SR04 echo (confirmed)
MQ2_DIGITAL_PIN = 25   # MQ-2 gas sensor (confirmed)
DHT_PIN = 27           # DHT sensor â€” no signal yet
DHT_TYPE = 22          # 22 for DHT22

# --- Actuator Pins ---
BUZZER_PIN = 20        # Buzzer (confirmed)
FAN_PIN = None         # Fan on J29 â€” GPIO pin not found yet
LED_DANGER_PIN = 12    # Turns ON all LEDs (danger)
LED_SAFE_PIN = 13      # Turns OFF all LEDs (safe/clear)
LED_BLUE1_PIN = 5      # Single blue LED
LED_BLUE2_PIN = 6      # LED1
LED_BLUE3_PIN = 19     # Blue LED 2

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

# --- Database ---
DB_PATH = "safety_logs.db"

# --- AI Analysis (Groq) ---
GROQ_API_KEY = ""   # Get free key at console.groq.com
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
AI_ANALYSIS_COOLDOWN = 60                  # Min seconds between AI analyses

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN = "8807317620:AAGrpn-GqGr6sJNotXcFYzUNm45Ura0vDgw"   # BotFather token (optional)
TELEGRAM_CHAT_ID = ""     # Your chat ID (optional)
