# Smart Safety Guard

> IoT & AI-Based Real-Time Industrial Safety Monitoring System

A two-node edge computing system combining IoT sensor fusion (Raspberry Pi 3) with AI-powered computer vision (Jetson Nano) to monitor industrial environments in real time. Data flows to a central Flask backend that serves a live web dashboard, stores historical records, and sends instant Telegram alerts.

---

## System Architecture

```
+-------------------------+         +--------------------------------------------+
|      Jetson Nano        |         |           Raspberry Pi 3                   |
|    (AI Vision Node)     |  HTTP   |         (Central Backend)                  |
|                         | ------> |                                            |
|  USB Webcam (640x480)   |  POST   |  Flask REST API   :5000                   |
|  YOLOv5n inference      |  /api/  |  SQLite database                           |
|  Person detection       |  frame  |  Sensor polling loop (2 s interval)        |
|  Danger zone logic      |  /api/  |  SSE live-push to browsers                 |
|  10 FPS to Pi           | detect  |  Groq Vision AI analyzer                   |
+-------------------------+         |  Telegram Bot (auto alerts + commands)     |
                                    |                                            |
+-------------------------+         |  Sensors:                                  |
|     Web Dashboard       |<------- |    MQ-2 Gas/Smoke    GPIO 25               |
|  http://<PI_IP>:5000    |  HTML   |    DHT22 Temp/Hum    GPIO 27               |
|                         |  + SSE  |    HC-SR04 Distance  GPIO 18/21            |
|  3-column live layout:  |         |    PIR Motion        GPIO 4                |
|  Left:  Camera + AI     |         |                                            |
|  Center:Sensors+Control |         |  Actuators:                                |
|  Right: Charts + Log    |         |    LED Danger/Safe   GPIO 12/13            |
|                         |         |    Buzzer            GPIO 20               |
|  Daily Report page:     |         |    Blue LEDs x3      GPIO 5/6/19           |
|  9 stats, 4 charts,     |         +--------------------------------------------+
|  hourly table, AI log   |                          |
+-------------------------+                          | alerts + AI analysis
                                                     v
                                    +--------------------------------------------+
                                    |         Telegram Bot                        |
                                    |   Commands: /status /alerts /photo         |
                                    |            /analyze /silence               |
                                    |            /led_on /led_off /fan_on        |
                                    |   Auto-send on: alert, AI result           |
                                    +--------------------------------------------+
```

---

## Repository Structure

```
smart_safety_guard/
|-- main.py              Entry point: sensor loop + Flask server + Telegram bot
|-- config.py            GPIO pins, thresholds, API keys, Telegram token
|-- sensors.py           HW abstraction: sensor reads + actuator control
|                        Gas hysteresis debounce (3 consecutive reads required)
|-- alerts.py            Safety evaluation: thresholds -> events -> actuators
|-- database.py          SQLite CRUD + daily report (9 metrics, hourly data)
|-- web_app.py           Flask routes, SSE stream, AI endpoint, Telegram API
|-- ai_analyzer.py       Groq Vision API: visual safety inspection per frame
|-- telegram_bot.py      Telegram bot: alerts, commands, auto chat_id discovery
|
|-- jetson/
|   `-- detector.py      Jetson Nano: YOLOv5n + POSTs frames to Pi
|                        Fallback: raw frame mode when torch unavailable
|
|-- templates/
|   |-- index.html       Live 3-column dashboard
|   `-- report.html      Daily report: stats, charts, event log, AI history
|
|-- static/
|   |-- style.css        Dark-theme CSS (toast, AI spinner, Telegram widget)
|   `-- app.js           SSE client, charts, toasts, analyze button
|
|-- docs/
|   |-- ARCHITECTURE.md  Full architecture + data flow + design decisions
|   |-- SETUP_PI.md      Raspberry Pi 3 setup guide
|   |-- SETUP_JETSON.md  Jetson Nano setup guide
|   `-- API.md           REST API reference
|
|-- requirements.txt     Pi runtime dependencies
`-- README.md
```

---

## Hardware Components

| Component | Model | GPIO | Notes |
|-----------|-------|------|-------|
| Main controller | Raspberry Pi 3 Model B+ | - | Flask backend |
| AI vision node | NVIDIA Jetson Nano 4GB | LAN | YOLOv5 + camera |
| Camera | USB Webcam | USB | 640x480, 10 FPS |
| Gas sensor | MQ-2 | GPIO 25 | Active-LOW, pull-up, hysteresis filter |
| Temp/Humidity | DHT22 | GPIO 27 | Falls back to simulated data |
| Ultrasonic | HC-SR04 | GPIO 18/21 | Danger zone < 50 cm |
| Motion | PIR sensor | GPIO 4 | Optional |
| Buzzer | Active buzzer | GPIO 20 | Edge-triggered, auto-off 3s |
| LED Danger | Red LED | GPIO 12 | ON during any alert |
| LED Safe | Green LED | GPIO 13 | ON when clear |
| Blue LEDs | x3 | GPIO 5/6/19 | Status indicators |
| Cooling fan | DC fan | GPIO opt. | ON for gas/overheat alerts |

---

## Quick Start

### Raspberry Pi 3

```bash
git clone https://github.com/abbosaliboev/Embedded_Systems.git
cd Embedded_Systems
pip3 install -r requirements.txt

