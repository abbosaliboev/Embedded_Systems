# Jetson Nano — Setup Guide

The Jetson runs a single script (`jetson/detector.py`) that:
1. Reads frames from the USB webcam
2. Runs YOLOv8n inference
3. Checks if any detected person is inside the defined danger zone
4. POSTs the result to the Pi's REST API

---

## Step 1 — JetPack

Use **JetPack 4.6.x** (Ubuntu 18.04 based). Flash with Balena Etcher.

---

## Step 2 — Install dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-opencv -y

# PyTorch for Jetson (CUDA-enabled wheel)
pip3 install torch torchvision --index-url https://developer.download.nvidia.com/...
# See: https://forums.developer.nvidia.com/t/pytorch-for-jetson

# Ultralytics YOLOv8
pip3 install ultralytics requests
```

---

## Step 3 — Copy the detector script

Copy only the `jetson/` folder to the Jetson:

```bash
scp -r jetson/ <jetson-user>@<JETSON_IP>:~/smart_safety_guard/
```

---

## Step 4 — Configure

Edit `jetson/detector.py` and set:

```python
PI_API_URL   = "http://192.168.1.100:5000/api/detection"  # Pi's static IP
CAMERA_INDEX = 0       # USB webcam index (try 0 or 1)
CONFIDENCE   = 0.5     # Minimum detection confidence
```

Danger zone is defined as a rectangle in pixel coordinates:
```python
DANGER_ZONE = (x1, y1, x2, y2)  # top-left and bottom-right corners
```

Adjust these by running the camera preview first to see the frame dimensions.

---

## Step 5 — Run

```bash
cd ~/smart_safety_guard
python3 jetson/detector.py
```

You should see console output like:
```
[INFO] Camera opened — 1280x720
[INFO] Model loaded: yolov8n.pt
[DETECTION] Person in danger zone (conf=0.87) → sent to Pi
```

---

## Step 6 — Auto-start on boot (optional)

```bash
sudo nano /etc/systemd/system/yolo-detector.service
```

```ini
[Unit]
Description=YOLO Safety Detector
After=network.target

[Service]
User=jetson
WorkingDirectory=/home/jetson/smart_safety_guard
ExecStart=/usr/bin/python3 jetson/detector.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable yolo-detector
sudo systemctl start yolo-detector
```

---

## Danger Zone Calibration

Run this helper on the Jetson to visually define the danger zone:

```bash
python3 jetson/detector.py --calibrate
```

Click and drag on the preview window to draw the zone. The coordinates are printed to the terminal — copy them into `DANGER_ZONE`.
