# Smart Safety Guard

Industrial IoT safety monitoring system for Raspberry Pi + Smart IoT Box.

Reads PIR, Ultrasonic, MQ-2 gas, and DHT11 sensors, saves all readings to a
local SQLite database, triggers buzzer/LED/fan actuators on safety events, and
serves a real-time web dashboard accessible from any device on the local network.

## Hardware (Smart IoT Box GPIO mapping)

| Component      | Pin      | Role                          |
|----------------|----------|-------------------------------|
| PIR sensor     | GPIO 23  | Motion detection              |
| Ultrasonic TRIG| GPIO 17  | Distance measurement          |
| Ultrasonic ECHO| GPIO 27  | Distance measurement          |
| MQ-2 (DO pin)  | GPIO 25  | Gas / smoke detection         |
| DHT11          | GPIO 4   | Temperature & humidity        |
| Buzzer         | GPIO 18  | Audible alarm                 |
| DC Fan         | GPIO 24  | Ventilation / cooling         |
| LED Red        | GPIO 22  | Danger indicator              |
| LED Green      | GPIO 11  | Safe indicator                |

Adjust any pin in `config.py` to match your exact wiring.

## Installation

```bash
# On the Raspberry Pi
sudo apt update && sudo apt upgrade -y
pip install -r requirements.txt
```

> **Note:** `Adafruit_DHT` may need to be installed from source on newer Pi OS versions:
> ```bash
> pip install adafruit-circuitpython-dht
> # then change the import in sensors.py accordingly
> ```

## Running

```bash
python main.py
```

Open the dashboard in any browser on the same network:
```
http://<raspberry-pi-ip>:5000
```

Find your Pi's IP with: `hostname -I`

## Project Structure

```
.
├── main.py          # Entry point — starts sensor loop + web server
├── config.py        # GPIO pins, thresholds, timing
├── sensors.py       # Hardware abstraction (reads sensors, drives actuators)
├── alerts.py        # Safety logic — evaluates readings, logs events
├── database.py      # SQLite CRUD helpers
├── web_app.py       # Flask app + SSE endpoint
├── templates/
│   └── index.html   # Dashboard HTML
├── static/
│   ├── style.css    # Dark-theme styles
│   └── app.js       # Live chart + SSE client
├── requirements.txt
└── safety_logs.db   # Created automatically on first run
```

## Dashboard Features

- **Live sensor cards** — update in real-time via Server-Sent Events (no page refresh)
- **Temperature & humidity chart** — last 60 readings with dual Y-axis
- **Safety event log** — timestamped table of all MOTION / GAS / PROXIMITY / OVERHEAT events
- **Status badge** — turns red and pulses when any alert is active

## Alert Logic

| Alert type   | Trigger condition                                 | Actuator response      |
|--------------|---------------------------------------------------|------------------------|
| MOTION       | PIR pin HIGH                                      | Buzzer + Red LED       |
| PROXIMITY    | Distance < 50 cm (configurable)                   | Buzzer + Red LED       |
| GAS          | MQ-2 digital output HIGH                         | Buzzer + Red LED + Fan |
| OVERHEAT     | Temperature > 40 °C (configurable)               | Buzzer + Red LED + Fan |

Events are edge-triggered (logged once on transition, not every poll cycle).

## Simulation Mode

If `RPi.GPIO` or `Adafruit_DHT` are not installed (e.g. running on a laptop for
development), `sensors.py` automatically falls back to randomised mock data so
the full application stack can be tested without hardware.
