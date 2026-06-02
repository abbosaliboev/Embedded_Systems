# Raspberry Pi 3 — Setup Guide

## Hardware

| Component | GPIO Pin | Notes |
|-----------|----------|-------|
| PIR Sensor | GPIO 23 | Digital input |
| Ultrasonic TRIG | GPIO 17 | |
| Ultrasonic ECHO | GPIO 27 | |
| MQ-2 Gas (DO) | GPIO 25 | Digital output pin |
| DHT22 | GPIO 4 | Change `DHT_TYPE=22` in config.py |
| Sound Sensor (DO) | GPIO 24 | Digital output pin |
| Buzzer | GPIO 18 | |
| Fan | GPIO 24 | |
| LED Red | GPIO 22 | |
| LED Green | GPIO 11 | |

> Adjust any pin in `config.py` to match your exact wiring.

---

## Step 1 — OS

Use **Raspberry Pi OS Lite** (64-bit) for minimal RAM usage. Flash with Raspberry Pi Imager.

Enable SSH and configure WiFi in the imager before flashing.

---

## Step 2 — Static IP (recommended)

So the Jetson always knows where to send detection results:

```bash
sudo nano /etc/dhcpcd.conf
```

Add at the bottom:
```
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8
```

```bash
sudo reboot
```

---

## Step 3 — System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

---

## Step 4 — Clone the project

```bash
git clone <repo-url> ~/smart_safety_guard
cd ~/smart_safety_guard
```

---

## Step 5 — Python dependencies

```bash
pip install -r requirements.txt
```

If `Adafruit_DHT` fails:
```bash
pip install adafruit-circuitpython-dht
```
Then update the import in `sensors.py` accordingly.

---

## Step 6 — Configure

```bash
nano config.py
```

Key values to check:
- `DHT_TYPE` — set to `22` for DHT22
- `MQ2_DIGITAL_PIN` — verify against your wiring
- `TELEGRAM_TOKEN` — paste your bot token
- `TELEGRAM_CHAT_ID` — paste your chat ID

---

## Step 7 — Run

```bash
python main.py
```

Dashboard: `http://<PI_IP>:5000`
Daily report: `http://<PI_IP>:5000/report`

---

## Step 8 — Auto-start on boot (optional)

```bash
sudo nano /etc/systemd/system/safety-guard.service
```

```ini
[Unit]
Description=Smart Safety Guard
After=network.target

[Service]
User=team4
WorkingDirectory=/home/team4/smart_safety_guard
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable safety-guard
sudo systemctl start safety-guard
```
