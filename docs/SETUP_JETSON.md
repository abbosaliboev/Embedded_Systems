# Jetson Nano Setup Guide

## Requirements
- NVIDIA Jetson Nano 4GB, JetPack 4.x (Ubuntu 18.04)
- USB Webcam, same LAN as Raspberry Pi

## Critical: Use Python 3.8 venv

System Python 3.6 has incompatible packages -> `Illegal instruction` crash.
Always use the Python 3.8 virtual environment.

```bash
source ~/detector_venv/bin/activate
python3 -c "import cv2; print(cv2.__version__)"  # should be 4.x
```

## Setup from Scratch (if venv missing)

```bash
sudo apt install python3.8 python3.8-venv -y
python3.8 -m venv ~/detector_venv
source ~/detector_venv/bin/activate
pip install requests numpy opencv-python==4.8.0.76
```

## Run Detector

```bash
source ~/detector_venv/bin/activate
cd ~/Embedded_Systems
python3 jetson/detector.py
```

Expected output:
```
[WARNING] torch / YOLOv5 not available - sending raw frames only.
[INFO] Camera 640x480 | YOLO: NO | PI: http://10.198.137.204:5000
```
Raw frame mode: camera feed visible on dashboard, no person detection.

## Install PyTorch for YOLOv5 (optional)

```bash
# JetPack 4.6, Python 3.8:
wget https://nvidia.box.com/shared/static/ssf2v7pf5i245fk4i0q926hy4imzs2ph.whl \
     -O torch-1.11.0-cp38-cp38-linux_aarch64.whl
pip install torch-1.11.0-cp38-cp38-linux_aarch64.whl
python3 -c "import torch; print(torch.__version__)"
```

## Configure Pi IP

Edit `jetson/detector.py` line 25:
```python
PI_BASE_URL = "http://10.198.137.204:5000"  # Your Pi IP
```

## Auto-start on Boot

```bash
sudo nano /etc/systemd/system/detector.service
```
```ini
[Unit]
Description=Smart Safety Detector
After=network.target

[Service]
User=dalab
WorkingDirectory=/home/dalab/Embedded_Systems
ExecStart=/home/dalab/detector_venv/bin/python3 jetson/detector.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable detector && sudo systemctl start detector
```

## Troubleshooting

**Illegal instruction (core dumped):**
Use venv python3.8, NOT system `python3` (3.6).

**Camera not found:**
```bash
ls /dev/video*
python3 -c "import cv2; cap=cv2.VideoCapture(0); print(cap.isOpened())"
```

**Pi not reachable:**
```bash
curl http://10.198.137.204:5000/api/frame_info
```
