# REST API Reference

Base URL: `http://<PI_IP>:5000`

---

## Dashboard endpoints

### `GET /`
Live sensor dashboard (HTML).

### `GET /report`
Daily report page (HTML).

---

## Data API

### `GET /api/latest`
Returns the most recent sensor reading and last 10 safety events.

**Response:**
```json
{
  "reading": {
    "id": 142,
    "timestamp": "2026-05-08 14:23:01",
    "pir": 0,
    "distance": 83.5,
    "gas": 0,
    "temp": 27.4,
    "humidity": 58.0
  },
  "events": [...]
}
```

### `GET /api/history`
Returns last 120 sensor readings (newest first).

### `GET /api/events`
Returns last 100 safety events.

### `GET /api/report?date=YYYY-MM-DD`
Returns daily summary statistics.

**Query params:**
- `date` (optional) — defaults to today

**Response:**
```json
{
  "date": "2026-05-08",
  "stats": {
    "total_readings": 1440,
    "avg_temp": 28.3,
    "max_temp": 41.2,
    "min_temp": 22.1,
    "avg_humidity": 55.0,
    "min_distance": 18.0,
    "motion_count": 12,
    "gas_count": 0
  },
  "events": [
    { "event_type": "MOTION", "cnt": 12 },
    { "event_type": "OVERHEAT", "cnt": 1 }
  ],
  "hourly_temp": [
    { "hour": "08", "avg_temp": 25.1 },
    ...
  ]
}
```

### `GET /api/days`
Returns list of days that have sensor data (last 30 days).

---

## Vision API (Jetson → Pi)

### `POST /api/detection`
Called by Jetson Nano after each YOLO inference cycle.

**Request body:**
```json
{
  "person_detected": true,
  "in_danger_zone": true,
  "confidence": 0.87,
  "timestamp": "2026-05-08 14:23:01"
}
```

**Response:**
```json
{ "status": "ok" }
```

**Behavior on Pi:**
- If `in_danger_zone` is `true` → logs a `PERSON_DETECTED` safety event + triggers buzzer and LED.
- If `person_detected` is `false` → no action, not logged.

---

## SSE Stream

### `GET /stream`
Server-Sent Events endpoint. Browser connects once; Pi pushes a JSON payload every 2 seconds.

**Event format:**
```
data: {"pir": false, "distance": 83.5, "gas": false, "temp": 27.4, "humidity": 58.0, "alerts": []}
```

Possible `alerts` values: `"MOTION"`, `"GAS"`, `"PROXIMITY"`, `"OVERHEAT"`, `"PERSON_DETECTED"`.
