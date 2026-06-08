# Raspberry Pi 3 Setup Guide

## Requirements
- Raspberry Pi 3 Model B+ with Raspberry Pi OS (Bullseye or later)
- Python 3.9+, connected to local network

## 1. Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-dev git

git clone https://github.com/abbosaliboev/Embedded_Systems.git
cd Embedded_Systems
pip3 install -r requirements.txt
pip3 install Adafruit_DHT
```

## 2. Configure

Edit `config.py`:
```python
GROQ_API_KEY = "gsk_..."          # Get free key at console.groq.com
TELEGRAM_BOT_TOKEN = "12345:AAB..." # From @BotFather
GAS_ALERT_ACTIVE = True            # Set False if sensor unreliable
DISTANCE_DANGER_CM = 50            # Proximity threshold (cm)
TEMP_HIGH_CELSIUS = 40.0           # Overheat threshold
```

## 3. Run

```bash
python3 main.py
# Dashboard: http://<PI_IP>:5000
```

## 4. Auto-start on Boot

```bash
sudo nano /etc/systemd/system/safety_guard.service
```
```ini
[Unit]
Description=Smart Safety Guard
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/Embedded_Systems
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable safety_guard && sudo systemctl start safety_guard
```

## 5. GPIO Wiring

| Sensor/Actuator   | GPIO BCM | Physical Pin |
|-------------------|----------|--------------|
| PIR motion        | 4        | Pin 7        |
| DHT22 data        | 27       | Pin 13       |
| HC-SR04 TRIG      | 18       | Pin 12       |
| HC-SR04 ECHO      | 21       | Pin 40       |
| MQ-2 digital      | 25       | Pin 22       |
| Buzzer            | 20       | Pin 38       |
| LED Danger (Red)  | 12       | Pin 32       |
| LED Safe (Green)  | 13       | Pin 33       |
| LED Blue 1        | 5        | Pin 29       |
| LED Blue 2        | 6        | Pin 31       |
| LED Blue 3        | 19       | Pin 35       |

## Troubleshooting

**Gas sensor always triggered:**
Set `GAS_ALERT_ACTIVE = False` in config.py temporarily.
Hardware fix: adjust MQ-2 potentiometer until D0 LED turns off in clean air.

**Telegram not sending:**
Run `python3 main.py`, send `/start` to your bot.
Chat_id is auto-saved to `.telegram_chat_id` file.

**DHT22 no readings:**
Check 4.7kOhm pull-up resistor on data line. System falls back to simulated data.
