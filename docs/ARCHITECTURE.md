# Architecture Decision Record

## System Overview

Smart Safety Guard uses a **two-node edge architecture** on a local WiFi/LAN network:

| Node | Device | Role |
|------|--------|------|
| IoT Sensor Hub | Raspberry Pi 3 | Central backend, all sensors, Telegram Bot, web dashboard |
| AI Vision Hub | Jetson Nano | YOLOv8 inference, sends detection events to Pi |

---

## Why this split?

### Raspberry Pi 3 → Central Hub

The Pi handles everything that doesn't require GPU compute:

- **Sensor polling** — GPIO-based sensors (MQ-2, DHT22, PIR, Ultrasonic, Sound) are wired directly to Pi GPIO pins. Moving this to Jetson would require rewiring.
- **Flask backend + SQLite** — lightweight, runs comfortably within Pi 3's 1 GB RAM.
- **Telegram Bot** — needs always-on internet connection; Pi is the stable, always-on node.
- **Web dashboard** — serves HTML/SSE to browsers on the same LAN.
- **Actuator control** — Buzzer, Fan, LED, DC Motor are wired to Pi GPIO.

### Jetson Nano → AI Client Only

The Jetson is used exclusively for what it's built for — GPU-accelerated inference:

- **YOLOv8n @ 15–20 FPS** — not possible on Pi 3 (would drop to <1 FPS).
- **Danger zone logic** — calculated locally on Jetson before sending result.
- **Sends a single POST request** to the Pi API when a person is detected — keeps network traffic minimal.

The Jetson does NOT store data, does NOT serve web pages, does NOT handle sensors.

---

## Data Flow

```
┌──────────────┐    GPIO read     ┌───────────────────┐
│  MQ-2 / DHT  │ ──────────────▶ │                   │
│  PIR / Ultra │                 │   Raspberry Pi 3  │──▶ SQLite DB
│  Sound sensor│                 │   Flask :5000     │──▶ Telegram alerts
└──────────────┘                 │   Web dashboard   │──▶ Browser (SSE)
                                 │   Alert engine    │
┌──────────────┐  POST /api/     │                   │
│  Jetson Nano │  detection      │                   │
│  (YOLO+cam)  │ ──────────────▶ │                   │
└──────────────┘                 └───────────────────┘
```

---

## Communication Protocol

Jetson → Pi: **HTTP POST** to `http://<PI_IP>:5000/api/detection`

```json
{
  "person_detected": true,
  "in_danger_zone": true,
  "confidence": 0.87,
  "timestamp": "2026-05-08 14:23:01"
}
```

Pi saves this into `safety_events` table and triggers alerts if `in_danger_zone` is true.

No authentication is required since both devices are on the same isolated LAN.

---

## Alert Priority Levels

| Level | Condition | Response |
|-------|-----------|----------|
| LOW | PIR motion (daytime) | Log only |
| MEDIUM | PIR motion (22:00–06:00) | Telegram alert |
| HIGH | Gas detected / Overheat / Proximity breach | Buzzer + LED + Fan + Telegram |
| CRITICAL | Person in danger zone (YOLO confirmed) | All actuators + Telegram with snapshot |

---

## Database Schema

```sql
sensor_readings  — one row per poll cycle (every 2s)
  id, timestamp, pir, distance, gas, temp, humidity, sound

safety_events    — one row per alert trigger (edge-triggered)
  id, timestamp, event_type, details

vision_events    — one row per YOLO detection from Jetson
  id, timestamp, person_detected, in_danger_zone, confidence
```

---

## Network Requirements

- Both Pi and Jetson must be on the **same WiFi or LAN**.
- Pi's IP should be **static** so Jetson always knows where to POST.
- No internet required for core functionality (only Telegram needs internet).

### Setting a static IP on Pi

Edit `/etc/dhcpcd.conf`:
```
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8
```