# Configure API keys
nano config.py   # Set GROQ_API_KEY, TELEGRAM_BOT_TOKEN

python3 main.py
# Dashboard: http://<PI_IP>:5000
```

### Jetson Nano

```bash
# Use Python 3.8 venv (compatible ARM cv2 4.13.0)
source /home/dalab/detector_venv/bin/activate
cd ~/Embedded_Systems
python3 jetson/detector.py
# Falls back to raw-frame mode if torch/YOLOv5 unavailable
```

---

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `GROQ_API_KEY` | `""` | Get free key at console.groq.com |
| `GROQ_MODEL` | `meta-llama/llama-4-scout-...` | Vision model |
| `TELEGRAM_BOT_TOKEN` | `""` | BotFather token |
| `TELEGRAM_CHAT_ID` | `""` | Auto-discovered on first /start |
| `DISTANCE_DANGER_CM` | `50` | Proximity alert threshold |
| `TEMP_HIGH_CELSIUS` | `40.0` | Overheat threshold |
| `GAS_ALERT_ACTIVE` | `True` | Set False to disable gas sensor |
| `AI_ANALYSIS_COOLDOWN` | `60` | Seconds between auto analyses |

---

## Telegram Bot

1. Create bot at [@BotFather](https://t.me/BotFather), get token
2. Set `TELEGRAM_BOT_TOKEN` in `config.py`
3. Run `python3 main.py`
4. Send `/start` to bot -> chat_id auto-saved

**Commands:** `/status` `/alerts` `/photo` `/analyze` `/silence` `/led_on` `/led_off` `/fan_on` `/fan_off`

---

## AI Analysis (Groq Vision)

Triggered manually (dashboard button) or automatically on safety alerts.
Sends camera frame + sensor context to Groq Vision API, returns:

- **Threat Level:** LOW / MEDIUM / HIGH / CRITICAL
- **Visual Safety Checks:** Fire, Smoke, Persons, PPE compliance, Hazards
- **Risk Assessment + Immediate Action**
- Result shown on dashboard + sent to Telegram with photo

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| IoT Hardware | Raspberry Pi 3B+, NVIDIA Jetson Nano 4GB |
| Backend | Python 3.9, Flask 3.x, SQLite |
| AI / Vision | Groq Vision API (Llama 4), YOLOv5n, OpenCV |
| Notifications | Telegram Bot API |
| Frontend | Vanilla JS, Chart.js 4, SSE, dark CSS |

---

## Team

| Member | Responsibilities |
|--------|-----------------|
| Abbos Aliboyev | AI analyzer, Frontend, Telegram Bot, deployment |
| Team | Backend, Database, Sensor integration |
