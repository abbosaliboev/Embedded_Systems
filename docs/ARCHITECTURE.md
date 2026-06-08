# System Architecture

## Overview

Smart Safety Guard is a distributed edge-computing safety system with three logical tiers:

1. **Sensor + Actuator Node** - Raspberry Pi 3 reads physical sensors and drives actuators
2. **AI Vision Node** - Jetson Nano runs person detection and streams annotated camera frames
3. **Backend + Dashboard** - Flask server on Pi aggregates data, serves web UI, notifies via Telegram

---

## Component Diagram

```
[Sensors]                [Raspberry Pi 3]              [Clients]
  MQ-2 Gas  --GPIO-->  |                    |  SSE  -->  Browser Dashboard
  DHT22     --GPIO-->  |  sensor_loop()     |  HTTP -->  Telegram Bot
  HC-SR04   --GPIO-->  |    read_all()      |
  PIR       --GPIO-->  |    evaluate()      |
                       |    insert_reading()|
[Actuators]            |    push_sse()      |
  LED       <--GPIO--  |                    |
  Buzzer    <--GPIO--  |  Flask API :5000   |
  Fan       <--GPIO--  |    /stream (SSE)   |
                       |    /api/control    |
[Jetson Nano]          |    /api/frame      |
  Webcam --> YOLO      |    /api/detection  |
  detector.py POST --> |    /api/analyze    |
  10 FPS frames        |                    |
  person + zone data   |  ai_analyzer.py   |
                       |    Groq Vision API |
                       |                    |
                       |  telegram_bot.py   |
                       |    polling thread  |
```

---

## Data Flow

### Real-Time Sensor Flow (every 2 seconds)
```
sensors.read_all()
  -> alerts.evaluate()
      -> insert_event() [if new alert]
      -> set_led() / set_buzzer() / set_fan()
      -> on_new_alert callback
          -> telegram_bot.send_alert()
          -> ai_analyzer.analyze_async() [if cooldown passed]
              -> Groq Vision API (with latest frame)
              -> push_sse({ai_analysis: ...})
              -> telegram_bot.send_analysis_result()
  -> insert_reading()
  -> push_sse({sensor data + actuator state})
```

### Camera Frame Flow (Jetson Nano, ~10 FPS)
```
detector.py (Jetson)
  -> cv2.VideoCapture -> frame
  -> YOLOv5n inference (5 FPS) OR skip
  -> draw_frame() [annotate: danger zone + bounding boxes]
  -> POST /api/frame {image_b64, timestamp}
      -> _latest_frame_bytes updated
      -> ai_analyzer.update_frame()
  -> POST /api/detection {person_detected, in_danger_zone, confidence}
      -> insert_vision_event()
      -> push_sse({alert: PERSON_DETECTED}) [if in zone]
```

### AI Analysis Flow (manual trigger)
```
User clicks "Analyze Now"
  -> POST /api/analyze
      -> ai_analyzer.analyze_async("MANUAL", reading, callback)
          [background thread]
          -> get_frame() -- latest JPEG from Jetson
          -> Groq Vision API:
              system: expert safety inspector
              user:   sensor context + visual inspection guide (fire/smoke/PPE/persons/hazards)
              image:  base64 JPEG
          -> parse JSON -> insert_ai_analysis()
          -> callback(result)
              -> push_sse({ai_analysis: result})
              -> telegram_bot.send_analysis_result()
```

---

## Database Schema

```sql
sensor_readings (id, timestamp, pir, distance, gas, temp, humidity)
safety_events   (id, timestamp, event_type, details)
vision_events   (id, timestamp, person_detected, in_danger_zone, confidence)
ai_analyses     (id, timestamp, trigger, threat_level, scene_desc, risk, action, summary)
```

---

## Alert Logic

| Condition | Trigger | Actions |
|-----------|---------|---------|
| distance < 50 cm | PROXIMITY | Buzzer (3s), LED danger, log |
| gas True (3+ consecutive reads) | GAS | Buzzer, LED, Fan ON, log |
| temp > 40.0 C | OVERHEAT | Fan ON, LED, log |
| pir True | MOTION | Buzzer, LED, log |
| Person in danger zone (YOLO) | PERSON_DETECTED | log, SSE alert |

**Gas hysteresis:** 3 consecutive True reads to trigger, 3 False to clear.
Prevents false positives from floating GPIO pin.

**Buzzer:** edge-triggered, auto-off after 3 seconds.

---

## AI Safety Analysis - Prompt Design

The AI prompt explicitly separates sensor data (background context) from visual analysis:
- Sensor readings provided as metadata only
- AI asked to describe ONLY what it visually sees
- 5 visual safety checks: Fire / Smoke / Persons / PPE / Hazards
- Threat level based on visual findings, not sensor readings
- Graceful fallback message when no camera frame available

---

## Telegram Bot Design

```
Auto chat_id discovery:
  1. Bot starts with token only
  2. On first /start message -> save chat_id to .telegram_chat_id file
  3. Loaded on subsequent restarts

Notification flow:
  Alert triggered -> send_alert() -> sendMessage (text)
  AI analysis done -> send_analysis_result():
    if frame available -> sendPhoto(frame, caption=analysis)
    else              -> sendMessage(analysis text)
```

---

## Frontend Design

**Dashboard (index.html + app.js):**
- SSE connection to /stream for live sensor updates
- 3-column layout: Camera+AI | Sensors+Controls | Charts+Log
- Toast notifications (stacked, color-coded by severity)
- AI pending spinner state during analysis
- Telegram widget with Status/Photo/Analyze buttons

**Report page (report.html):**
- Standalone JS, no framework
- /api/report API: 9 stat cards, 4 hourly charts, event log, AI history
- AI threat distribution donut chart
- Hourly sensor table with color-coded temperature
