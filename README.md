# Smart Safety Guard

IoT & AI-Based Real-Time Industrial Safety Monitoring System

## Overview

Smart Safety Guard is a two-node edge computing system that combines IoT sensor fusion (Raspberry Pi 3) with AI-powered computer vision (Jetson Nano) to monitor industrial environments 24/7. All data flows into a central Flask backend running on the Pi, which serves a live web dashboard and sends instant Telegram alerts.

## System Architecture

```
┌─────────────────────────┐         ┌─────────────────────────────────────┐
│      Jetson Nano        │         │          Raspberry Pi 3              │
│    (AI Vision Hub)      │         │       (Central Backend Hub)          │
│                         │  POST   │                                      │
│  USB Webcam             │────────▶│  Flask REST API  :5000               │
│  YOLOv8n model          │  /api/  │  SQLite database                     │
│  Person detection       │detection│  Sensor polling loop                 │
│  Danger zone logic      │         │  Telegram Bot                        │
│                         │         │  Web Dashboard                       │
└─────────────────────────┘         │                                      │
                                    │  Sensors:                            │
┌─────────────────────────┐         │    MQ-2 Gas · DHT22 · PIR            │
│      Web Browser        │◀────────│    Ultrasonic · Sound                │
│   (any device on LAN)   │  HTML/  │                                      │
│   http://<PI_IP>:5000   │  SSE    │  Actuators:                          │
└─────────────────────────┘         │    LED · Fan · DC Motor              │
                                    └─────────────────────────────────────┘
┌─────────────────────────┐                         │
│     Telegram Bot        │◀────────────────────────┘
│  /status /snapshot      │       alerts
│  /history /alert off    │
└─────────────────────────┘
```

## Repository Structure

```
smart_safety_guard/
├── main.py               # Entry point — sensor loop + Flask server + Telegram bot
├── config.py             # All GPIO pins, thresholds, API tokens
├── sensors.py            # Hardware abstraction (reads sensors, drives actuators)
├── alerts.py             # Safety logic — evaluates readings, logs events
├── database.py           # SQLite CRUD + daily report queries
├── web_app.py            # Flask routes, SSE endpoint, detection API
├── telegram_bot.py       # Telegram bot — alerts + command handlers
│
├── jetson/
│   └── detector.py       # Runs on Jetson Nano — YOLO inference + POSTs to Pi
│
├── templates/
│   ├── index.html        # Live sensor dashboard
│   └── report.html       # Daily report page
│
├── static/
│   ├── style.css
│   └── app.js
│
├── docs/
│   ├── ARCHITECTURE.md   # Detailed architecture decisions
│   ├── SETUP_PI.md       # Pi 3 setup guide
│   ├── SETUP_JETSON.md   # Jetson Nano setup guide
│   └── API.md            # REST API reference
│
├── requirements.txt      # Pi dependencies
├── requirements-web.txt  # Railway / web-only dependencies
└── README.md
```

## Quick Start

See the full setup guides:
- [Raspberry Pi 3 Setup](docs/SETUP_PI.md)
- [Jetson Nano Setup](docs/SETUP_JETSON.md)

## Team

| Member | Responsibilities |
|--------|-----------------|
| Ali | AI model (YOLOv8), Frontend, Telegram Bot |
| 전설민 | Backend API, Database, AI integration |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| IoT Hardware | Raspberry Pi 3, Jetson Nano, USB Webcam |
| Backend | Python 3, Flask, SQLite |
| AI / Vision | YOLOv8n, OpenCV |
| Notifications | python-telegram-bot |
| Frontend | HTML/CSS/JS, Chart.js, SSE |
