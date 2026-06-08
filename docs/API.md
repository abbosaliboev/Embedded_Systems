# REST API Reference

Base URL: `http://<PI_IP>:5000`

---

## Sensor Data

### GET /api/latest
Latest reading + 10 recent events.

### GET /api/history
Last 120 sensor readings (newest first).

### GET /api/events
Last 100 safety events.

---

## Daily Report

### GET /api/report?date=YYYY-MM-DD
```json
{
  "stats": {"total_readings":1440,"avg_temp":24.3,"max_temp":31.0,"min_temp":22.1,
            "avg_humidity":51.2,"min_distance":38.0,"motion_count":12,"gas_count":0},
  "hourly_temp":  [{"hour":"08","avg_temp":23.1}],
  "hourly_hum":   [{"hour":"08","avg_humidity":50.2}],
  "hourly_dist":  [{"hour":"08","avg_dist":95.0,"min_dist":42.0}],
  "hourly_gas":   [{"hour":"08","gas_count":0}],
  "events":       [{"event_type":"GAS","cnt":2}],
  "event_log":    [{"timestamp":"...","event_type":"...","details":"..."}],
  "ai_analyses":  [{"timestamp":"...","trigger":"...","threat_level":"LOW","scene_desc":"..."}],
  "ai_threats":   [{"threat_level":"LOW","cnt":3}]
}
```

### GET /api/days
List of dates with recorded data (last 30 days).

---

## Actuator Control

### POST /api/control
```json
{"action": "led_on|led_off|fan_on|fan_off|test_buzzer|silence"}
```
Response:
```json
{"status":"ok","action":"led_on","led_on":true,"buzzer_on":false,"fan_on":false}
```

---

## Camera

### GET /api/latest_frame
Latest JPEG frame (image/jpeg).

### GET /api/frame_info
```json
{"available":true,"timestamp":"HH:MM:SS","vision":{"person_detected":false,"in_danger_zone":false,"confidence":0.0}}
```

### POST /api/frame  (Jetson -> Pi)
```json
{"image_b64":"<base64>","timestamp":"HH:MM:SS"}
```

### POST /api/detection  (Jetson -> Pi)
```json
{"person_detected":true,"in_danger_zone":false,"confidence":0.87}
```

---

## AI Analysis

### POST /api/analyze
Triggers manual analysis. Returns immediately; result pushed via SSE.
```json
{"status":"ok","msg":"Analysis started"}
```

### GET /api/latest_analysis
Most recent AI result.
```json
{
  "threat_level": "LOW",
  "scene_description": "Empty area, no hazards visible.",
  "safety_checks": {
    "fire":"no fire visible","smoke":"no smoke","persons":"0 visible",
    "ppe":"N/A","hazards":"none"
  },
  "risk_assessment": "...",
  "immediate_action": "Continue monitoring.",
  "incident_summary": "Routine inspection - area clear.",
  "trigger": "MANUAL",
  "has_image": true,
  "timestamp": "2026-06-09 10:30:01"
}
```

---

## Telegram

### GET /api/telegram_info
```json
{"configured":true,"bot_name":"safety_guard_bot","last_sent":"10:30",
 "last_alert":{"event_type":"GAS","timestamp":"..."},"today_alert_count":3}
```

### POST /api/telegram_send_status
Send current sensor status to Telegram.

### POST /api/telegram_send_photo
Send latest camera frame to Telegram.

### POST /api/telegram_analyze_report
Trigger AI analysis and send result + photo to Telegram.

---

## SSE Stream

### GET /stream
Subscribe once; receives all live updates.

```
// Sensor update (every 2s):
{"temp":24.1,"humidity":52.0,"distance":120.0,"gas":false,"pir":false,
 "alerts":[],"led_on":false,"buzzer_on":false,"fan_on":false}

// AI analysis result:
{"ai_analysis":{"threat_level":"LOW","scene_description":"...",...}}

// AI error:
{"ai_error":"Groq API key not configured in config.py"}

// Heartbeat (every 30s):
: heartbeat
```
