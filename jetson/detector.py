"""
Jetson Nano — AI Vision detector.

Runs YOLOv8n on the USB webcam, checks if any detected person
is inside the defined danger zone, and POSTs the result to the
Raspberry Pi backend API.
"""

import time
import argparse
import logging
import sys
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Configuration — edit these before running                          #
# ------------------------------------------------------------------ #

PI_API_URL   = "http://192.168.1.100:5000/api/detection"
CAMERA_INDEX = 0
MODEL_PATH   = "yolov8n.pt"   # downloaded automatically on first run
CONFIDENCE   = 0.50
INFERENCE_FPS = 5             # run inference this many times per second

# Danger zone — pixel rectangle (x1, y1, x2, y2)
# Run with --calibrate to set this visually.
DANGER_ZONE = (200, 100, 600, 500)

# ------------------------------------------------------------------ #


def box_in_zone(box, zone):
    """True if the center of the detection box is inside the danger zone."""
    bx1, by1, bx2, by2 = box
    cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
    zx1, zy1, zx2, zy2 = zone
    return zx1 <= cx <= zx2 and zy1 <= cy <= zy2


def post_result(person_detected: bool, in_danger_zone: bool, confidence: float):
    payload = {
        "person_detected": person_detected,
        "in_danger_zone": in_danger_zone,
        "confidence": round(confidence, 3),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        resp = requests.post(PI_API_URL, json=payload, timeout=2)
        if resp.status_code == 200:
            logger.info("Sent to Pi: %s", payload)
        else:
            logger.warning("Pi returned %s", resp.status_code)
    except requests.exceptions.RequestException as e:
        logger.error("Could not reach Pi: %s", e)


def calibrate(cap):
    """Interactive danger zone calibration — draw a rectangle on the frame."""
    ret, frame = cap.read()
    if not ret:
        logger.error("Cannot read from camera")
        return

    zone = [None, None]
    drawing = False

    def mouse_cb(event, x, y, flags, param):
        nonlocal drawing
        if event == cv2.EVENT_LBUTTONDOWN:
            zone[0] = (x, y)
            drawing = True
        elif event == cv2.EVENT_LBUTTONUP:
            zone[1] = (x, y)
            drawing = False

    cv2.namedWindow("Calibrate — draw danger zone, then press Q")
    cv2.setMouseCallback("Calibrate — draw danger zone, then press Q", mouse_cb)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        display = frame.copy()
        if zone[0] and zone[1]:
            cv2.rectangle(display, zone[0], zone[1], (0, 0, 255), 2)
        cv2.imshow("Calibrate — draw danger zone, then press Q", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()
    if zone[0] and zone[1]:
        x1, y1 = min(zone[0][0], zone[1][0]), min(zone[0][1], zone[1][1])
        x2, y2 = max(zone[0][0], zone[1][0]), max(zone[0][1], zone[1][1])
        print(f"\nDANGER_ZONE = ({x1}, {y1}, {x2}, {y2})")
        print("Copy this into detector.py")


def run():
    model = YOLO(MODEL_PATH)
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        logger.error("Cannot open camera at index %d", CAMERA_INDEX)
        sys.exit(1)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info("Camera opened — %dx%d", w, h)
    logger.info("Model loaded: %s", MODEL_PATH)
    logger.info("Danger zone: %s", DANGER_ZONE)

    interval = 1.0 / INFERENCE_FPS
    last_sent_state = None  # only POST on state change to avoid spam

    while True:
        t_start = time.time()
        ret, frame = cap.read()
        if not ret:
            logger.warning("Frame read failed — retrying")
            time.sleep(0.5)
            continue

        results = model(frame, classes=[0], verbose=False)  # class 0 = person

        person_detected = False
        in_danger_zone = False
        best_conf = 0.0

        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < CONFIDENCE:
                    continue
                person_detected = True
                coords = box.xyxy[0].cpu().numpy()
                if box_in_zone(coords, DANGER_ZONE):
                    in_danger_zone = True
                    best_conf = max(best_conf, conf)

        current_state = (person_detected, in_danger_zone)
        if current_state != last_sent_state:
            if person_detected:
                post_result(person_detected, in_danger_zone, best_conf)
            last_sent_state = current_state

        elapsed = time.time() - t_start
        sleep_for = max(0, interval - elapsed)
        time.sleep(sleep_for)

    cap.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true", help="Run danger zone calibration")
    args = parser.parse_args()

    if args.calibrate:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        calibrate(cap)
        cap.release()
    else:
        run()
